"""Evidence-based discovery and guarded local process control for DSH Forge."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
import uuid
from pathlib import Path
from typing import Any, Iterable

import fcntl

from .packages import PackageError
from .sandbox import ApptainerSandbox, SandboxConfig, SandboxError


PROTECTED_PORTS = {3080, 3090}
CELL_REGISTRY_SCHEMA_VERSION = 1
CELL_REGISTRY_EVENT_LIMIT = 64
VERSION_REGISTRY_SCHEMA_VERSION = 1
DEFAULT_VERSIONS_DIRECTORY = "dsh-versions"
DEFAULT_VERSION_LAUNCH = {
    "surface": "web",
    "profile": "tui-min",
    "port": "auto",
    "open_browser": False,
    "home_mode": "fresh",
    "workspace": "managed",
    "network": "host",
    "resources": {"gpu": "none"},
}
SECRET_NAMES = (
    "DEEPSEEK_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GITHUB_TOKEN",
    "GH_TOKEN",
)
SAFE_ENV_NAMES = (
    "PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "SHELL", "USER",
    "TERM", "COLORTERM", "NO_COLOR", "NODE_EXTRA_CA_CERTS", "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "no_proxy", "all_proxy",
)
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".cache",
    ".venv",
    "venv",
    "dist",
    "build",
}
CLONE_EXCLUDES = {
    ".cache",
    "cache",
    "caches",
    "sessions",
    "session",
    "credentials",
    "secrets",
    "locks",
    "pids",
    "sockets",
}


class LauncherError(Exception):
    """A user-facing launcher validation or policy failure."""


def _display_path(path: Path) -> str:
    try:
        return "~/" + str(path.resolve().relative_to(Path.home().resolve()))
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _version_launch_settings(raw: Any = None) -> dict[str, Any]:
    """Return the small, safe preset supported by one-click local launches."""
    value = raw if isinstance(raw, dict) else {}
    resources = value.get("resources") if isinstance(value.get("resources"), dict) else {}
    gpu = str(value.get("gpu") or resources.get("gpu") or "none").strip().lower()
    if gpu not in {"none", "allocated"}:
        gpu = "none"
    return {
        **DEFAULT_VERSION_LAUNCH,
        "open_browser": value.get("open_browser") is True,
        "resources": {"gpu": gpu},
    }


def _file_sha256(path: Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _run_git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _git_metadata(root: Path) -> tuple[dict[str, Any] | None, str | None]:
    top = _run_git(root, "rev-parse", "--show-toplevel")
    if not top:
        return None, None
    git_root = Path(top)
    sha = _run_git(git_root, "rev-parse", "--short=12", "HEAD")
    branch = _run_git(git_root, "branch", "--show-current") or "detached"
    dirty = bool(_run_git(git_root, "status", "--porcelain", "--untracked-files=no"))
    remote = _run_git(git_root, "remote", "get-url", "origin")
    return ({"branch": branch, "sha": sha or "unknown", "dirty": dirty}, remote)


def _process_birth(pid: int) -> str | None:
    """Return a stable process-start identity where the platform exposes one."""
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").split()
        if len(fields) > 21:
            return "linux-ticks:" + fields[21]
    except (OSError, UnicodeError):
        pass
    try:
        result = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=1,
            check=False,
        )
        value = result.stdout.strip()
        return "ps:" + value if result.returncode == 0 and value else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _port_available(port: int) -> bool:
    if not 1024 <= port <= 65535:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _tree_id(path: Path) -> str:
    return "tree_" + hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:12]


def _version_id(path: Path) -> str:
    return "version_" + hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:12]


def _candidate_dirs(root: Path, max_depth: int = 3, max_nodes: int = 500) -> Iterable[Path]:
    """Bounded directory traversal; explicit roots only and no candidate execution."""
    root = root.resolve()
    if not root.is_dir():
        return
    queue: list[tuple[Path, int]] = [(root, 0)]
    visited = 0
    while queue and visited < max_nodes:
        current, depth = queue.pop(0)
        visited += 1
        yield current
        if depth >= max_depth:
            continue
        try:
            children = sorted((p for p in current.iterdir() if p.is_dir()), key=lambda p: p.name)
        except OSError:
            continue
        for child in children:
            if child.name not in SKIP_DIRS and not child.is_symlink():
                queue.append((child, depth + 1))


def _is_harness_package_name(value: Any) -> bool:
    """Accept Harness CLIs without treating internal dsh-* tools as versions."""
    package_name = str(value or "").strip().lower()
    unscoped_name = package_name.rsplit("/", 1)[-1]
    return unscoped_name in {"dsh", "deepseek-harness"}


def _source_candidate(root: Path) -> tuple[Path, dict[str, Any]] | None:
    package = _read_json(root / "package.json")
    cli_package = _read_json(root / "apps" / "cli" / "package.json")
    package_name = str(package.get("name", "")).lower()
    signatures = [
        (root / "apps" / "cli" / "lib" / "bin.js", cli_package),
        (root / "apps" / "cli" / "src" / "bin.ts", cli_package),
        (root / "lib" / "bin.js", package),
        (root / "src" / "bin.ts", package),
        (root / "packages" / "cli" / "bin" / "dsh.js", package),
        (root / "packages" / "cli" / "dist" / "bin" / "dsh.js", package),
        (root / "bin" / "dsh", package),
        (root / "dsh", package),
    ]
    selected = next(((path, metadata) for path, metadata in signatures if path.is_file()), None)
    executable, selected_package = selected if selected else (None, {})
    if selected_package:
        package = selected_package
        package_name = str(package.get("name", "")).lower()
    named_package = _is_harness_package_name(package_name)
    recognized_root = named_package or root.name.lower() in {"deepseek-harness", "dsh"}
    recognized_layout = bool(package and executable and executable.parts[-4:-1] in {
        ("packages", "cli", "bin"),
        ("cli", "dist", "bin"),
    })
    if not executable or not (recognized_root or recognized_layout):
        return None
    return executable, package


def _official_remote(remote: str) -> bool:
    value = remote.strip().lower().rstrip("/")
    return bool(re.fullmatch(
        r"(?:https?://github\.com/|git@github\.com:|ssh://git@github\.com/)deepseek-ai/deepseek-harness(?:\.git)?",
        value,
    ))


def _trust_for(root: Path, remote: str | None) -> str:
    if remote and not _official_remote(remote):
        return "foreign"
    return "personal" if os.access(root, os.W_OK) else "readonly"


class Launcher:
    """Own scanner configuration and processes started by this sidecar instance."""

    def __init__(
        self,
        scan_roots: Iterable[str | Path] = (),
        state_root: str | Path | None = None,
        sandbox: ApptainerSandbox | None = None,
    ):
        configured_state = state_root or os.environ.get("DSH_FORGE_STATE_DIR")
        self.state_root = Path(configured_state).expanduser() if configured_state else Path.home() / ".local" / "state" / "dsh-forge"
        self.launch_cwd = Path.cwd().resolve()
        self.protected_ports = set(PROTECTED_PORTS)
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.logs_root = self.state_root / "logs"
        self.cells_root = self.state_root / "cells"
        self.logs_root.mkdir(exist_ok=True, mode=0o700)
        self.cells_root.mkdir(exist_ok=True, mode=0o700)
        self.roots_file = self.state_root / "scan-roots.json"
        self.roots_lock_file = self.state_root / "scan-roots.lock"
        self.cells_file = self.state_root / "cells.json"
        self.cells_lock_file = self.state_root / "cells.lock"
        self.sandbox_results_file = self.state_root / "sandbox-results.json"
        self._lock = threading.RLock()
        self._mutation_lock = threading.RLock()
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._registry_generation = 0
        self._cells: dict[str, dict[str, Any]] = self._load_cells()
        self._trees: dict[str, dict[str, Any]] = {}
        self._coverage_gaps: list[str] = []
        self.sandbox = sandbox or ApptainerSandbox(SandboxConfig.from_environment(), self.state_root / "sandbox")
        self._sandbox_results = self._load_sandbox_results()
        roots = [Path(p).expanduser() for p in scan_roots]
        env_roots = os.environ.get("DSH_FORGE_SCAN_ROOTS", "")
        roots.extend(Path(p).expanduser() for p in env_roots.split(os.pathsep) if p)
        managed_directory = os.environ.get("DSH_FORGE_VERSIONS_DIR")
        self.versions_directory = (
            Path(managed_directory).expanduser()
            if managed_directory
            else Path.home() / DEFAULT_VERSIONS_DIRECTORY
        ).resolve()
        if self.versions_directory.is_dir():
            roots.append(self.versions_directory)
        self._configured_scan_roots = self._dedupe_paths(roots)
        self._saved_roots = self._load_roots()
        self._scan_roots = self._dedupe_paths([
            *self._configured_scan_roots,
            *(record["path"] for record in self._saved_roots.values()),
        ])
        self.scan()

    def _load_roots(self) -> dict[str, dict[str, Any]]:
        """Load durable local-version roots, accepting the alpha string format."""
        payload = _read_json(self.roots_file)
        schema_version = payload.get("schema_version", VERSION_REGISTRY_SCHEMA_VERSION)
        if schema_version != VERSION_REGISTRY_SCHEMA_VERSION:
            raise LauncherError(
                f"Unsupported local-version registry schema {schema_version}; "
                f"expected {VERSION_REGISTRY_SCHEMA_VERSION}"
            )
        raw_roots = payload.get("roots", [])
        records: dict[str, dict[str, Any]] = {}
        for raw in raw_roots if isinstance(raw_roots, list) else []:
            if isinstance(raw, str):
                raw_path, added_at = raw, 0
            elif isinstance(raw, dict) and isinstance(raw.get("path"), str):
                raw_path = raw["path"]
                added_at = raw.get("added_at", 0)
            else:
                continue
            try:
                path = Path(raw_path).expanduser().resolve()
            except OSError:
                continue
            record_id = _version_id(path)
            source = raw.get("source") if isinstance(raw, dict) else "manual"
            records[record_id] = {
                "id": record_id,
                "path": path,
                "added_at": added_at if isinstance(added_at, int) and added_at >= 0 else 0,
                "source": source if source in {"auto", "manual"} else "manual",
                "launch": _version_launch_settings(raw.get("launch") if isinstance(raw, dict) else None),
            }
        return records

    def _load_sandbox_results(self) -> dict[str, dict[str, Any]]:
        raw = _read_json(self.sandbox_results_file).get("results", {})
        if not isinstance(raw, dict):
            return {}
        return {str(key): value for key, value in raw.items() if isinstance(value, dict)}

    def _save_sandbox_results(self) -> None:
        temporary = self.sandbox_results_file.with_suffix(".tmp")
        temporary.write_text(json.dumps({"results": self._sandbox_results}, indent=2) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.sandbox_results_file)

    def _sandbox_key(self, tree: dict[str, Any]) -> str:
        revision = str((tree.get("git") or {}).get("sha") or "unknown")
        image = str(self.sandbox.status().get("image_sha256") or "unconfigured")
        executable = str(tree.get("executable_sha256") or "unknown")
        material = "\0".join((str(tree.get("real_path")), revision, executable, image))
        return hashlib.sha256(material.encode()).hexdigest()

    @staticmethod
    def _sandbox_summary(result: dict[str, Any]) -> dict[str, Any]:
        return {key: result.get(key) for key in (
            "status", "exit_code", "duration_ms", "tested_at", "network",
            "secrets_forwarded", "image_sha256", "executable_sha256", "command_summary",
        )}

    @contextmanager
    def _registry_file_lock(self):
        """Serialize registry mutations across the sidecar and CLI processes."""
        descriptor = os.open(self.cells_lock_file, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @contextmanager
    def _roots_file_lock(self):
        """Serialize saved local-version mutations across UI and CLI processes."""
        descriptor = os.open(self.roots_lock_file, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _load_cells(self) -> dict[str, dict[str, Any]]:
        payload = _read_json(self.cells_file)
        schema_version = payload.get("schema_version", CELL_REGISTRY_SCHEMA_VERSION)
        if schema_version != CELL_REGISTRY_SCHEMA_VERSION:
            raise LauncherError(
                f"Unsupported cell registry schema {schema_version}; expected {CELL_REGISTRY_SCHEMA_VERSION}"
            )
        generation = payload.get("generation", 0)
        self._registry_generation = generation if isinstance(generation, int) and generation >= 0 else 0
        raw = payload.get("cells", [])
        cells: dict[str, dict[str, Any]] = {}
        for cell in raw if isinstance(raw, list) else []:
            if not isinstance(cell, dict) or not isinstance(cell.get("id"), str):
                continue
            if not isinstance(cell.get("pid"), int) or not isinstance(cell.get("process_birth"), str):
                continue
            cell.setdefault("execution_backend", "legacy-host-preview")
            cell.setdefault("sandboxed", False)
            cell.setdefault("parent_cell_id", None)
            cell.setdefault("lineage_action", "legacy")
            cell.setdefault("created_at", cell.get("started"))
            cell.setdefault("updated_at", cell.get("started"))
            cell.setdefault("lifecycle", [])
            if cell.get("state") not in {"stopped", "exited"}:
                current_birth = _process_birth(cell["pid"])
                if current_birth == cell["process_birth"]:
                    cell["state"] = "running"
                    cell["process"] = "alive"
                elif current_birth:
                    cell["state"] = "identity-mismatch"
                    cell["process"] = "unverified"
                else:
                    cell["state"] = "exited"
                    cell["process"] = "exited"
            cells[cell["id"]] = cell
        return cells

    def _sync_cells(self) -> None:
        """Refresh persistent cell state while preserving local process handles."""
        with self._lock:
            self._cells = self._load_cells()

    def _save_cells(self) -> None:
        with self._lock:
            self._registry_generation += 1
            payload = {
                "schema_version": CELL_REGISTRY_SCHEMA_VERSION,
                "generation": self._registry_generation,
                "updated_at": int(time.time() * 1000),
                "cells": list(self._cells.values()),
            }
            temporary = self.cells_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            os.chmod(temporary, 0o600)
            temporary.replace(self.cells_file)

    @staticmethod
    def _record_lifecycle(cell: dict[str, Any], event: str, detail: str = "") -> None:
        now = int(time.time() * 1000)
        events = cell.setdefault("lifecycle", [])
        if not isinstance(events, list):
            events = []
            cell["lifecycle"] = events
        events.append({"event": event, "at": now, "detail": detail})
        del events[:-CELL_REGISTRY_EVENT_LIMIT]
        cell["updated_at"] = now

    @staticmethod
    def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
        result: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            try:
                resolved = path.expanduser().resolve()
            except OSError:
                continue
            key = str(resolved)
            if key not in seen:
                seen.add(key)
                result.append(resolved)
        return result

    def _save_roots(self) -> None:
        temporary = self.roots_file.with_suffix(".tmp")
        payload = {
            "schema_version": VERSION_REGISTRY_SCHEMA_VERSION,
            "updated_at": int(time.time() * 1000),
            "roots": [
                {
                    "id": record["id"],
                    "path": str(record["path"]),
                    "added_at": record["added_at"],
                    "source": record.get("source", "manual"),
                    "launch": _version_launch_settings(record.get("launch")),
                }
                for record in self._saved_roots.values()
            ],
        }
        temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(self.roots_file)

    def add_scan_roots(self, roots: Iterable[str]) -> dict[str, Any]:
        additions: list[Path] = []
        for raw in roots:
            if not isinstance(raw, str) or not raw.strip():
                raise LauncherError("Each scan root must be a non-empty path")
            path = Path(raw).expanduser().resolve()
            if not path.is_dir():
                raise LauncherError(f"Scan root is not a directory: {raw}")
            additions.append(path)
        with self._mutation_lock, self._roots_file_lock():
            self._saved_roots = self._load_roots()
            now = int(time.time() * 1000)
            for path in additions:
                record_id = _version_id(path)
                previous = self._saved_roots.get(record_id)
                self._saved_roots[record_id] = {
                    "id": record_id,
                    "path": path,
                    "added_at": previous["added_at"] if previous else now,
                    "source": "manual",
                    "launch": _version_launch_settings(previous.get("launch") if previous else None),
                }
            self._save_roots()
        return self.scan()

    def update_saved_version(self, version_id: str, raw: dict[str, Any]) -> dict[str, Any]:
        """Persist the limited launch preferences exposed by the simple UI."""
        if not isinstance(version_id, str) or not re.fullmatch(r"version_[a-f0-9]{12}", version_id):
            raise LauncherError("Choose a valid saved local-version ID")
        if not isinstance(raw, dict):
            raise LauncherError("Launch settings must be a JSON object")
        unknown = set(raw) - {"open_browser", "gpu", "resources"}
        if unknown:
            raise LauncherError("Only open-browser and GPU preferences can be changed")
        if "open_browser" in raw and not isinstance(raw["open_browser"], bool):
            raise LauncherError("Open-browser preference must be true or false")
        if "resources" in raw and not isinstance(raw["resources"], dict):
            raise LauncherError("Resource preferences must be a JSON object")
        with self._mutation_lock, self._roots_file_lock():
            self._saved_roots = self._load_roots()
            record = self._saved_roots.get(version_id)
            if not record:
                raise LauncherError("Unknown saved local version")
            current = _version_launch_settings(record.get("launch"))
            resources = raw.get("resources") if isinstance(raw.get("resources"), dict) else {}
            requested_gpu_value = raw["gpu"] if "gpu" in raw else resources.get(
                "gpu", current["resources"]["gpu"]
            )
            update = {
                "open_browser": raw.get("open_browser", current["open_browser"]),
                "gpu": requested_gpu_value,
            }
            requested_gpu = str(update["gpu"]).strip().lower()
            if requested_gpu not in {"none", "allocated"}:
                raise LauncherError("GPU preference must be 'none' or 'allocated'")
            record["launch"] = _version_launch_settings(update)
            self._save_roots()
        return self.scan()

    def remove_saved_version(self, version_id: str) -> dict[str, Any]:
        """Forget one scan root without modifying its source directory."""
        if not isinstance(version_id, str) or not re.fullmatch(r"version_[a-f0-9]{12}", version_id):
            raise LauncherError("Choose a valid saved local-version ID")
        with self._mutation_lock, self._roots_file_lock():
            self._saved_roots = self._load_roots()
            if version_id not in self._saved_roots:
                raise LauncherError("Unknown saved local version")
            del self._saved_roots[version_id]
            self._save_roots()
        return self.scan()

    def _tree_record(self, root: Path, executable: Path, package: dict[str, Any], kind: str) -> dict[str, Any]:
        git, remote = _git_metadata(root)
        trust = _trust_for(root, remote)
        node = shutil.which("node") if executable.suffix in {".js", ".ts"} else None
        launchability = "ready"
        if executable.suffix == ".ts":
            launchability = "needs-build"
        elif not os.access(executable, os.R_OK) or (executable.suffix != ".js" and not os.access(executable, os.X_OK)):
            launchability = "not-executable"
        elif trust != "foreign" and executable.suffix == ".js" and not node:
            launchability = "missing-node"
        elif trust == "foreign":
            launchability = "sandbox-testable" if self.sandbox.ready else "sandbox-unavailable"
        name = str(package.get("name") or root.name or "dsh")
        version = str(package.get("version") or "unknown")
        record = {
            "id": _tree_id(root),
            "name": name,
            "short": re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "dsh",
            "kind": kind,
            "version": version,
            "path": _display_path(root),
            "real_path": str(root.resolve()),
            "exe": _display_path(executable),
            "real_exe": str(executable.resolve()),
            "executable_sha256": _file_sha256(executable),
            "node": (node + " · detected") if node else ("bundled" if executable.suffix != ".js" else "—"),
            "real_node": node,
            "git": git,
            "trust": trust,
            "launchability": launchability,
            "evidence": ["recognized CLI artifact", "package metadata" if package else "PATH executable"],
        }
        if trust == "foreign":
            previous = self._sandbox_results.get(self._sandbox_key(record))
            if previous:
                record["sandbox_test"] = self._sandbox_summary(previous)
                record["launchability"] = "sandbox-tested" if previous.get("status") == "passed" else "sandbox-test-failed"
        return record

    def scan(self) -> dict[str, Any]:
        with self._roots_file_lock():
            self._saved_roots = self._load_roots()
            self._scan_roots = self._dedupe_paths([
                *self._configured_scan_roots,
                *(record["path"] for record in self._saved_roots.values()),
            ])
        trees: dict[str, dict[str, Any]] = {}
        gaps: list[str] = []
        path_dsh = shutil.which("dsh")
        if path_dsh:
            executable = Path(path_dsh).resolve()
            root = executable.parent
            package = {}
            for parent in [executable.parent, *list(executable.parents)[:3]]:
                candidate_package = _read_json(parent / "package.json")
                if _is_harness_package_name(candidate_package.get("name")):
                    root, package = parent, candidate_package
                    break
            record = self._tree_record(root, executable, package, "npm" if package else "bin")
            trees[record["id"]] = record
        seen_executables = {tree["real_exe"] for tree in trees.values()}
        for root in self._scan_roots:
            if not root.exists():
                gaps.append(f"{_display_path(root)} · missing")
                continue
            if not root.is_dir() or not os.access(root, os.R_OK | os.X_OK):
                gaps.append(f"{_display_path(root)} · unreadable")
                continue
            found = False
            for candidate in _candidate_dirs(root):
                match = _source_candidate(candidate)
                if not match:
                    continue
                executable, package = match
                if str(executable.resolve()) in seen_executables:
                    found = True
                    continue
                record = self._tree_record(candidate, executable, package, "source")
                trees[record["id"]] = record
                seen_executables.add(record["real_exe"])
                found = True
            if not found:
                gaps.append(f"{_display_path(root)} · no strong DSH signature")
        discovered_in_managed_directory = []
        for tree in trees.values():
            try:
                Path(tree["real_path"]).resolve().relative_to(self.versions_directory)
            except (KeyError, OSError, ValueError):
                continue
            discovered_in_managed_directory.append(Path(tree["real_path"]).resolve())
        if discovered_in_managed_directory:
            with self._roots_file_lock():
                self._saved_roots = self._load_roots()
                changed = False
                now = int(time.time() * 1000)
                for path in discovered_in_managed_directory:
                    record_id = _version_id(path)
                    if record_id in self._saved_roots:
                        continue
                    self._saved_roots[record_id] = {
                        "id": record_id,
                        "path": path,
                        "added_at": now,
                        "source": "auto",
                        "launch": _version_launch_settings(),
                    }
                    changed = True
                if changed:
                    self._save_roots()
        with self._lock:
            self._trees = trees
            self._coverage_gaps = gaps
        return self.status()

    def _public_tree(self, tree: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in tree.items() if not k.startswith("real_")}

    def _public_saved_versions(self) -> list[dict[str, Any]]:
        versions: list[dict[str, Any]] = []
        trees = list(self._trees.values())
        for record in self._saved_roots.values():
            root = record["path"]
            matched: list[dict[str, Any]] = []
            for tree in trees:
                try:
                    Path(tree["real_path"]).resolve().relative_to(root.resolve())
                except (KeyError, OSError, ValueError):
                    continue
                matched.append(tree)
            exact = next(
                (tree for tree in matched if Path(tree["real_path"]).resolve() == root.resolve()),
                None,
            )
            primary = exact or (matched[0] if matched else None)
            if not root.exists():
                state = "missing"
            elif not root.is_dir() or not os.access(root, os.R_OK | os.X_OK):
                state = "unreadable"
            elif primary and primary.get("launchability") == "ready":
                state = "ready"
            elif primary:
                state = str(primary.get("launchability") or "detected")
            else:
                state = "no-harness-found"
            versions.append({
                "id": record["id"],
                "path": _display_path(root),
                "added_at": record["added_at"],
                "source": record.get("source", "manual"),
                "launch": _version_launch_settings(record.get("launch")),
                "state": state,
                "tree_ids": [tree["id"] for tree in matched],
                "primary_tree": self._public_tree(primary) if primary else None,
            })
        return versions

    def suggested_port(self) -> int:
        with self._lock:
            managed = {c.get("port") for c in self._cells.values() if c.get("state") not in {"stopped", "exited"}}
        protected = self.protected_ports | {p for p in managed if isinstance(p, int)}
        for port in range(3100, 65536):
            if port not in protected and _port_available(port):
                return port
        raise LauncherError("No free loopback port is available")

    def _refresh_cell(self, cell: dict[str, Any]) -> None:
        previous_state = cell.get("state")
        process = self._processes.get(cell["id"])
        if not process:
            if cell.get("state") in {"stopped", "exited"}:
                return
            current_birth = _process_birth(cell["pid"])
            if current_birth == cell.get("process_birth"):
                cell["process"] = "alive"
                cell["state"] = "running"
            elif current_birth:
                cell["state"] = "identity-mismatch"
                cell["process"] = "unverified"
                if previous_state != cell["state"]:
                    self._record_lifecycle(cell, "identity-mismatch", "PID exists but process-start identity changed")
                    self._save_cells()
                return
            else:
                cell["state"] = "exited"
                cell["process"] = "exited"
                cell["http"] = "n/a" if not cell.get("port") else "unreachable"
                if previous_state != cell["state"]:
                    self._record_lifecycle(cell, "exited", "process no longer exists")
                self._save_cells()
                return
        else:
            code = process.poll()
            if code is not None:
                if cell["state"] not in {"stopped", "stopping"}:
                    cell["state"] = "exited"
                cell["returncode"] = code
                cell["process"] = "exited"
                cell["http"] = "n/a" if not cell.get("port") else "unreachable"
                if previous_state != cell["state"]:
                    self._record_lifecycle(cell, "exited", f"return code {code}")
                self._save_cells()
                return
            if _process_birth(process.pid) != cell.get("process_birth"):
                cell["state"] = "identity-mismatch"
                cell["process"] = "unverified"
                if previous_state != cell["state"]:
                    self._record_lifecycle(cell, "identity-mismatch", "owned process identity changed")
                    self._save_cells()
                return
            cell["process"] = "alive"
            cell["state"] = "running"
        if cell.get("port"):
            if not cell.get("open_url"):
                try:
                    log_tail = Path(cell["log_path"]).read_text(encoding="utf-8", errors="replace")[-65536:]
                except OSError:
                    log_tail = ""
                urls = re.findall(r"dsh web:\s+(https?://[^\s]+)", log_tail)
                if urls:
                    candidate = urls[-1].rstrip(".,;)")
                    parsed = urlsplit(candidate)
                    if parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"} and parsed.port == cell["port"]:
                        cell["open_url"] = candidate
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{cell['port']}/", timeout=0.2) as response:
                    cell["http"] = str(response.status)
            except urllib.error.HTTPError as error:
                cell["http"] = str(error.code)
            except (OSError, urllib.error.URLError):
                cell["http"] = "pending"
        else:
            cell["http"] = "n/a"

    def _activity_state(self, cell: dict[str, Any]) -> str:
        """Map process and recent log evidence to the fleet's small state vocabulary."""
        if cell.get("process") != "alive" or cell.get("state") in {"stopped", "exited", "identity-mismatch"}:
            return "exited"
        if cell.get("blocked") is True:
            return "blocked"
        try:
            age = time.time() - Path(cell["log_path"]).stat().st_mtime
        except (KeyError, OSError):
            age = float("inf")
        return "working" if cell.get("state") == "starting" or age < 15 else "idle"

    def _public_cell(self, cell: dict[str, Any]) -> dict[str, Any]:
        self._refresh_cell(cell)
        public = {k: v for k, v in cell.items() if k not in {"launch_spec", "log_path", "process_birth", "real_home", "real_workspace", "open_url"}}
        public["open_ready"] = bool(cell.get("open_url"))
        public["agent_state"] = self._activity_state(cell)
        public["state_source"] = "process identity + recent log activity"
        public["recent_logs"] = [line["msg"] for line in self.logs(cell["id"], limit=3)]
        return public

    def status(self) -> dict[str, Any]:
        with self._mutation_lock, self._registry_file_lock():
            self._sync_cells()
            with self._lock:
                cells = [self._public_cell(cell) for cell in self._cells.values()]
                trees = [self._public_tree(tree) for tree in self._trees.values()]
        return {
            "api_version": "v1",
            "mode": "live-local-sidecar",
            "trees": trees,
            "cells": cells,
            "scan_roots": [_display_path(p) for p in self._scan_roots],
            "saved_versions": self._public_saved_versions(),
            "versions_directory": {
                "path": _display_path(self.versions_directory),
                "available": self.versions_directory.is_dir(),
                "auto_scan": True,
            },
            "coverage_gaps": list(self._coverage_gaps),
            "suggested_port": self.suggested_port(),
            "credentials": [{"name": name, "present": bool(os.environ.get(name))} for name in SECRET_NAMES],
            "sandbox": self.sandbox.status(),
            "registry": {
                "schema_version": CELL_REGISTRY_SCHEMA_VERSION,
                "generation": self._registry_generation,
                "path": _display_path(self.cells_file),
                "cross_process_lock": True,
            },
            "capabilities": self.capabilities(),
        }

    def capabilities(self) -> dict[str, dict[str, Any]]:
        """Describe implemented behavior without implying unsupported adapters."""
        sandbox_status = self.sandbox.status()
        sandbox_ready = bool(sandbox_status.get("ready"))
        return {
            "persistent_registry": {
                "available": True,
                "schema_version": CELL_REGISTRY_SCHEMA_VERSION,
                "cross_process_lock": True,
            },
            "saved_local_versions": {
                "available": True,
                "schema_version": VERSION_REGISTRY_SCHEMA_VERSION,
                "cross_process_lock": True,
                "source_directories_mutated": False,
                "auto_discovery_directory": _display_path(self.versions_directory),
                "one_click_presets": True,
            },
            "parallel_local_cells": {
                "available": sandbox_ready,
                "backend": "apptainer-cell-v1",
                "security_boundary": True,
                "reason": sandbox_status.get("reason"),
            },
            "runtime_logs": {"available": True, "source": "process stdout/stderr"},
            "artifacts": {"available": True, "scope": "managed workspace files"},
            "sandboxed_cells": {
                "available": sandbox_ready,
                "backend": "apptainer-cell-v1",
                "reason": sandbox_status.get("reason"),
            },
            "prompt_delivery": {
                "available": False,
                "reason": "No verified live Harness prompt transport is configured.",
            },
            "session_transcript": {
                "available": False,
                "reason": "Runtime stdout is available, but no version-independent Harness session adapter is configured.",
            },
        }

    def cell(self, cell_id: str) -> dict[str, Any]:
        """Return one current persistent cell record through the public contract."""
        with self._mutation_lock, self._registry_file_lock():
            self._sync_cells()
            with self._lock:
                cell = self._cells.get(cell_id)
            if not cell:
                raise LauncherError("Unknown cell")
            return self._public_cell(cell)

    def sandbox_test(self, tree_id: str) -> dict[str, Any]:
        """Execute a bounded CLI help probe in a networkless pinned container."""
        with self._mutation_lock:
            # Refresh Git and filesystem evidence immediately before executing a
            # captured CLI. Persisted results are tied to this observed revision.
            self.scan()
            with self._lock:
                tree = self._trees.get(tree_id)
            if not tree:
                raise LauncherError("Select a detected DSH tree")
            if tree.get("trust") != "foreign":
                raise LauncherError("Sandbox testing is reserved for foreign/community trees")
            git = tree.get("git") or {}
            if not git or git.get("sha") in {None, "", "unknown"} or git.get("dirty") is not False:
                raise LauncherError("Community tree must have a recorded Git revision with no tracked changes before sandbox testing")
            if tree.get("launchability") in {"needs-build", "not-executable"}:
                raise LauncherError(f"Tree cannot be sandbox-tested yet: {tree['launchability']}")
            try:
                result = self.sandbox.test_tree(tree)
            except SandboxError as error:
                raise LauncherError(str(error)) from error
            output = str(result.get("output") or "")
            for name in SECRET_NAMES:
                if value := os.environ.get(name):
                    output = output.replace(value, "<redacted>")
            result.update({
                "tree_id": tree_id,
                "revision": str((tree.get("git") or {}).get("sha") or "unknown"),
                "tested_at": int(time.time() * 1000),
                "output": output,
                "verdict": "Capability evidence only; this is not a security or compatibility guarantee.",
            })
            key = self._sandbox_key(tree)
            self._sandbox_results[key] = result
            self._save_sandbox_results()
            tree["sandbox_test"] = self._sandbox_summary(result)
            tree["launchability"] = "sandbox-tested" if result.get("status") == "passed" else "sandbox-test-failed"
            return dict(result)

    def _tree(self, tree_id: str) -> dict[str, Any]:
        with self._lock:
            tree = self._trees.get(tree_id)
        if not tree:
            raise LauncherError("Select a detected DSH tree")
        if tree["trust"] == "foreign":
            raise LauncherError("Foreign trees may be capability-tested but are not promoted for complete cell execution")
        if tree["launchability"] != "ready":
            raise LauncherError(f"Tree is not launchable: {tree['launchability']}")
        return tree

    def install_package(
        self,
        *,
        tree_id: str,
        envelope: dict[str, Any],
        trust_root: dict[str, Any],
        receipt_path: str | Path,
        install_root: str | Path,
        profile: str = "web",
        timeout_seconds: int = 900,
    ) -> dict[str, Any]:
        """Install a signed package into a new sandbox-owned profile."""

        from .installation import install_in_sandbox

        tree = self._tree(tree_id)
        try:
            return install_in_sandbox(
                envelope,
                trust_root,
                receipt_path,
                tree=tree,
                sandbox=self.sandbox,
                install_root=install_root,
                profile=profile,
                timeout_seconds=timeout_seconds,
            )
        except (PackageError, SandboxError) as error:
            raise LauncherError(str(error)) from error

    def _normalize_spec(self, raw: dict[str, Any]) -> dict[str, Any]:
        tree = self._tree(str(raw.get("tree_id", "")))
        if not self.sandbox.ready:
            raise LauncherError(str(self.sandbox.status().get("reason") or "Apptainer cell runner is unavailable"))
        surface = str(raw.get("surface", "web"))
        if surface not in {"web", "headless"}:
            raise LauncherError("This launcher alpha supports the web and headless surfaces")
        profile = str(raw.get("profile", "tui-min"))
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", profile):
            raise LauncherError("Custom profile contains unsupported characters")
        port = None
        if surface != "headless":
            requested_port = raw.get("port")
            if requested_port in {None, "", "auto"}:
                port = self.suggested_port()
            else:
                try:
                    port = int(requested_port)
                except (TypeError, ValueError):
                    raise LauncherError("Choose a numeric port or use automatic assignment") from None
            if port in self.protected_ports:
                raise LauncherError(f"Port {port} is protected and cannot be used by a cell")
            with self._lock:
                managed = next((c for c in self._cells.values() if c.get("port") == port and c.get("state") not in {"stopped", "exited"}), None)
            if managed:
                raise LauncherError(f"Port {port} belongs to managed cell {managed['name']}")
            if not _port_available(port):
                raise LauncherError(f"Port {port} is occupied by an unmanaged process; DSH Forge will not stop it")
        home_mode = str(raw.get("home_mode", "fresh"))
        if home_mode not in {"fresh", "clone"}:
            raise LauncherError("Apptainer cells require a managed fresh or cloned home; the host DSH home is never mounted")
        workspace_raw = str(raw.get("workspace") or "managed").strip()
        workspace_mode = workspace_raw if workspace_raw in {"none", "managed", "clone"} else "existing"
        workspace = Path(workspace_raw).expanduser().resolve() if workspace_mode == "existing" else None
        if workspace and not workspace.is_dir():
            raise LauncherError("Workspace must be an existing directory or 'none'")
        if workspace_mode == "existing":
            raise LauncherError("Apptainer cells require a unique managed or cloned workspace; host workspaces are not mounted writable")
        if workspace_mode == "none":
            workspace_mode = "managed"
            workspace_raw = "managed"
        clone_source_raw = str(raw.get("clone_source") or "~/.dsh")
        clone_source = Path(clone_source_raw).expanduser().resolve()
        task = str(raw.get("task") or "").strip()
        if surface == "headless" and not task:
            raise LauncherError("Enter a task for the one-shot headless surface")
        if len(task) > 20000:
            raise LauncherError("Headless task exceeds the 20,000-character launcher limit")
        resources_raw = raw.get("resources") if isinstance(raw.get("resources"), dict) else {}
        gpu_label = str(resources_raw.get("gpu") or "none").strip().lower()
        if gpu_label not in {"none", "allocated", "inherit allocation"}:
            raise LauncherError("GPU mode must be 'none' or 'allocated'")
        gpu = gpu_label in {"allocated", "inherit allocation"}
        network = str(raw.get("network") or ("host" if surface == "web" else "none")).strip().lower()
        if network not in {"none", "host"}:
            raise LauncherError("Cell network must be 'none' or 'host'")
        if surface == "web" and network != "host":
            raise LauncherError("Web cells require host networking for their loopback port; use headless for a networkless cell")
        limits = self.sandbox.status().get("resource_limits") or {}
        resources = {
            "cpu": str(limits.get("cpus") or "unknown")[:32],
            "gpu": "allocated" if gpu else "none",
            "ram": str(limits.get("memory") or "unknown")[:32],
            "pids": limits.get("pids"),
            "wall_seconds": limits.get("wall_seconds"),
            "enforced": True,
            "note": "Apptainer limits accepted by the runtime; the surrounding Slurm allocation remains authoritative.",
        }
        for value in (resources["cpu"], resources["gpu"], resources["ram"]):
            if not re.fullmatch(r"[A-Za-z0-9 ._+:/-]{1,32}", value):
                raise LauncherError("Resource labels contain unsupported characters")
        return {
            "tree": tree,
            "tree_id": tree["id"],
            "surface": surface,
            "profile": profile,
            "port": port,
            "open_browser": bool(raw.get("open_browser", True)),
            "home_mode": home_mode,
            "clone_source": str(clone_source),
            "workspace": str(workspace) if workspace else workspace_mode,
            "workspace_mode": workspace_mode,
            "workspace_clone_source": str(raw.get("workspace_clone_source") or ""),
            "task": task,
            "include_sessions": bool(raw.get("include_sessions", False)),
            "resources": resources,
            "network": network,
            "gpu": gpu,
        }

    def _home_preview(self, spec: dict[str, Any], cell_id: str = "<generated>") -> str:
        target = self.cells_root / cell_id / "home"
        if spec["home_mode"] == "clone":
            return f"{_display_path(target)} (safe clone of {_display_path(Path(spec['clone_source']))})"
        return _display_path(target) + " (fresh empty)"

    def preview(self, raw: dict[str, Any]) -> dict[str, Any]:
        spec = self._normalize_spec(raw)
        preview_id = "cell_<generated>"
        home = self.cells_root / preview_id / "home"
        workspace = self.cells_root / preview_id / "workspace"
        try:
            plan = self.sandbox.cell_plan(
                tree=spec["tree"], home=home, workspace=workspace,
                surface=spec["surface"], task=spec["task"], port=spec["port"],
                profile=spec["profile"], network=spec["network"], gpu=spec["gpu"],
                validate_paths=False,
            )
        except SandboxError as error:
            raise LauncherError(str(error)) from error
        return {
            "tree": self._public_tree(spec["tree"]),
            "argv": plan["argv"],
            "cwd": "/workspace (inside Apptainer)",
            "home": self._home_preview(spec),
            "home_mode": spec["home_mode"],
            "workspace": self._workspace_preview(spec),
            "resources": plan["resources"],
            "network": plan["network"],
            "environment_keys": sorted(plan["environment"]),
            "credential_keys": [],
            "notes": [
                "No repository code was executed during discovery.",
                "The captured source is mounted read-only in a pinned Apptainer SIF.",
                "Home and workspace are unique writable mounts; host home and working directory stay hidden.",
                "No launcher API keys or credentials are forwarded.",
                "Host network mode permits outbound traffic; networkless headless cells use a separate network namespace.",
                "Loader health is reported as not observed until an adapter exists.",
            ],
        }

    def _workspace_preview(self, spec: dict[str, Any], cell_id: str = "<generated>") -> str:
        if spec["workspace_mode"] == "managed":
            return _display_path(self.cells_root / cell_id / "workspace") + " (managed empty)"
        if spec["workspace_mode"] == "clone":
            return _display_path(self.cells_root / cell_id / "workspace") + " (session clone)"
        return _display_path(Path(spec["workspace"])) if spec["workspace_mode"] == "existing" else "none"

    def _prepare_home(self, spec: dict[str, Any], cell_id: str) -> tuple[Path, str]:
        target = self.cells_root / cell_id / "home"
        target.parent.mkdir(parents=True, exist_ok=False, mode=0o700)
        if spec["home_mode"] == "fresh":
            target.mkdir(mode=0o700)
            return target, "fresh empty"
        source = Path(spec["clone_source"])
        if not source.is_dir():
            raise LauncherError("Clone source is not an existing directory")

        def ignore(directory: str, names: list[str]) -> set[str]:
            ignored = set()
            for name in names:
                lower = name.lower()
                if (
                    (Path(directory) / name).is_symlink()
                    or (lower in CLONE_EXCLUDES and not (spec["include_sessions"] and lower in {"session", "sessions"}))
                    or lower.endswith((".lock", ".pid", ".sock"))
                    or lower.startswith((".env", "credential", "secret"))
                ):
                    ignored.add(name)
            return ignored

        shutil.copytree(source, target, symlinks=False, ignore=ignore)
        os.chmod(target, 0o700)
        return target, "cloned home"

    def _prepare_workspace(self, spec: dict[str, Any], cell_id: str) -> tuple[Path | None, str]:
        mode = spec["workspace_mode"]
        if mode == "none":
            return None, "none"
        target = self.cells_root / cell_id / "workspace"
        if mode == "managed":
            target.mkdir(mode=0o700)
            return target, "managed empty"
        source = Path(spec["workspace_clone_source"])
        if not source.is_dir():
            raise LauncherError("Workspace clone source is not an existing directory")

        def ignore(_directory: str, names: list[str]) -> set[str]:
            return {name for name in names if name in {".git", "node_modules", ".cache"} or (Path(_directory) / name).is_symlink()}

        shutil.copytree(source, target, symlinks=False, ignore=ignore)
        os.chmod(target, 0o700)
        return target, "cloned workspace"

    def launch(self, raw: dict[str, Any]) -> dict[str, Any]:
        with self._mutation_lock, self._registry_file_lock():
            self._sync_cells()
            return self._launch(raw)

    def _launch(self, raw: dict[str, Any]) -> dict[str, Any]:
        spec = self._normalize_spec(raw)
        cell_id = "cell_" + uuid.uuid4().hex[:10]
        home, isolation = self._prepare_home(spec, cell_id)
        workspace, workspace_isolation = self._prepare_workspace(spec, cell_id)
        if not workspace:
            raise LauncherError("Apptainer cell workspace creation failed closed")
        try:
            plan = self.sandbox.cell_plan(
                tree=spec["tree"], home=home, workspace=workspace,
                surface=spec["surface"], task=spec["task"], port=spec["port"],
                profile=spec["profile"], network=spec["network"], gpu=spec["gpu"],
            )
        except SandboxError as error:
            raise LauncherError(str(error)) from error
        argv = plan["argv"]
        env = plan["environment"]
        log_path = self.logs_root / f"{cell_id}.log"
        log_handle = log_path.open("ab", buffering=0)
        try:
            process = subprocess.Popen(
                argv,
                cwd=str(self.state_root),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as error:
            log_handle.close()
            raise LauncherError(f"Could not start the selected executable: {error}") from error
        finally:
            log_handle.close()
        birth = None
        for _ in range(10):
            birth = _process_birth(process.pid)
            if birth or process.poll() is not None:
                break
            time.sleep(0.02)
        if not birth:
            try:
                process.terminate()
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)
            except OSError:
                pass
            raise LauncherError("The process started, but its start identity could not be recorded safely")
        name = f"{spec['tree']['short']}-{spec['surface']}" + (f"-{spec['port']}" if spec["port"] else "")
        cell = {
            "id": cell_id,
            "name": name,
            "state": "starting",
            "treeId": spec["tree_id"],
            "version": spec["tree"]["version"],
            "commit": (spec["tree"].get("git") or {}).get("sha") or "package pin",
            "surface": spec["surface"],
            "port": spec["port"],
            "pid": process.pid,
            "procStart": birth,
            "process_birth": birth,
            "started": int(time.time() * 1000),
            "home": _display_path(home),
            "real_home": str(home),
            "isolation": isolation,
            "workspace": _display_path(workspace) if workspace else "none",
            "real_workspace": str(workspace) if workspace else "",
            "workspace_isolation": workspace_isolation,
            "resources": plan["resources"],
            "http": "pending" if spec["port"] else "n/a",
            "loader": "not observed",
            "process": "alive",
            "execution_backend": "apptainer-cell-v1",
            "sandboxed": True,
            "network": plan["network"],
            "secrets_forwarded": plan["secrets_forwarded"],
            "container_identity": {
                "runtime": "apptainer",
                "image_sha256": plan["image_sha256"],
                "executable_sha256": plan["executable_sha256"],
                "command_sha256": plan["command_sha256"],
                "supervisor": "coreutils-timeout",
            },
            "parent_cell_id": str(raw.get("parent_cell_id") or "") or None,
            "lineage_action": str(raw.get("lineage_action") or "start"),
            "created_at": int(time.time() * 1000),
            "updated_at": int(time.time() * 1000),
            "lifecycle": [],
            "log_path": str(log_path),
            "launch_spec": {
                "tree_id": spec["tree_id"], "surface": spec["surface"], "profile": spec["profile"],
                "task": spec["task"], "port": spec["port"], "open_browser": spec["open_browser"],
                "home_mode": spec["home_mode"], "clone_source": spec["clone_source"],
                "workspace": spec["workspace"], "resources": spec["resources"],
                "network": spec["network"],
            },
        }
        self._record_lifecycle(cell, "started", "fail-closed Apptainer cell process created")
        with self._lock:
            self._processes[cell_id] = process
            self._cells[cell_id] = cell
            self._save_cells()
        return self._public_cell(cell)

    def _owned_live_process(self, cell_id: str) -> tuple[dict[str, Any], subprocess.Popen[bytes] | None]:
        with self._lock:
            cell = self._cells.get(cell_id)
            process = self._processes.get(cell_id)
        if not cell:
            raise LauncherError("Unknown cell")
        if process and process.poll() is not None:
            raise LauncherError("Cell process is no longer running")
        pid = process.pid if process else cell["pid"]
        if pid != cell["pid"] or _process_birth(pid) != cell["process_birth"]:
            raise LauncherError("Process identity changed; refusing to signal it")
        return cell, process

    def stop(self, cell_id: str, timeout: float = 3.0) -> dict[str, Any]:
        with self._mutation_lock, self._registry_file_lock():
            self._sync_cells()
            return self._stop(cell_id, timeout)

    def _stop(self, cell_id: str, timeout: float) -> dict[str, Any]:
        with self._lock:
            existing = self._cells.get(cell_id)
        if not existing:
            raise LauncherError("Unknown cell")
        if existing.get("state") in {"stopped", "exited"}:
            return self._public_cell(existing)
        cell, process = self._owned_live_process(cell_id)
        pid = process.pid if process else cell["pid"]
        cell["state"] = "stopping"
        self._record_lifecycle(cell, "stopping", "SIGTERM requested")
        self._save_cells()
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError as error:
            raise LauncherError(f"Could not signal the verified process group: {error}") from error
        if process:
            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                if _process_birth(process.pid) != cell["process_birth"]:
                    raise LauncherError("Process identity changed while stopping; refusing SIGKILL")
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=2)
            returncode = process.returncode
        else:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline and _process_birth(cell["pid"]) == cell["process_birth"]:
                time.sleep(0.05)
            if _process_birth(cell["pid"]) == cell["process_birth"]:
                os.killpg(cell["pid"], signal.SIGKILL)
            returncode = None
        cell["state"] = "stopped"
        cell["process"] = "exited"
        cell["returncode"] = returncode
        self._record_lifecycle(cell, "stopped", "verified process group stopped")
        self._save_cells()
        return self._public_cell(cell)

    def restart(self, cell_id: str) -> dict[str, Any]:
        with self._mutation_lock, self._registry_file_lock():
            self._sync_cells()
            with self._lock:
                cell = self._cells.get(cell_id)
            if not cell:
                raise LauncherError("Unknown cell")
            raw = dict(cell["launch_spec"])
            if cell["state"] not in {"stopped", "exited"}:
                self._stop(cell_id, 3.0)
            raw.update({
                "port": "auto" if raw.get("port") else None,
                "home_mode": "clone",
                "clone_source": cell["real_home"],
                "include_sessions": True,
                "parent_cell_id": cell_id,
                "lineage_action": "restart",
            })
            if cell.get("real_workspace") and cell.get("workspace_isolation") != "shared existing":
                raw.update({"workspace": "clone", "workspace_clone_source": cell["real_workspace"]})
            return self._launch(raw)

    def clone(self, cell_id: str) -> dict[str, Any]:
        """Start a parallel cell from a sanitized snapshot of a managed session."""
        with self._mutation_lock, self._registry_file_lock():
            self._sync_cells()
            with self._lock:
                cell = self._cells.get(cell_id)
            if not cell:
                raise LauncherError("Unknown cell")
            raw = dict(cell["launch_spec"])
            raw.update({
                "port": "auto" if raw.get("port") else None,
                "home_mode": "clone",
                "clone_source": cell["real_home"],
                "include_sessions": True,
                "parent_cell_id": cell_id,
                "lineage_action": "clone",
            })
            if cell.get("real_workspace") and cell.get("workspace_isolation") != "shared existing":
                raw.update({"workspace": "clone", "workspace_clone_source": cell["real_workspace"]})
            return self._launch(raw)

    def logs(self, cell_id: str, limit: int = 500) -> list[dict[str, str]]:
        with self._lock:
            cell = self._cells.get(cell_id)
        if not cell:
            raise LauncherError("Unknown cell")
        try:
            lines = Path(cell["log_path"]).read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, min(limit, 500)) :]
        except OSError:
            lines = []
        secret_values = [value for name in SECRET_NAMES if (value := os.environ.get(name))]
        result = []
        for raw in lines:
            for secret in secret_values:
                raw = raw.replace(secret, "<redacted>")
            raw = re.sub(r"(dsh web:\s+)https?://\S+", r"\1<authenticated URL redacted; use Open>", raw)
            result.append({"t": "", "level": "process", "msg": raw, "color": "oklch(0.72 0.01 255)"})
        return result

    def open_url(self, cell_id: str) -> str:
        with self._mutation_lock, self._registry_file_lock():
            self._sync_cells()
            with self._lock:
                cell = self._cells.get(cell_id)
            if not cell:
                raise LauncherError("Unknown cell")
            self._refresh_cell(cell)
            value = cell.get("open_url")
            if not value:
                raise LauncherError("The authenticated DSH Web URL is not ready yet; check logs and try again")
            return str(value)

    def artifacts(self, cell_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            cell = self._cells.get(cell_id)
        if not cell:
            raise LauncherError("Unknown cell")
        root_raw = cell.get("real_workspace")
        if not root_raw or cell.get("workspace_isolation") == "shared existing":
            return []
        root = Path(root_raw)
        if not root.is_dir():
            return []
        results = []
        for path in sorted(root.rglob("*")):
            if len(results) >= max(1, min(limit, 100)):
                break
            if path.is_file() and not path.is_symlink():
                try:
                    stat = path.stat()
                    results.append({"path": str(path.relative_to(root)), "bytes": stat.st_size, "modified": int(stat.st_mtime * 1000)})
                except OSError:
                    continue
        return results

    def shutdown(self) -> None:
        """Stop only processes still owned and identity-verified by this instance."""
        with self._lock:
            ids = [cell_id for cell_id, cell in self._cells.items() if cell.get("state") not in {"stopped", "exited", "identity-mismatch"}]
        for cell_id in ids:
            try:
                self.stop(cell_id, timeout=1)
            except LauncherError:
                pass
