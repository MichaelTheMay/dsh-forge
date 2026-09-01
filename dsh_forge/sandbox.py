"""Fail-closed Apptainer planning and capability checks for foreign DSH code."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


Runner = Callable[..., subprocess.CompletedProcess[str]]


class SandboxError(Exception):
    """A sandbox configuration, capability, or execution failure."""


@dataclass(frozen=True)
class SandboxConfig:
    """Pinned runtime inputs and requested per-test resource limits."""

    image: Path | None = None
    image_sha256: str | None = None
    binary: str = "apptainer"
    cpus: str = "4"
    memory: str = "8G"
    pids_limit: int = 256
    timeout_seconds: int = 30

    @classmethod
    def from_values(
        cls,
        image: str | Path | None = None,
        image_sha256: str | None = None,
        binary: str = "apptainer",
        cpus: str = "4",
        memory: str = "8G",
        pids_limit: int = 256,
        timeout_seconds: int = 30,
    ) -> "SandboxConfig":
        # Keep the configured final path component intact so a symlink can be
        # rejected during inspection instead of silently followed by resolve().
        resolved_image = Path(os.path.abspath(Path(image).expanduser())) if image else None
        digest = image_sha256.strip().lower() if image_sha256 else None
        if digest and not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise SandboxError("Sandbox image SHA-256 must contain exactly 64 hexadecimal characters")
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", str(cpus)) or float(cpus) <= 0:
            raise SandboxError("Sandbox CPU limit must be a positive number")
        if not re.fullmatch(r"[1-9][0-9]*(?:[KMGTP]i?B?)?", str(memory), re.IGNORECASE):
            raise SandboxError("Sandbox memory limit must be a positive byte value such as 8G")
        if not 16 <= int(pids_limit) <= 65536:
            raise SandboxError("Sandbox PID limit must be between 16 and 65536")
        if not 1 <= int(timeout_seconds) <= 600:
            raise SandboxError("Sandbox timeout must be between 1 and 600 seconds")
        return cls(
            image=resolved_image,
            image_sha256=digest,
            binary=str(binary),
            cpus=str(cpus),
            memory=str(memory),
            pids_limit=int(pids_limit),
            timeout_seconds=int(timeout_seconds),
        )


class ApptainerSandbox:
    """Build and run networkless, pinned-image tests without inherited secrets."""

    def __init__(
        self,
        config: SandboxConfig,
        state_root: str | Path,
        runner: Runner | None = None,
        which: Callable[[str], str | None] = shutil.which,
    ):
        self.config = config
        self.state_root = Path(state_root).resolve()
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.cache_root = self.state_root / "cache"
        self.cache_root.mkdir(exist_ok=True, mode=0o700)
        self._runner = runner or subprocess.run
        self.binary = self._resolve_binary(config.binary, which)
        self.image_digest: str | None = None
        self._status = self._inspect_and_probe()

    @staticmethod
    def _resolve_binary(binary: str, which: Callable[[str], str | None]) -> str | None:
        candidate = Path(binary).expanduser()
        if candidate.is_absolute():
            return str(candidate.resolve()) if candidate.is_file() and os.access(candidate, os.X_OK) else None
        value = which(binary)
        return str(Path(value).resolve()) if value else None

    @property
    def ready(self) -> bool:
        return bool(self._status.get("ready"))

    def status(self) -> dict[str, Any]:
        return dict(self._status)

    def _base_status(self) -> dict[str, Any]:
        return {
            "mode": "apptainer-networkless-test" if self.config.image else "unavailable",
            "configured": bool(self.config.image),
            "ready": False,
            "runtime": "apptainer",
            "hostile_code_isolation": False,
            "network": "none",
            "host_home_exposed": False,
            "secrets_forwarded": False,
            "image": str(self.config.image) if self.config.image else None,
            "image_sha256": self.config.image_sha256,
            "resource_limits": {
                "cpus": self.config.cpus,
                "memory": self.config.memory,
                "pids": self.config.pids_limit,
                "probe_required": True,
            },
            "enforced": [],
            "not_enforced": ["kernel exploit immunity", "GPU access", "model/API access", "web port bridging"],
            "reason": "Configure --sandbox-image and --sandbox-image-sha256 to enable foreign-code tests.",
        }

    def _inspect_and_probe(self) -> dict[str, Any]:
        status_value = self._base_status()
        image = self.config.image
        if not image:
            return status_value
        if not self.binary:
            status_value["reason"] = "Apptainer executable was not found or is not executable."
            return status_value
        if not self.config.image_sha256:
            status_value["reason"] = "A pinned sandbox image SHA-256 is required."
            return status_value
        try:
            info = image.lstat()
        except OSError:
            status_value["reason"] = "Configured sandbox image does not exist."
            return status_value
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
            status_value["reason"] = "Sandbox image must be a regular, non-symlink SIF file."
            return status_value
        if info.st_mode & 0o222:
            status_value["reason"] = "Sandbox image must be read-only; remove every filesystem write bit."
            return status_value
        digest = self._sha256(image)
        self.image_digest = digest
        if digest != self.config.image_sha256:
            status_value["reason"] = "Sandbox image SHA-256 does not match the configured pin."
            return status_value
        try:
            with tempfile.TemporaryDirectory(prefix="probe-", dir=self.state_root) as raw:
                root = Path(raw)
                home = root / "home"
                workspace = root / "workspace"
                home.mkdir(mode=0o700)
                workspace.mkdir(mode=0o700)
                command = self.command(home=home, workspace=workspace, payload=["node", "--version"])
                completed = self._execute(command, timeout=min(15, self.config.timeout_seconds))
        except (OSError, SandboxError, subprocess.TimeoutExpired) as error:
            status_value["reason"] = f"Apptainer capability probe failed: {type(error).__name__}."
            return status_value
        if completed.returncode != 0:
            status_value["reason"] = "Apptainer capability probe rejected the required isolation or resource flags."
            status_value["probe_exit_code"] = completed.returncode
            return status_value
        if not re.search(r"\bv\d+\.\d+\.\d+\b", completed.stdout or ""):
            status_value["reason"] = "Pinned sandbox image did not provide the expected Node runtime."
            return status_value
        status_value.update({
            "ready": True,
            "reason": "Pinned Apptainer image passed network, mount, environment, and resource capability checks.",
            "image_sha256": digest,
            "capability_probe": "passed",
            "enforced": [
                "non-root payload without sudo or fakeroot",
                "immutable pinned SIF image",
                "host home hidden",
                "source checkout read-only",
                "separate writable home and workspace",
                "clean environment without launcher secrets",
                "new PID and IPC namespaces",
                "network namespace with loopback only",
                "CPU, RAM, and PID limits accepted by runtime",
            ],
        })
        return status_value

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _mount(source: Path, destination: str, read_only: bool) -> str:
        source = source.resolve()
        if "\x00" in str(source) or "\n" in str(source):
            raise SandboxError("Sandbox mount path contains unsupported characters")
        escaped = str(source).replace('"', '""')
        mode = "ro" if read_only else "rw"
        return f'type=bind,src="{escaped}",dst={destination},{mode},nonested'

    def command(
        self,
        home: Path,
        workspace: Path,
        payload: Sequence[str],
        tree_root: Path | None = None,
    ) -> list[str]:
        if not self.binary or not self.config.image:
            raise SandboxError("Apptainer sandbox is not configured")
        if not home.is_dir() or home.is_symlink() or not workspace.is_dir() or workspace.is_symlink():
            raise SandboxError("Sandbox home and workspace must be existing non-symlink directories")
        if not payload or any("\x00" in str(item) for item in payload):
            raise SandboxError("Sandbox payload is empty or invalid")
        command = [
            self.binary,
            "exec",
            "--containall",
            "--cleanenv",
            "--no-eval",
            "--no-privs",
            "--no-mount",
            "home,cwd,hostfs,bind-paths",
            "--net",
            "--network",
            "none",
            "--cpus",
            self.config.cpus,
            "--memory",
            self.config.memory,
            "--pids-limit",
            str(self.config.pids_limit),
            "--mount",
            self._mount(home, "/home/dsh", read_only=False),
            "--mount",
            self._mount(workspace, "/workspace", read_only=False),
        ]
        if tree_root:
            if not tree_root.is_dir() or tree_root.is_symlink():
                raise SandboxError("Sandbox source tree must be an existing non-symlink directory")
            command.extend(["--mount", self._mount(tree_root, "/opt/dsh", read_only=True)])
        command.extend([
            "--env",
            "HOME=/home/dsh",
            "--env",
            "DSH_HOME=/home/dsh",
            "--pwd",
            "/workspace",
            str(self.config.image),
            *[str(item) for item in payload],
        ])
        return command

    def _host_environment(self) -> Mapping[str, str]:
        allowed = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR")
        environment = {name: value for name in allowed if (value := os.environ.get(name))}
        environment["APPTAINER_CACHEDIR"] = str(self.cache_root)
        return environment

    def _execute(self, command: Sequence[str], timeout: int) -> subprocess.CompletedProcess[str]:
        return self._runner(
            list(command),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
            env=dict(self._host_environment()),
        )

    def test_tree(self, tree: Mapping[str, Any]) -> dict[str, Any]:
        if not self.ready:
            raise SandboxError(str(self._status.get("reason") or "Apptainer sandbox is not ready"))
        image = self.config.image
        if not image or image.is_symlink() or not image.is_file() or image.stat().st_mode & 0o222:
            raise SandboxError("Pinned sandbox image is missing, replaced, or no longer read-only")
        if self._sha256(image) != self.image_digest:
            raise SandboxError("Pinned sandbox image changed after the capability probe")
        root = Path(str(tree.get("real_path") or "")).resolve()
        executable = Path(str(tree.get("real_exe") or "")).resolve()
        try:
            relative = executable.relative_to(root)
        except ValueError as error:
            raise SandboxError("Detected executable escapes the source tree") from error
        if not executable.is_file() or executable.is_symlink():
            raise SandboxError("Detected executable is not a regular in-tree file")
        executable_digest = self._sha256(executable)
        if tree.get("executable_sha256") and tree.get("executable_sha256") != executable_digest:
            raise SandboxError("Detected executable changed after the scanner captured it")
        payload = [str(Path("/opt/dsh") / relative), "--help"]
        if executable.suffix == ".js":
            payload.insert(0, "node")
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="test-", dir=self.state_root) as raw:
            test_root = Path(raw)
            home = test_root / "home"
            workspace = test_root / "workspace"
            home.mkdir(mode=0o700)
            workspace.mkdir(mode=0o700)
            command = self.command(home=home, workspace=workspace, tree_root=root, payload=payload)
            try:
                completed = self._execute(command, timeout=self.config.timeout_seconds)
                output = (completed.stdout or "")[-65536:]
                return {
                    "status": "passed" if completed.returncode == 0 else "failed",
                    "exit_code": completed.returncode,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "output": output,
                    "network": "none",
                    "secrets_forwarded": False,
                    "image_sha256": self.image_digest,
                    "executable_sha256": executable_digest,
                    "command_summary": "node /opt/dsh/<captured-cli> --help" if executable.suffix == ".js" else "/opt/dsh/<captured-cli> --help",
                }
            except subprocess.TimeoutExpired:
                return {
                    "status": "timeout",
                    "exit_code": None,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "output": "Sandbox test exceeded its configured timeout.",
                    "network": "none",
                    "secrets_forwarded": False,
                    "image_sha256": self.image_digest,
                    "executable_sha256": executable_digest,
                    "command_summary": "captured CLI help probe",
                }
            except OSError as error:
                raise SandboxError(f"Could not start Apptainer: {error}") from error
