"""Durable, schema-versioned Harness configurations for DSH Forge.

Configurations are inert records.  They can point at one signed package recipe
(which may itself contain many plugins) plus metadata-only catalog selections.
Only the launcher decides whether a record is runnable; loading this registry
never imports or executes community code.
"""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
from typing import Any, Iterator, Mapping


CONFIGURATION_SCHEMA = "dsh-forge.configuration/v1"
CONFIGURATION_REGISTRY_SCHEMA_VERSION = 1
_CONFIGURATION_ID = re.compile(r"config_[a-f0-9]{20}")
_VERSION_ID = re.compile(r"version_[a-f0-9]{12}")
_PACKAGE_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{1,63}")
_PROFILE = re.compile(r"[A-Za-z0-9_.-]{1,64}")
_ARTIFACT_ID = re.compile(r"[A-Za-z0-9@:/._+-]{1,240}")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ConfigurationError(Exception):
    """A configuration registry validation or persistence failure."""


def _text(value: Any, *, label: str, minimum: int, maximum: int) -> str:
    rendered = str(value or "").strip()
    if not minimum <= len(rendered) <= maximum or _CONTROL.search(rendered):
        raise ConfigurationError(f"{label} must contain {minimum} to {maximum} printable characters")
    return rendered


def normalize_launch(raw: Any = None) -> dict[str, Any]:
    """Return the deliberately small launch preset shared by UI and CLI."""

    value = raw if isinstance(raw, Mapping) else {}
    surface = str(value.get("surface") or "web")
    if surface not in {"web", "headless"}:
        raise ConfigurationError("Launch surface must be web or headless")
    profile = str(value.get("profile") or "web")
    if not _PROFILE.fullmatch(profile):
        raise ConfigurationError("Launch profile contains unsupported characters")
    task = str(value.get("task") or "").strip()
    if len(task) > 20_000 or _CONTROL.search(task):
        raise ConfigurationError("Headless task is invalid or exceeds 20,000 characters")
    if surface == "headless" and not task:
        raise ConfigurationError("Headless configurations require a task")
    requested_port = value.get("port", "auto")
    if requested_port in {None, "", "auto"}:
        port: str | int = "auto"
    else:
        try:
            port = int(requested_port)
        except (TypeError, ValueError):
            raise ConfigurationError("Launch port must be automatic or numeric") from None
        if not 1024 <= port <= 65535:
            raise ConfigurationError("Launch port must be between 1024 and 65535")
    network = str(value.get("network") or ("host" if surface == "web" else "none"))
    if network not in {"none", "host"}:
        raise ConfigurationError("Launch network must be none or host")
    if surface == "web" and network != "host":
        raise ConfigurationError("Web configurations require host networking for their loopback port")
    resources = value.get("resources") if isinstance(value.get("resources"), Mapping) else {}
    gpu = str(resources.get("gpu") or value.get("gpu") or "none")
    if gpu not in {"none", "allocated"}:
        raise ConfigurationError("GPU mode must be none or allocated")
    return {
        "surface": surface,
        "profile": profile,
        "task": task,
        "port": port,
        "open_browser": value.get("open_browser") is True,
        "network": network,
        "resources": {"gpu": gpu},
        "workspace": "managed",
    }


def normalize_selections(raw: Any = None) -> list[dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list) or len(raw) > 64:
        raise ConfigurationError("Catalog selections must be an array with at most 64 entries")
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise ConfigurationError("Each catalog selection must be an object")
        kind = str(item.get("type") or "")
        identity = str(item.get("id") or "")
        if kind not in {"package", "plugin", "fork"} or not _ARTIFACT_ID.fullmatch(identity):
            raise ConfigurationError("Catalog selection contains an invalid type or identity")
        key = (kind, identity)
        if key not in seen:
            result.append({"type": kind, "id": identity})
            seen.add(key)
    return result


class ConfigurationRegistry:
    """Cross-process safe registry whose mutations never touch Harness trees."""

    def __init__(self, state_root: str | Path):
        self.state_root = Path(state_root).expanduser()
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.state_root / "configurations.json"
        self.lock_path = self.state_root / "configurations.lock"

    @contextmanager
    def _lock(self) -> Iterator[None]:
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _load_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        if self.path.is_symlink():
            raise ConfigurationError("Configuration registry may not be a symlink")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ConfigurationError(f"Could not read the configuration registry: {error}") from error
        if not isinstance(payload, dict) or payload.get("schema_version") != CONFIGURATION_REGISTRY_SCHEMA_VERSION:
            raise ConfigurationError("Unsupported configuration registry schema")
        rows = payload.get("configurations")
        if not isinstance(rows, list) or len(rows) > 1024:
            raise ConfigurationError("Configuration registry is invalid or too large")
        return [self._validate_record(row) for row in rows]

    def _save_unlocked(self, records: list[dict[str, Any]]) -> None:
        payload = {
            "schema_version": CONFIGURATION_REGISTRY_SCHEMA_VERSION,
            "updated_at": int(time.time() * 1000),
            "configurations": records,
        }
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.state_root,
                prefix=".configurations-", suffix=".tmp", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                os.chmod(temporary, 0o600)
                handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    @staticmethod
    def _validate_record(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            raise ConfigurationError("Configuration record must be an object")
        identity = str(raw.get("id") or "")
        if not _CONFIGURATION_ID.fullmatch(identity):
            raise ConfigurationError("Configuration has an invalid identity")
        version_id = str(raw.get("version_id") or "")
        if not _VERSION_ID.fullmatch(version_id):
            raise ConfigurationError("Configuration has an invalid saved-version identity")
        package_slug = raw.get("package_slug")
        if package_slug is not None and not _PACKAGE_SLUG.fullmatch(str(package_slug)):
            raise ConfigurationError("Configuration has an invalid package identity")
        status = str(raw.get("status") or "draft")
        if status not in {"draft", "ready"}:
            raise ConfigurationError("Configuration status must be draft or ready")
        created_at = raw.get("created_at")
        updated_at = raw.get("updated_at")
        if not isinstance(created_at, int) or not isinstance(updated_at, int):
            raise ConfigurationError("Configuration timestamps must be integers")
        return {
            "schema": CONFIGURATION_SCHEMA,
            "id": identity,
            "name": _text(raw.get("name"), label="Configuration name", minimum=1, maximum=80),
            "description": _text(raw.get("description", ""), label="Configuration description", minimum=0, maximum=4000),
            "version_id": version_id,
            "package_slug": str(package_slug) if package_slug is not None else None,
            "selections": normalize_selections(raw.get("selections")),
            "launch": normalize_launch(raw.get("launch")),
            "status": status,
            "source": str(raw.get("source")) if raw.get("source") in {"user", "mcp-draft"} else "user",
            "created_at": created_at,
            "updated_at": updated_at,
        }

    def list(self) -> list[dict[str, Any]]:
        with self._lock():
            return self._load_unlocked()

    def get(self, identity: str) -> dict[str, Any]:
        if not _CONFIGURATION_ID.fullmatch(str(identity or "")):
            raise ConfigurationError("Choose a valid configuration")
        record = next((item for item in self.list() if item["id"] == identity), None)
        if record is None:
            raise ConfigurationError("Unknown configuration")
        return record

    def save(
        self,
        *,
        name: str,
        version_id: str,
        package_slug: str | None = None,
        description: str = "",
        selections: Any = None,
        launch: Any = None,
        status: str = "ready",
        source: str = "user",
    ) -> dict[str, Any]:
        now = int(time.time() * 1000)
        candidate = self._validate_record({
            "schema": CONFIGURATION_SCHEMA,
            "id": "config_" + secrets.token_hex(10),
            "name": name,
            "description": description,
            "version_id": version_id,
            "package_slug": package_slug,
            "selections": selections or [],
            "launch": launch or {},
            "status": status,
            "source": source,
            "created_at": now,
            "updated_at": now,
        })
        with self._lock():
            records = self._load_unlocked()
            records.append(candidate)
            self._save_unlocked(records)
        return candidate

    def approve(self, identity: str) -> dict[str, Any]:
        with self._lock():
            records = self._load_unlocked()
            for index, record in enumerate(records):
                if record["id"] == identity:
                    approved = {**record, "status": "ready", "source": "user", "updated_at": int(time.time() * 1000)}
                    records[index] = self._validate_record(approved)
                    self._save_unlocked(records)
                    return records[index]
        raise ConfigurationError("Unknown configuration")

    def remove(self, identity: str) -> list[dict[str, Any]]:
        if not _CONFIGURATION_ID.fullmatch(str(identity or "")):
            raise ConfigurationError("Choose a valid configuration")
        with self._lock():
            records = self._load_unlocked()
            remaining = [record for record in records if record["id"] != identity]
            if len(remaining) == len(records):
                raise ConfigurationError("Unknown configuration")
            self._save_unlocked(remaining)
            return remaining
