"""Commit-pinned community fork installation.

A catalog fork becomes a local Harness version in three steps:

1. **Plan** – the fork must be a GitHub repository from the catalog. Forge pins
   the catalog's captured commit, or the current head of the default branch
   when the catalog has none, and shows that exact commit before anything is
   downloaded.
2. **Acquire** – a hardened ``git fetch`` of that single commit into a staging
   directory. System and global Git configuration, hooks, credential helpers,
   submodules, LFS, non-HTTPS transports, and symlinks are all disabled, and no
   token is ever sent. ``HEAD`` must equal the pinned commit before the checkout
   is moved into ``<versions>/forks``.
3. **Build** – dependency installation and the repository's build script run
   only inside the pinned Apptainer sandbox with a disposable home and no
   launcher secrets. There is no host build fallback.

The resulting tree is classified ``community``: it can run only in Apptainer
cells launched with an explicit risk acknowledgement, and never as a host
profile, assistant, or package host.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Any, Callable, Iterator, Mapping, Sequence

from .file_lock import lock as lock_file, unlock as unlock_file


SCHEMA = "dsh-forge.fork-installations/v1"
REPOSITORY_URL = re.compile(r"https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9_.-]{1,100})")
FULL_SHA = re.compile(r"[0-9a-f]{40}")
BRANCH = re.compile(r"[A-Za-z0-9._/-]{1,200}")
INSTALL_ID = re.compile(r"fork_[a-f0-9]{16}")
GIT_TIMEOUT_SECONDS = 900
LS_REMOTE_TIMEOUT_SECONDS = 60
MAX_CHECKOUT_BYTES = 4 * 1024 * 1024 * 1024
MAX_CHECKOUT_FILES = 250_000
LOG_LIMIT = 256 * 1024
ACTIVE_STATES = {"queued", "fetching", "building"}
SHIM_DIRECTORY = "/home/dsh/.local/bin"
HARDENED_GIT_CONFIG = (
    "protocol.allow=never",
    "protocol.https.allow=always",
    "core.hooksPath=" + os.devnull,
    "core.fsmonitor=false",
    "core.symlinks=false",
    "core.protectNTFS=true",
    "core.protectHFS=true",
    "submodule.recurse=false",
    "fetch.recurseSubmodules=false",
    "credential.helper=",
    "credential.interactive=false",
    "filter.lfs.smudge=",
    "filter.lfs.process=",
    "filter.lfs.required=false",
    "advice.detachedHead=false",
    "init.defaultBranch=forge",
)
PASSTHROUGH_ENV = (
    "PATH", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR", "GIT_SSL_CAINFO",
    "HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy", "NO_PROXY", "no_proxy", "ALL_PROXY", "all_proxy",
)

Runner = Callable[..., subprocess.CompletedProcess]


class ForkInstallError(Exception):
    """A user-facing fork installation failure."""


def normalize_remote(value: str | None) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\.git$", "", text.rstrip("/"))
    return text.lower()


def fork_identity(artifact: Mapping[str, Any]) -> tuple[str, str, str]:
    """Validate a catalog record and return ``(full_name, url, branch)``."""
    if artifact.get("artifact_type") != "fork":
        raise ForkInstallError("Only catalog forks can be installed as Harness versions")
    url = str(artifact.get("repository_url") or "")
    match = REPOSITORY_URL.fullmatch(url)
    if not match:
        raise ForkInstallError("Fork repository must be a public https://github.com/<owner>/<repo> URL")
    full_name = f"{match.group(1)}/{match.group(2)}"
    if str(artifact.get("full_name") or "").lower() != full_name.lower():
        raise ForkInstallError("Fork repository URL does not match its catalog name")
    if artifact.get("archived") is True:
        raise ForkInstallError("Archived forks are not installed")
    branch = str(artifact.get("default_branch") or "")
    if branch and (not BRANCH.fullmatch(branch) or ".." in branch or branch.startswith("-")):
        raise ForkInstallError("Fork default branch has an unsupported name")
    return full_name, url, branch


def directory_name(full_name: str, commit: str) -> str:
    owner, name = full_name.split("/", 1)
    safe = re.sub(r"[^A-Za-z0-9_.-]", "-", f"{owner}--{name}")[:120].strip(".-") or "fork"
    return f"{safe}@{commit[:12]}"


def detect_build(root: Path) -> dict[str, Any]:
    """Choose fixed dependency and build commands from lockfiles; never from repository text."""
    try:
        manifest = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        manifest = {}
    scripts = manifest.get("scripts") if isinstance(manifest.get("scripts"), dict) else {}
    has_build = isinstance(scripts.get("build"), str) and bool(scripts.get("build"))
    # Build scripts in pnpm and yarn monorepos call the package manager by its
    # bare name, so corepack first installs its shim into the disposable build
    # home, which the sandbox puts first on PATH.
    shims = ["corepack", "enable", "--install-directory", SHIM_DIRECTORY]
    if (root / "pnpm-lock.yaml").is_file():
        manager, install = "pnpm", ["corepack", "pnpm", "install", "--frozen-lockfile"]
        build = ["corepack", "pnpm", "run", "build"]
        prepare = [[*shims, "pnpm"]]
    elif (root / "yarn.lock").is_file():
        manager, install = "yarn", ["corepack", "yarn", "install", "--immutable"]
        build = ["corepack", "yarn", "run", "build"]
        prepare = [[*shims, "yarn"]]
    elif (root / "package-lock.json").is_file():
        manager, install = "npm", ["npm", "ci", "--no-audit", "--no-fund"]
        build = ["npm", "run", "build"]
        prepare = []
    else:
        return {"manager": None, "steps": [], "reason": "No supported lockfile; the checkout must already contain a built CLI"}
    steps = [*prepare, install] + ([build] if has_build else [])
    return {"manager": manager, "steps": steps, "reason": "" if has_build else "No build script; dependencies only"}


class ForkInstaller:
    """Own the fork-installation registry and acquisition of pinned checkouts."""

    def __init__(
        self,
        forks_root: Path,
        state_root: Path,
        *,
        runner: Runner = subprocess.run,
        git: str | None = None,
    ):
        self.forks_root = Path(forks_root)
        self.state_root = Path(state_root)
        self.registry_file = self.state_root / "fork-installations.json"
        self.lock_path = self.state_root / "fork-installations.lock"
        self.logs_root = self.state_root / "fork-logs"
        self._runner = runner
        self.git = git or shutil.which("git")
        self._lock = threading.RLock()
        self._threads: dict[str, threading.Thread] = {}

    # ------------------------------------------------------------ registry
    @contextmanager
    def _file_lock(self) -> Iterator[None]:
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            lock_file(descriptor)
            yield
        finally:
            unlock_file(descriptor)
            os.close(descriptor)

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            payload = json.loads(self.registry_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise ForkInstallError("Fork installation registry is unreadable") from None
        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
            raise ForkInstallError("Unsupported fork installation registry schema")
        records = payload.get("installations")
        return {
            str(item["id"]): item for item in records if isinstance(item, dict) and INSTALL_ID.fullmatch(str(item.get("id")))
        } if isinstance(records, list) else {}

    def _save(self, records: Mapping[str, Mapping[str, Any]]) -> None:
        payload = {"schema": SCHEMA, "installations": list(records.values())}
        descriptor, temporary = tempfile.mkstemp(prefix=".forks-", dir=self.state_root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.registry_file)
        except BaseException:
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise

    def records(self) -> list[dict[str, Any]]:
        with self._lock, self._file_lock():
            records = self._load()
        return sorted(records.values(), key=lambda item: int(item.get("created_at") or 0))

    def public_records(self) -> list[dict[str, Any]]:
        return [
            {key: value for key, value in record.items() if not key.startswith("real_")}
            for record in self.records()
        ]

    def update(self, install_id: str, **changes: Any) -> dict[str, Any]:
        with self._lock, self._file_lock():
            records = self._load()
            record = records.get(install_id)
            if not record:
                raise ForkInstallError("Unknown fork installation")
            record.update(changes)
            record["updated_at"] = int(time.time() * 1000)
            self._save(records)
            return dict(record)

    def for_path(self, path: str | Path) -> dict[str, Any] | None:
        """Return the newest live installation that owns this exact checkout path.

        Retries reuse the same checkout, so earlier failed attempts share the
        path; they must not shadow the attempt that is building or ready.
        """
        try:
            resolved = str(Path(path).resolve())
        except OSError:
            return None
        for record in reversed(self.records()):
            if record.get("real_path") == resolved and record.get("state") not in {"removed", "failed"}:
                return record
        return None

    def for_artifact(self, artifact_id: str) -> dict[str, Any] | None:
        matches = [
            record for record in self.records()
            if record.get("artifact_id") == artifact_id and record.get("state") != "removed"
        ]
        return matches[-1] if matches else None

    # ------------------------------------------------------------ git
    def _environment(self, home: Path) -> dict[str, str]:
        environment = {name: value for name in PASSTHROUGH_ENV if (value := os.environ.get(name))}
        environment.update({
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": "",
            "SSH_ASKPASS": "",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "GIT_ALLOW_PROTOCOL": "https",
            "GIT_PROTOCOL_FROM_USER": "0",
        })
        return environment

    def git_argv(self, *args: str, cwd: Path | None = None) -> list[str]:
        if not self.git:
            raise ForkInstallError("Git is required to install forks")
        argv = [self.git]
        for item in HARDENED_GIT_CONFIG:
            argv.extend(["-c", item])
        if cwd is not None:
            argv.extend(["-C", str(cwd)])
        return [*argv, *args]

    def _git(self, *args: str, cwd: Path | None, home: Path, timeout: int, log: Path | None = None) -> str:
        argv = self.git_argv(*args, cwd=cwd)
        try:
            completed = self._runner(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                check=False,
                env=self._environment(home),
            )
        except subprocess.TimeoutExpired:
            raise ForkInstallError(f"git {args[0]} exceeded {timeout}s") from None
        except OSError as error:
            raise ForkInstallError(f"Could not run git: {error}") from None
        output = completed.stdout or ""
        if log is not None:
            self._append_log(log, f"$ git {' '.join(args)}\n{output[-8192:]}\n")
        if completed.returncode != 0:
            last = output.strip().splitlines()[-1:] or [f"exit {completed.returncode}"]
            raise ForkInstallError(f"git {args[0]} failed: {last[0][:300]}")
        return output

    def resolve_head(self, url: str, branch: str) -> str:
        with tempfile.TemporaryDirectory(prefix="git-home-") as raw:
            ref = f"refs/heads/{branch}" if branch else "HEAD"
            output = self._git(
                "ls-remote", "--exit-code", url, ref,
                cwd=None, home=Path(raw), timeout=LS_REMOTE_TIMEOUT_SECONDS,
            )
        for line in output.splitlines():
            parts = line.split()
            if len(parts) == 2 and FULL_SHA.fullmatch(parts[0]) and parts[1] == ref:
                return parts[0]
        raise ForkInstallError("Could not resolve the fork's current commit")

    # ------------------------------------------------------------ plan
    def plan(self, artifact: Mapping[str, Any]) -> dict[str, Any]:
        full_name, url, branch = fork_identity(artifact)
        captured = str(artifact.get("head_sha") or "")
        if FULL_SHA.fullmatch(captured):
            commit, source = captured, "catalog"
        else:
            commit, source = self.resolve_head(url, branch), "remote-head"
        destination = self.forks_root / directory_name(full_name, commit)
        existing = self.for_artifact(str(artifact.get("artifact_id") or ""))
        return {
            "artifact_id": str(artifact.get("artifact_id") or ""),
            "full_name": full_name,
            "repository_url": url,
            "default_branch": branch or None,
            "commit": commit,
            "commit_source": source,
            "destination": str(destination),
            "existing": {k: v for k, v in existing.items() if not k.startswith("real_")} if existing else None,
            "steps": [
                "Fetch exactly this commit over HTTPS with hooks, submodules, LFS, and credentials disabled",
                "Install dependencies and build inside the pinned Apptainer sandbox (network on, no secrets)",
                "Register it under Local as a community fork that runs only in Apptainer cells",
            ],
        }

    # ------------------------------------------------------------ install
    def begin(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        """Create a queued record; refuses to start a second active install of one fork."""
        commit = str(plan.get("commit") or "")
        if not FULL_SHA.fullmatch(commit):
            raise ForkInstallError("A full 40-character commit is required")
        destination = Path(str(plan["destination"]))
        with self._lock, self._file_lock():
            records = self._load()
            for record in records.values():
                if record.get("artifact_id") == plan["artifact_id"] and record.get("state") in ACTIVE_STATES:
                    raise ForkInstallError("This fork is already being installed")
                if record.get("real_path") == str(destination.resolve()) and record.get("state") == "ready":
                    raise ForkInstallError("This exact commit is already installed")
            install_id = "fork_" + secrets.token_hex(8)
            self.logs_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            now = int(time.time() * 1000)
            record = {
                "id": install_id,
                "artifact_id": plan["artifact_id"],
                "full_name": plan["full_name"],
                "repository_url": plan["repository_url"],
                "commit": commit,
                "commit_source": plan.get("commit_source"),
                "path": str(destination),
                "real_path": str(destination.resolve()),
                "state": "queued",
                "detail": "Waiting to fetch the pinned commit",
                "build": None,
                "created_at": now,
                "updated_at": now,
                "log_path": str(self.logs_root / f"{install_id}.log"),
            }
            records[install_id] = record
            self._save(records)
            return dict(record)

    @staticmethod
    def _append_log(path: Path, text: str) -> None:
        try:
            if path.exists() and path.stat().st_size > LOG_LIMIT:
                return
            with path.open("a", encoding="utf-8") as handle:
                handle.write(text)
        except OSError:
            pass

    def acquire(self, record: Mapping[str, Any]) -> Path:
        """Fetch the pinned commit into staging, verify HEAD, then move it into place."""
        destination = Path(str(record["real_path"]))
        commit = str(record["commit"])
        log = Path(str(record["log_path"]))
        if destination.is_symlink():
            raise ForkInstallError("The destination folder is a symlink; remove it first")
        if destination.exists():
            if self._verified_checkout(destination, commit, str(record["repository_url"])):
                self._append_log(log, f"Reusing the existing checkout of {commit} at {destination}\n")
                return destination
            raise ForkInstallError("A different checkout already exists at the destination; remove it first")
        self.forks_root.mkdir(parents=True, exist_ok=True, mode=0o755)
        staging_root = self.forks_root / ".incoming"
        staging_root.mkdir(exist_ok=True, mode=0o700)
        staging = Path(tempfile.mkdtemp(prefix=destination.name[:40] + "-", dir=staging_root))
        try:
            with tempfile.TemporaryDirectory(prefix="git-home-") as raw_home, \
                    tempfile.TemporaryDirectory(prefix="git-template-") as template:
                home = Path(raw_home)
                self._git("init", "--quiet", f"--template={template}", str(staging), cwd=None, home=home, timeout=60, log=log)
                self._git("remote", "add", "origin", str(record["repository_url"]), cwd=staging, home=home, timeout=60, log=log)
                self._git(
                    "fetch", "--depth=1", "--no-tags", "--no-recurse-submodules", "origin", commit,
                    cwd=staging, home=home, timeout=GIT_TIMEOUT_SECONDS, log=log,
                )
                self._git("checkout", "--quiet", "--detach", "FETCH_HEAD", cwd=staging, home=home, timeout=GIT_TIMEOUT_SECONDS, log=log)
                head = self._git("rev-parse", "HEAD", cwd=staging, home=home, timeout=60).strip()
            if head != commit:
                raise ForkInstallError("Fetched HEAD does not match the pinned commit")
            self._check_size(staging)
            os.replace(staging, destination)
            self._append_log(log, f"Checked out {commit} into {destination}\n")
            return destination
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def _verified_checkout(self, path: Path, commit: str, url: str) -> bool:
        """True when an earlier attempt already placed exactly this commit here."""
        if not (path / ".git").is_dir():
            return False
        with tempfile.TemporaryDirectory(prefix="git-home-") as raw:
            try:
                head = self._git("rev-parse", "HEAD", cwd=path, home=Path(raw), timeout=60).strip()
                remote = self._git("remote", "get-url", "origin", cwd=path, home=Path(raw), timeout=60).strip()
            except ForkInstallError:
                return False
        return head == commit and normalize_remote(remote) == normalize_remote(url)

    @staticmethod
    def _check_size(root: Path) -> None:
        total = 0
        files = 0
        for directory, _dirs, names in os.walk(root):
            for name in names:
                files += 1
                try:
                    total += os.lstat(os.path.join(directory, name)).st_size
                except OSError:
                    continue
                if total > MAX_CHECKOUT_BYTES or files > MAX_CHECKOUT_FILES:
                    raise ForkInstallError("Fork checkout exceeds the size limit")

    def start(self, install_id: str, work: Callable[[str], None]) -> None:
        """Run ``work`` for one installation on a background thread."""
        def target() -> None:
            try:
                work(install_id)
            except ForkInstallError as error:
                self.update(install_id, state="failed", detail=str(error)[:500])
            except Exception as error:  # pragma: no cover - defensive
                self.update(install_id, state="failed", detail=f"Internal error: {type(error).__name__}")
            finally:
                with self._lock:
                    self._threads.pop(install_id, None)

        thread = threading.Thread(target=target, name=f"fork-install-{install_id}", daemon=True)
        with self._lock:
            self._threads[install_id] = thread
        thread.start()

    def wait(self, install_id: str, timeout: float | None = None) -> None:
        with self._lock:
            thread = self._threads.get(install_id)
        if thread:
            thread.join(timeout)

    def remove(self, install_id: str) -> dict[str, Any]:
        """Delete a Forge-created checkout and mark its record removed."""
        if not INSTALL_ID.fullmatch(str(install_id or "")):
            raise ForkInstallError("Choose a fork installation")
        with self._lock, self._file_lock():
            records = self._load()
            record = records.get(install_id)
            if not record:
                raise ForkInstallError("Unknown fork installation")
            if record.get("state") in ACTIVE_STATES:
                raise ForkInstallError("Wait for the installation to finish before removing it")
            path = Path(str(record.get("real_path") or ""))
            forks_root = self.forks_root.resolve()
            try:
                path.relative_to(forks_root)
            except ValueError:
                raise ForkInstallError("Forge only removes checkouts it created under the forks folder") from None
            if path.parent != forks_root or path.is_symlink():
                raise ForkInstallError("Forge only removes checkouts it created under the forks folder")
            if path.exists():
                shutil.rmtree(path)
            record.update({"state": "removed", "detail": "Checkout removed", "updated_at": int(time.time() * 1000)})
            self._save(records)
            return dict(record)

    def log_tail(self, install_id: str, limit: int = 200) -> list[str]:
        for record in self.records():
            if record.get("id") == install_id:
                try:
                    lines = Path(str(record["log_path"])).read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    return []
                return lines[-limit:]
        raise ForkInstallError("Unknown fork installation")


def build_summary(steps: Sequence[Sequence[str]]) -> list[str]:
    return [" ".join(step) for step in steps]
