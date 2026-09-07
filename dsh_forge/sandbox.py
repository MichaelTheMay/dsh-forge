"""Fail-closed Apptainer planning for probes and complete local DSH cells."""

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
    """Pinned runtime inputs and required per-cell resource limits."""

    image: Path | None = None
    image_sha256: str | None = None
    binary: str = "apptainer"
    cpus: str = "4"
    memory: str = "8G"
    pids_limit: int = 256
    timeout_seconds: int = 30
    cell_timeout_seconds: int = 14400

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
        cell_timeout_seconds: int = 14400,
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
        if not 60 <= int(cell_timeout_seconds) <= 604800:
            raise SandboxError("Sandbox cell timeout must be between 60 seconds and 7 days")
        return cls(
            image=resolved_image,
            image_sha256=digest,
            binary=str(binary),
            cpus=str(cpus),
            memory=str(memory),
            pids_limit=int(pids_limit),
            timeout_seconds=int(timeout_seconds),
            cell_timeout_seconds=int(cell_timeout_seconds),
        )

    @classmethod
    def from_environment(cls) -> "SandboxConfig":
        """Build the same configuration for the UI sidecar and standalone CLI."""
        return cls.from_values(
            image=os.environ.get("DSH_FORGE_SANDBOX_IMAGE"),
            image_sha256=os.environ.get("DSH_FORGE_SANDBOX_IMAGE_SHA256"),
            binary=os.environ.get("DSH_FORGE_SANDBOX_BINARY", "apptainer"),
            cpus=os.environ.get("DSH_FORGE_SANDBOX_CPUS", "4"),
            memory=os.environ.get("DSH_FORGE_SANDBOX_MEMORY", "8G"),
            pids_limit=int(os.environ.get("DSH_FORGE_SANDBOX_PIDS_LIMIT", "256")),
            timeout_seconds=int(os.environ.get("DSH_FORGE_SANDBOX_TIMEOUT", "30")),
            cell_timeout_seconds=int(os.environ.get("DSH_FORGE_CELL_TIMEOUT", "14400")),
        )


class ApptainerSandbox:
    """Build pinned-image cell commands without inherited launcher secrets."""

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
        self.runtime_home = self.state_root / "runtime-home"
        self.runtime_home.mkdir(exist_ok=True, mode=0o700)
        self._runner = runner or subprocess.run
        self.binary = self._resolve_binary(config.binary, which)
        self.timeout_binary = self._resolve_binary("timeout", which)
        self.image_digest: str | None = None
        self.resource_scope = "unavailable"
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
            "mode": "apptainer-cell-v1" if self.config.image else "unavailable",
            "configured": bool(self.config.image),
            "ready": False,
            "runtime": "apptainer",
            "hostile_code_isolation": False,
            "network": "none",
            "network_modes": ["none", "host"],
            "host_home_exposed": False,
            "secrets_forwarded": False,
            "image": str(self.config.image) if self.config.image else None,
            "image_sha256": self.config.image_sha256,
            "resource_limits": {
                "cpus": self.config.cpus,
                "memory": self.config.memory,
                "pids": self.config.pids_limit,
                "wall_seconds": self.config.cell_timeout_seconds,
                "scope": "pending",
                "probe_required": True,
            },
            "enforced": [],
            "not_enforced": ["kernel exploit immunity", "per-cell disk quota", "outbound filtering in host-network mode"],
            "reason": "Configure a pinned Apptainer image and SHA-256 before launching any cell.",
        }

    def _inspect_and_probe(self) -> dict[str, Any]:
        status_value = self._base_status()
        image = self.config.image
        if not image:
            return status_value
        if not self.binary:
            status_value["reason"] = "Apptainer executable was not found or is not executable."
            return status_value
        if not self.timeout_binary:
            status_value["reason"] = "The coreutils timeout executable is required for persistent wall-time enforcement."
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
                core_command = self.command(
                    home=home,
                    workspace=workspace,
                    payload=["node", "--version"],
                    include_resource_limits=False,
                )
                completed = self._execute(core_command, timeout=min(15, self.config.timeout_seconds))
                if completed.returncode != 0:
                    status_value["reason"] = "Apptainer capability probe rejected the required isolation flags."
                    status_value["probe_exit_code"] = completed.returncode
                    status_value["probe_output"] = self._probe_output(completed.stdout)
                    return status_value
                if not re.search(r"\bv\d+\.\d+\.\d+\b", completed.stdout or ""):
                    status_value["reason"] = "Pinned sandbox image did not provide the expected Node runtime."
                    status_value["probe_output"] = self._probe_output(completed.stdout)
                    return status_value

                # DeltaAI enforces the job allocation with Slurm, but its compute
                # nodes do not delegate the user cgroups that Apptainer's
                # per-container resource flags require. Outside Slurm, those
                # flags must pass or the runner remains unavailable.
                if os.environ.get("SLURM_JOB_ID"):
                    self.resource_scope = "shared-slurm"
                else:
                    limited_command = self.command(
                        home=home,
                        workspace=workspace,
                        payload=["node", "--version"],
                        include_resource_limits=True,
                    )
                    limited = self._execute(limited_command, timeout=min(15, self.config.timeout_seconds))
                    if limited.returncode != 0:
                        status_value["reason"] = (
                            "Apptainer per-cell resource controls were rejected, and no Slurm allocation is active."
                        )
                        status_value["probe_exit_code"] = limited.returncode
                        status_value["probe_output"] = self._probe_output(limited.stdout)
                        return status_value
                    self.resource_scope = "per-cell-cgroup"
        except (OSError, SandboxError, subprocess.TimeoutExpired) as error:
            status_value["reason"] = f"Apptainer capability probe failed: {type(error).__name__}."
            return status_value

        enforced = [
            "non-root payload without sudo or fakeroot",
            "immutable pinned SIF image",
            "host home hidden",
            "source checkout read-only",
            "separate writable home and workspace",
            "clean environment without launcher secrets",
            "new PID and IPC namespaces",
            "networkless mode available through a loopback-only namespace",
            "cell wall time enforced by an external process supervisor",
        ]
        if self.resource_scope == "per-cell-cgroup":
            enforced.append("per-cell CPU, RAM, and PID limits accepted by the runtime")
            reason = "Pinned Apptainer image passed isolation and per-cell resource capability checks."
        else:
            enforced.append("aggregate CPU, RAM, and GPU allocation enforced by Slurm")
            status_value["not_enforced"].append(
                "per-cell CPU, RAM, or PID quotas inside the shared Slurm allocation"
            )
            reason = "Pinned Apptainer image passed isolation checks inside the active Slurm allocation."
        status_value["resource_limits"]["scope"] = self.resource_scope
        status_value.update({
            "ready": True,
            "reason": reason,
            "image_sha256": digest,
            "capability_probe": "passed",
            "enforced": enforced,
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
    def _probe_output(output: str | None) -> str:
        excerpt = (output or "")[-4096:]
        host_home = str(Path.home())
        return excerpt.replace(host_home, "~") if host_home else excerpt

    @staticmethod
    def _mount(source: Path, destination: str, read_only: bool) -> str:
        source = source.resolve()
        # This is passed as one argv item, so whitespace needs no shell quoting.
        # DeltaAI's Apptainer 1.4 parser rejects a quote embedded after ``src=``.
        # Reject mount-spec delimiters instead of constructing partial CSV.
        if any(character in str(source) for character in ("\x00", "\n", ",", '"')):
            raise SandboxError("Sandbox mount path contains unsupported characters")
        suffix = ",ro" if read_only else ""
        return f"type=bind,src={source},dst={destination}{suffix}"

    def command(
        self,
        home: Path,
        workspace: Path,
        payload: Sequence[str],
        tree_root: Path | None = None,
        network: str = "none",
        gpu: bool = False,
        container_environment: Mapping[str, str] | None = None,
        read_only_mounts: Sequence[tuple[Path, str]] = (),
        validate_paths: bool = True,
        include_resource_limits: bool | None = None,
    ) -> list[str]:
        if not self.binary or not self.config.image:
            raise SandboxError("Apptainer sandbox is not configured")
        if validate_paths and (not home.is_dir() or home.is_symlink() or not workspace.is_dir() or workspace.is_symlink()):
            raise SandboxError("Sandbox home and workspace must be existing non-symlink directories")
        if network not in {"none", "host"}:
            raise SandboxError("Sandbox network must be 'none' or 'host'")
        if not payload or any("\x00" in str(item) for item in payload):
            raise SandboxError("Sandbox payload is empty or invalid")
        resolved_home = home.resolve()
        if any(character in str(resolved_home) for character in ("\x00", "\n", ":")):
            raise SandboxError("Sandbox home path contains unsupported characters")
        command = [
            self.binary,
            "exec",
            "--containall",
            "--cleanenv",
            "--no-eval",
            "--no-privs",
            "--no-mount",
            "cwd,hostfs,bind-paths",
            "--home",
            f"{resolved_home}:/home/dsh",
            "--mount",
            self._mount(workspace, "/workspace", read_only=False),
        ]
        if include_resource_limits is None:
            include_resource_limits = self.resource_scope == "per-cell-cgroup"
        if include_resource_limits:
            command.extend([
                "--cpus",
                self.config.cpus,
                "--memory",
                self.config.memory,
                "--pids-limit",
                str(self.config.pids_limit),
            ])
        if network == "none":
            command.extend(["--net", "--network", "none"])
        if gpu:
            command.append("--nv")
        if tree_root:
            if validate_paths and (not tree_root.is_dir() or tree_root.is_symlink()):
                raise SandboxError("Sandbox source tree must be an existing non-symlink directory")
            command.extend(["--mount", self._mount(tree_root, "/opt/dsh", read_only=True)])
        destinations: set[str] = set()
        for source, destination in read_only_mounts:
            if not isinstance(destination, str) or not re.fullmatch(r"/[A-Za-z0-9._/-]{1,255}", destination):
                raise SandboxError("Additional sandbox mount has an invalid destination")
            if destination in destinations or destination in {"/home/dsh", "/workspace", "/opt/dsh"}:
                raise SandboxError("Additional sandbox mount destination collides with a protected mount")
            destinations.add(destination)
            if validate_paths and (source.is_symlink() or not source.is_file()):
                raise SandboxError("Additional sandbox mount must be an existing non-symlink file")
            command.extend(["--mount", self._mount(source, destination, read_only=True)])
        environment = {
            "DSH_HOME": "/home/dsh",
            # Stop the APPTAINER_BIND propagation described by Apptainer for
            # nested invocations. The host runner environment is allowlisted too.
            "APPTAINER_BIND": "",
            "APPTAINER_BINDPATH": "",
            "APPTAINER_MOUNT": "",
        }
        for name, value in (container_environment or {}).items():
            if not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", str(name)) or "\x00" in str(value) or "\n" in str(value):
                raise SandboxError("Sandbox environment contains an invalid name or value")
            environment[str(name)] = str(value)
        for name, value in environment.items():
            command.extend(["--env", f"{name}={value}"])
        command.extend([
            "--pwd",
            "/workspace",
            str(self.config.image),
            *[str(item) for item in payload],
        ])
        return command

    def package_command_plan(
        self,
        *,
        tree: Mapping[str, Any],
        home: Path,
        workspace: Path,
        payload: Sequence[str],
        network: str,
        read_only_mounts: Sequence[tuple[Path, str]],
        container_environment: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        """Build a supervised command for a disposable package operation."""

        root, executable, relative = self._verify_pinned_inputs(tree)
        executable_payload = [str(Path("/opt/dsh") / relative)]
        if executable.suffix == ".js":
            executable_payload.insert(0, "node")
        command = self.command(
            home=home,
            workspace=workspace,
            tree_root=root,
            payload=[*executable_payload, *[str(item) for item in payload]],
            network=network,
            gpu=False,
            container_environment=container_environment,
            read_only_mounts=read_only_mounts,
        )
        if not self.timeout_binary:
            raise SandboxError("Cell wall-time supervisor is unavailable")
        supervised = [
            self.timeout_binary,
            "--foreground",
            "--signal=TERM",
            "--kill-after=5",
            str(self.config.cell_timeout_seconds),
            *command,
        ]
        return {
            "argv": supervised,
            "environment": dict(self._host_environment()),
            "network": network,
            "image_sha256": self.image_digest,
            "executable_sha256": self._sha256(executable),
            "secrets_forwarded": False,
        }

    def _verify_pinned_inputs(self, tree: Mapping[str, Any]) -> tuple[Path, Path, Path]:
        if not self.ready:
            raise SandboxError(str(self._status.get("reason") or "Apptainer sandbox is not ready"))
        image = self.config.image
        if not image or image.is_symlink() or not image.is_file() or image.stat().st_mode & 0o222:
            raise SandboxError("Pinned sandbox image is missing, replaced, or no longer read-only")
        if self._sha256(image) != self.image_digest:
            raise SandboxError("Pinned sandbox image changed after the capability probe")
        root_candidate = Path(str(tree.get("real_path") or ""))
        executable_candidate = Path(str(tree.get("real_exe") or ""))
        if root_candidate.is_symlink() or not root_candidate.is_dir():
            raise SandboxError("Detected source tree is missing or was replaced by a symlink")
        if executable_candidate.is_symlink() or not executable_candidate.is_file():
            raise SandboxError("Detected executable is missing or was replaced by a symlink")
        root = root_candidate.resolve()
        executable = executable_candidate.resolve()
        try:
            relative = executable.relative_to(root)
        except ValueError as error:
            raise SandboxError("Detected executable escapes the source tree") from error
        executable_digest = self._sha256(executable)
        if tree.get("executable_sha256") and tree.get("executable_sha256") != executable_digest:
            raise SandboxError("Detected executable changed after the scanner captured it")
        return root, executable, relative

    def cell_plan(
        self,
        *,
        tree: Mapping[str, Any],
        home: Path,
        workspace: Path,
        surface: str,
        task: str,
        port: int | None,
        profile: str,
        network: str,
        gpu: bool,
        validate_paths: bool = True,
    ) -> dict[str, Any]:
        """Return a complete immutable launch plan or fail before process creation."""
        root, executable, relative = self._verify_pinned_inputs(tree)
        if surface not in {"web", "headless"}:
            raise SandboxError("Unsupported Harness surface")
        if surface == "web" and network != "host":
            raise SandboxError("Web cells require explicit host networking so their loopback port is reachable")
        if surface == "web" and not port:
            raise SandboxError("Web cells require a reserved loopback port")
        if surface == "headless" and not task:
            raise SandboxError("Headless cells require a task")
        if gpu and not (
            os.environ.get("SLURM_JOB_ID")
            and any(os.environ.get(name) for name in ("CUDA_VISIBLE_DEVICES", "SLURM_JOB_GPUS"))
        ):
            raise SandboxError("GPU exposure requires an existing scheduler GPU allocation")
        payload = [str(Path("/opt/dsh") / relative)]
        if executable.suffix == ".js":
            payload.insert(0, "node")
        if surface == "headless":
            payload.extend(["headless", task])
        else:
            payload.extend(["web", "--host", "127.0.0.1", "--port", str(port), "--no-open"])
        environment = {"DSH_PROFILE": "web" if surface == "web" else profile}
        if port:
            environment["DSH_PORT"] = str(port)
        command = self.command(
            home=home,
            workspace=workspace,
            tree_root=root,
            payload=payload,
            network=network,
            gpu=gpu,
            container_environment=environment,
            validate_paths=validate_paths,
        )
        if not self.timeout_binary:
            raise SandboxError("Cell wall-time supervisor is unavailable")
        supervised = [
            self.timeout_binary,
            "--foreground",
            "--signal=TERM",
            "--kill-after=5",
            str(self.config.cell_timeout_seconds),
            *command,
        ]
        material = "\0".join(supervised).encode()
        return {
            "argv": supervised,
            "environment": dict(self._host_environment()),
            "network": network,
            "gpu": "allocated" if gpu else "none",
            "image_sha256": self.image_digest,
            "executable_sha256": self._sha256(executable),
            "command_sha256": hashlib.sha256(material).hexdigest(),
            "resources": {
                "cpu": self.config.cpus,
                "gpu": "allocated" if gpu else "none",
                "ram": self.config.memory,
                "pids": self.config.pids_limit,
                "wall_seconds": self.config.cell_timeout_seconds,
                "enforced": True,
                "scope": self.resource_scope,
                "per_cell_enforced": self.resource_scope == "per-cell-cgroup",
                "note": (
                    "Per-cell cgroup limits accepted by Apptainer."
                    if self.resource_scope == "per-cell-cgroup"
                    else "CPU, RAM, and GPU are shared within the Slurm allocation; wall time is per cell."
                ),
            },
            "secrets_forwarded": False,
        }

    def _host_environment(self) -> Mapping[str, str]:
        allowed = ("PATH", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR")
        environment = {name: value for name in allowed if (value := os.environ.get(name))}
        environment["HOME"] = str(self.runtime_home)
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
        if self.resource_scope != "per-cell-cgroup":
            raise SandboxError(
                "Community-code probes require per-cell cgroup controls; shared Slurm allocation limits are insufficient."
            )
        root, executable, relative = self._verify_pinned_inputs(tree)
        executable_digest = self._sha256(executable)
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
