"""Fail-closed inspection and disposable installation of signed DSH packages.

Only artifacts already acquired by :mod:`dsh_forge.acquisition` are accepted.
The DSSE envelope and content addresses are re-verified, npm archives are
inspected without host extraction, and installation targets a fresh Apptainer
home. The user's existing DSH home is never mounted or modified.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import subprocess
import tarfile
from typing import Any, Callable, Mapping, Sequence

from .acquisition import RECEIPT_SCHEMA
from .packages import PackageError, read_json, verify, write_json
from .sandbox import ApptainerSandbox


INSPECTION_SCHEMA = "dsh-forge.archive-inspection/v1"
INSTALL_RECEIPT_SCHEMA = "dsh-forge.sandbox-install-receipt/v1"
DEFAULT_INSTALL_ROOT = Path.home() / ".local" / "state" / "dsh-forge" / "package-installs"
MAX_ARCHIVE_ENTRIES = 20_000
MAX_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_PACKAGE_JSON_BYTES = 1024 * 1024
MAX_LOG_BYTES = 1024 * 1024

_OBJECT = re.compile(r"objects/sha256/[0-9a-f]{2}/([0-9a-f]{64})/artifact")
_PACKAGE_NAME = re.compile(r"(?:@[a-z0-9._-]+/)?[a-z0-9._-]+")
_SAFE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{1,127}")


class InstallationError(PackageError):
    """A package failed archive or disposable-install policy."""


def _exact_keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InstallationError(f"{label} must be an object", "invalid_receipt")
    actual = set(value)
    if actual != expected:
        raise InstallationError(
            f"{label} fields differ; missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}",
            "invalid_receipt",
        )
    return value


def _file_identity(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                size += len(chunk)
                digest.update(chunk)
    except OSError as error:
        raise InstallationError(f"Could not read quarantined object: {error}", "quarantine_io_error") from error
    return size, "sha256:" + digest.hexdigest()


def _safe_archive_name(raw: str) -> str:
    if not isinstance(raw, str) or not raw or len(raw.encode("utf-8", errors="ignore")) > 4096:
        raise InstallationError("Archive contains an invalid or overlong path", "unsafe_archive")
    if "\\" in raw or "\x00" in raw or any(ord(character) < 32 for character in raw):
        raise InstallationError("Archive path contains forbidden characters", "unsafe_archive")
    path = PurePosixPath(raw)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise InstallationError(f"Archive path is not confined: {raw}", "unsafe_archive")
    normalized = path.as_posix().rstrip("/")
    if not normalized or not (normalized == "package" or normalized.startswith("package/")):
        raise InstallationError("npm archive must use the package/ root", "unsafe_archive")
    return normalized


def _json_object(raw: bytes, label: str) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise InstallationError(f"Duplicate JSON key in {label}: {key}", "unsafe_archive")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InstallationError(f"Invalid UTF-8 JSON in {label}: {error}", "unsafe_archive") from error
    if not isinstance(value, dict):
        raise InstallationError(f"{label} must contain a JSON object", "unsafe_archive")
    return value


def _dependency_summary(package_json: Mapping[str, Any]) -> tuple[dict[str, int], list[str]]:
    counts: dict[str, int] = {}
    forbidden: list[str] = []
    for field in ("dependencies", "optionalDependencies", "peerDependencies"):
        dependencies = package_json.get(field, {})
        if dependencies is None:
            dependencies = {}
        if not isinstance(dependencies, dict) or len(dependencies) > 2048:
            raise InstallationError(f"package.json {field} is invalid or too large", "unsafe_archive")
        counts[field] = len(dependencies)
        for name, specification in dependencies.items():
            if not isinstance(name, str) or not _PACKAGE_NAME.fullmatch(name) or not isinstance(specification, str):
                raise InstallationError(f"package.json {field} contains an invalid dependency", "unsafe_archive")
            lowered = specification.strip().lower()
            if lowered.startswith(("file:", "link:", "workspace:", "git:", "git+", "http:", "https:")):
                forbidden.append(f"{field}:{name}")
    return counts, forbidden


def inspect_npm_archive(path: Path, expected_name: str, expected_version: str) -> dict[str, Any]:
    """Inspect one npm tgz without extracting it to the host filesystem."""

    names: set[str] = set()
    casefolded: set[str] = set()
    total_size = 0
    package_json_bytes: bytes | None = None
    try:
        with tarfile.open(path, mode="r:gz") as archive:
            for index, member in enumerate(archive, start=1):
                if index > MAX_ARCHIVE_ENTRIES:
                    raise InstallationError("Archive exceeds the entry limit", "archive_too_large")
                name = _safe_archive_name(member.name)
                folded = name.casefold()
                if name in names or folded in casefolded:
                    raise InstallationError(f"Archive contains a duplicate or case-colliding path: {name}", "unsafe_archive")
                names.add(name)
                casefolded.add(folded)
                if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                    raise InstallationError(f"Archive contains a forbidden special entry: {name}", "unsafe_archive")
                if not (member.isfile() or member.isdir()):
                    raise InstallationError(f"Archive contains an unsupported entry: {name}", "unsafe_archive")
                if member.isfile():
                    if member.size < 0 or member.size > MAX_FILE_BYTES:
                        raise InstallationError(f"Archive member exceeds the file limit: {name}", "archive_too_large")
                    total_size += member.size
                    if total_size > MAX_EXPANDED_BYTES:
                        raise InstallationError("Archive exceeds the expanded byte limit", "archive_too_large")
                    if name == "package/package.json":
                        if member.size > MAX_PACKAGE_JSON_BYTES:
                            raise InstallationError("package.json exceeds the byte limit", "archive_too_large")
                        extracted = archive.extractfile(member)
                        if extracted is None:
                            raise InstallationError("Could not read package.json from archive", "unsafe_archive")
                        package_json_bytes = extracted.read(MAX_PACKAGE_JSON_BYTES + 1)
    except (tarfile.TarError, OSError, EOFError) as error:
        raise InstallationError(f"Invalid npm archive: {error}", "unsafe_archive") from error

    if package_json_bytes is None:
        raise InstallationError("npm archive has no package/package.json", "unsafe_archive")
    package_json = _json_object(package_json_bytes, "package/package.json")
    if package_json.get("name") != expected_name or package_json.get("version") != expected_version:
        raise InstallationError("Archive package name/version does not match the signed manifest", "package_identity_mismatch")
    scripts = package_json.get("scripts", {})
    if scripts is None:
        scripts = {}
    if not isinstance(scripts, dict) or len(scripts) > 256 or any(
        not isinstance(name, str) or not isinstance(command, str) for name, command in scripts.items()
    ):
        raise InstallationError("package.json scripts is invalid", "unsafe_archive")
    dependency_counts, forbidden_dependencies = _dependency_summary(package_json)
    if forbidden_dependencies:
        raise InstallationError(
            "Package uses local, Git, or direct-URL dependencies: " + ", ".join(sorted(forbidden_dependencies)),
            "unsupported_dependency_source",
        )
    lifecycle_names = sorted(set(scripts).intersection({"preinstall", "install", "postinstall", "prepare"}))
    return {
        "format": "npm-tgz",
        "entry_count": len(names),
        "expanded_bytes": total_size,
        "package_name": expected_name,
        "package_version": expected_version,
        "lifecycle_scripts_declared": lifecycle_names,
        "lifecycle_scripts_allowed": False,
        "dependency_counts": dependency_counts,
        "forbidden_entries": [],
    }


def inspect_acquisition(
    envelope: dict[str, Any],
    trust_root: dict[str, Any],
    receipt_path: str | Path,
) -> dict[str, Any]:
    """Re-verify a signed acquisition receipt and inspect all npm archives."""

    verification = verify(envelope, trust_root)
    manifest = verification["manifest"]
    receipt = read_json(receipt_path)
    _exact_keys(receipt, {
        "schema", "package", "payload_digest", "composition_digest", "valid_signers", "threshold",
        "acquired_at", "quarantine_root", "limits", "artifacts", "credentials_forwarded",
        "archives_extracted", "installation_authorized", "execution_authorized",
    }, "acquisition receipt")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise InstallationError("Unsupported acquisition receipt schema", "invalid_receipt")
    if receipt.get("payload_digest") != verification["payload_digest"]:
        raise InstallationError("Receipt payload digest does not match the signed package", "receipt_mismatch")
    if receipt.get("composition_digest") != manifest["composition_digest"] or receipt.get("package") != manifest["package"]:
        raise InstallationError("Receipt package does not match the signed package", "receipt_mismatch")
    if receipt.get("valid_signers") != verification["valid_signers"] or receipt.get("threshold") != verification["threshold"]:
        raise InstallationError("Receipt signer evidence does not match current verification", "receipt_mismatch")
    if any(receipt.get(field) is not False for field in (
        "credentials_forwarded", "archives_extracted", "installation_authorized", "execution_authorized"
    )):
        raise InstallationError("Acquisition receipt makes an unsupported authorization claim", "invalid_receipt")

    artifacts = receipt.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != len(manifest["plugins"]):
        raise InstallationError("Receipt artifact count does not match the signed package", "receipt_mismatch")
    by_id: dict[str, dict[str, Any]] = {}
    for artifact in artifacts:
        if not isinstance(artifact, dict) or not isinstance(artifact.get("plugin_id"), str):
            raise InstallationError("Receipt contains an invalid artifact", "invalid_receipt")
        if artifact["plugin_id"] in by_id:
            raise InstallationError("Receipt contains duplicate plugin artifacts", "invalid_receipt")
        by_id[artifact["plugin_id"]] = artifact

    quarantine_root = Path(str(receipt.get("quarantine_root") or "")).expanduser()
    if quarantine_root.is_symlink() or not quarantine_root.is_dir():
        raise InstallationError("Quarantine root is missing or is a symlink", "quarantine_corrupt")
    quarantine_root = quarantine_root.resolve()
    inspected: list[dict[str, Any]] = []
    for plugin in manifest["plugins"]:
        artifact = by_id.get(plugin["id"])
        if artifact is None:
            raise InstallationError(f"Receipt is missing artifact {plugin['id']}", "receipt_mismatch")
        source = plugin["source"]
        for field, expected in (
            ("source_kind", source["kind"]), ("source_name", source["name"]),
            ("source_version", source["version"]), ("signed_integrity", source["integrity"]),
        ):
            if artifact.get(field) != expected:
                raise InstallationError(f"Receipt artifact {plugin['id']} does not match signed {field}", "receipt_mismatch")
        object_name = artifact.get("object")
        match = _OBJECT.fullmatch(object_name) if isinstance(object_name, str) else None
        if not match:
            raise InstallationError("Receipt contains an invalid content-addressed object path", "invalid_receipt")
        object_path = quarantine_root.joinpath(*PurePosixPath(object_name).parts)
        if object_path.is_symlink() or not object_path.is_file():
            raise InstallationError("Quarantined object is missing or is a symlink", "quarantine_corrupt")
        if stat.S_IMODE(object_path.stat().st_mode) & 0o222:
            raise InstallationError("Quarantined object is writable", "quarantine_corrupt")
        size, digest = _file_identity(object_path)
        if digest != artifact.get("content_sha256") or digest != "sha256:" + match.group(1) or size != artifact.get("bytes"):
            raise InstallationError("Quarantined object failed its content address", "quarantine_corrupt")
        if source["kind"] != "npm":
            raise InstallationError(
                f"Disposable V1 installation supports npm artifacts only, not {source['kind']}",
                "unsupported_artifact_kind",
            )
        archive = inspect_npm_archive(object_path, source["name"], source["version"])
        inspected.append({"plugin_id": plugin["id"], "object": object_name, "content_sha256": digest, **archive})

    return {
        "schema": INSPECTION_SCHEMA,
        "package": manifest["package"],
        "payload_digest": verification["payload_digest"],
        "composition_digest": manifest["composition_digest"],
        "inspected_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "artifacts": inspected,
        "limits": {
            "max_entries_per_archive": MAX_ARCHIVE_ENTRIES,
            "max_expanded_bytes_per_archive": MAX_EXPANDED_BYTES,
            "max_file_bytes": MAX_FILE_BYTES,
        },
        "archives_extracted_on_host": False,
        "lifecycle_scripts_allowed": False,
        "host_installation_authorized": False,
        "sandbox_installation_authorized": True,
        "execution_authorized": False,
    }


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _run(command: Sequence[str], environment: Mapping[str, str], timeout: int, runner: Runner) -> subprocess.CompletedProcess[str]:
    try:
        return runner(
            list(command), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, check=False, timeout=timeout, env=dict(environment),
        )
    except subprocess.TimeoutExpired as error:
        raise InstallationError("Sandbox installation exceeded its timeout", "install_timeout") from error
    except OSError as error:
        raise InstallationError(f"Could not start sandbox installation: {error}", "install_failed") from error


def install_in_sandbox(
    envelope: dict[str, Any],
    trust_root: dict[str, Any],
    receipt_path: str | Path,
    *,
    tree: Mapping[str, Any],
    sandbox: ApptainerSandbox,
    install_root: str | Path = DEFAULT_INSTALL_ROOT,
    profile: str = "web",
    timeout_seconds: int = 900,
    runner: Runner = subprocess.run,
) -> dict[str, Any]:
    """Install exact top-level npm artifacts into a new contained DSH home."""

    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", profile):
        raise InstallationError("Profile contains unsupported characters", "invalid_install_argument")
    if type(timeout_seconds) is not int or not 30 <= timeout_seconds <= 3600:
        raise InstallationError("Install timeout must be between 30 and 3600 seconds", "invalid_install_argument")
    inspection = inspect_acquisition(envelope, trust_root, receipt_path)
    verification = verify(envelope, trust_root)
    manifest = verification["manifest"]
    if not sandbox.ready:
        raise InstallationError(str(sandbox.status().get("reason") or "Apptainer sandbox is unavailable"), "sandbox_unavailable")

    package_id = manifest["package"]["id"]
    if not _SAFE_ID.fullmatch(package_id):
        raise InstallationError("Signed package ID is invalid", "invalid_package")
    payload_hex = verification["payload_digest"].removeprefix("sha256:")
    install_id = f"install_{payload_hex[:12]}_{secrets.token_hex(4)}"
    root = Path(install_root).expanduser().resolve() / install_id
    if root.exists():
        raise InstallationError("Generated installation identity already exists", "install_conflict")
    home = root / "home"
    workspace = root / "workspace"
    root.mkdir(parents=True, mode=0o700)
    home.mkdir(mode=0o700)
    workspace.mkdir(mode=0o700)
    log_path = workspace / "install.log"

    acquisition_receipt = read_json(receipt_path)
    quarantine_root = Path(acquisition_receipt["quarantine_root"]).expanduser().resolve()
    artifact_receipts = {item["plugin_id"]: item for item in acquisition_receipt["artifacts"]}
    plugin_by_id = {plugin["id"]: plugin for plugin in manifest["plugins"]}
    output_parts: list[str] = []
    installed: list[dict[str, str]] = []
    environment = {
        "CI": "1", "NPM_CONFIG_IGNORE_SCRIPTS": "true", "NPM_CONFIG_AUDIT": "false",
        "NPM_CONFIG_FUND": "false", "NPM_CONFIG_USERCONFIG": "/dev/null",
        "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0", "DSH_PROFILE": profile,
    }

    try:
        for index, plugin_id in enumerate(manifest["load_order"]):
            plugin = plugin_by_id[plugin_id]
            artifact = artifact_receipts[plugin_id]
            host_artifact = quarantine_root.joinpath(*PurePosixPath(artifact["object"]).parts)
            target = f"/quarantine/{index:03d}-{plugin_id}.tgz"
            plan = sandbox.package_command_plan(
                tree=tree, home=home, workspace=workspace,
                payload=["plugin", "--profile", profile, "add", "--save-exact", "--ignore-scripts", f"file:{target}"],
                network="host", read_only_mounts=[(host_artifact, target)],
                container_environment=environment,
            )
            completed = _run(plan["argv"], plan["environment"], timeout_seconds, runner)
            output_parts.append(f"[{plugin_id}]\n{completed.stdout or ''}")
            if completed.returncode != 0:
                raise InstallationError(
                    f"Sandbox package installation failed for {plugin_id} with exit code {completed.returncode}; evidence: {root}",
                    "install_failed",
                )
            installed.append({"plugin_id": plugin_id, "name": plugin["source"]["name"], "version": plugin["source"]["version"]})

        probe = sandbox.package_command_plan(
            tree=tree, home=home, workspace=workspace, payload=["--profile", profile, "--dump-config"],
            network="none", read_only_mounts=[], container_environment=environment,
        )
        completed = _run(probe["argv"], probe["environment"], min(timeout_seconds, 300), runner)
        output_parts.append(f"[composition-probe]\n{completed.stdout or ''}")
        if completed.returncode != 0:
            raise InstallationError(
                f"Networkless package composition probe failed with exit code {completed.returncode}; evidence: {root}",
                "compatibility_probe_failed",
            )
        missing = [item["name"] for item in installed if item["name"] not in (completed.stdout or "")]
        if missing:
            raise InstallationError(
                "Networkless composition output did not identify installed package(s): " + ", ".join(missing),
                "compatibility_probe_failed",
            )
    finally:
        rendered = "\n".join(output_parts).encode("utf-8", errors="replace")[-MAX_LOG_BYTES:]
        log_path.write_bytes(rendered)
        os.chmod(log_path, 0o600)

    receipt = {
        "schema": INSTALL_RECEIPT_SCHEMA,
        "install_id": install_id,
        "package": manifest["package"],
        "payload_digest": verification["payload_digest"],
        "composition_digest": manifest["composition_digest"],
        "installed_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "profile": profile,
        "home": str(home),
        "workspace": str(workspace),
        "log": str(log_path),
        "plugins": installed,
        "archive_inspection": inspection,
        "sandbox": {
            "mode": "apptainer-cell-v1", "image_sha256": sandbox.status().get("image_sha256"),
            "network_during_install": "host", "network_during_probe": "none",
            "secrets_forwarded": False, "host_home_exposed": False,
        },
        "dependency_resolution": {
            "top_level_artifacts_signed": True, "transitive_dependencies_signed": False,
            "source": "credential-free public npm inside disposable sandbox",
        },
        "lifecycle_scripts_allowed": False,
        "host_profile_modified": False,
        "sandbox_installed": True,
        "composition_probe_passed": True,
        "ready_for_sandbox_launch": True,
    }
    output = root / "receipt.json"
    write_json(output, receipt)
    output.chmod(0o400)
    receipt["receipt"] = str(output)
    return receipt
