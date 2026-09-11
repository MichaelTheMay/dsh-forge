"""Offline composition and signature verification for DSH Forge packages.

This module deliberately does not fetch, install, import, or execute plugin code.
It only validates metadata, produces deterministic manifests, and invokes the
host OpenSSL binary for Ed25519 signing and verification.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from typing import Any
from urllib.parse import urlsplit


SPEC_SCHEMA = "dsh-forge.package-spec/v1"
PACKAGE_SCHEMA = "dsh-forge.package/v1"
TRUST_ROOT_SCHEMA = "dsh-forge.trust-root/v1"
PAYLOAD_TYPE = "application/vnd.dsh-forge.package.v1+json"
CANONICALIZATION = "RFC8785-JCS-ascii-key-no-number-profile/v1"
MAX_JSON_BYTES = 1_048_576
MAX_PLUGINS = 128
PERMISSIONS = {
    "browser:control",
    "environment:read",
    "filesystem:read",
    "filesystem:write",
    "gpu:access",
    "model:invoke",
    "network:outbound",
    "process:spawn",
    "session:read",
    "session:write",
}

_ID = re.compile(r"[a-z0-9][a-z0-9._-]{1,127}")
_VERSION = re.compile(r"[0-9][0-9A-Za-z.+-]{0,63}")
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_SHA512 = re.compile(r"sha512-[A-Za-z0-9+/]+={0,2}")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_SPDX = re.compile(r"[A-Za-z0-9][A-Za-z0-9-.+() ]{0,127}")
_NPM_NAME = re.compile(r"(?:@[a-z0-9._-]+/)?[a-z0-9._-]+")


class PackageError(ValueError):
    """A deterministic package-contract failure."""

    def __init__(self, message: str, code: str = "invalid_package"):
        super().__init__(message)
        self.code = code


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PackageError(f"Duplicate JSON key: {key}", "invalid_json")
        result[key] = value
    return result


def read_json(path: str | Path, *, max_bytes: int = MAX_JSON_BYTES) -> dict[str, Any]:
    source = Path(path).expanduser()
    try:
        raw = source.read_bytes()
    except OSError as error:
        raise PackageError(f"Could not read {source}: {error}", "local_io_error") from error
    if len(raw) > max_bytes:
        raise PackageError(f"JSON input exceeds {max_bytes} bytes", "input_too_large")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackageError(f"Invalid UTF-8 JSON in {source}: {error}", "invalid_json") from error
    if not isinstance(value, dict):
        raise PackageError("Top-level JSON value must be an object", "invalid_json")
    return value


def write_json(
    path: str | Path,
    value: dict[str, Any],
    *,
    force: bool = False,
    compact: bool = False,
) -> None:
    destination = Path(path).expanduser()
    if destination.exists() and not force:
        raise PackageError(f"Refusing to overwrite {destination}; pass --force", "output_exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(
        value,
        indent=None if compact else 2,
        separators=(",", ":") if compact else None,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent, prefix=f".{destination.name}.", delete=False
        ) as handle:
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
            temporary = Path(handle.name)
        os.replace(temporary, destination)
    except OSError as error:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise PackageError(f"Could not write {destination}: {error}", "local_io_error") from error


def _keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PackageError(f"{label} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise PackageError(f"{label} fields differ; missing={missing}, unknown={unknown}")
    return value


def _text(value: Any, label: str, *, maximum: int = 512, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()) or len(value) > maximum:
        raise PackageError(f"{label} must be a{' possibly empty' if allow_empty else ' non-empty'} string <= {maximum} characters")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise PackageError(f"{label} contains an invalid Unicode surrogate") from error
    return value.strip()


def _identifier(value: Any, label: str) -> str:
    rendered = _text(value, label, maximum=128)
    if not _ID.fullmatch(rendered):
        raise PackageError(f"{label} must match {_ID.pattern}")
    return rendered


def _version(value: Any, label: str) -> str:
    rendered = _text(value, label, maximum=64)
    if not _VERSION.fullmatch(rendered) or any(token in rendered for token in ("*", "<", ">", "^", "~", " ")):
        raise PackageError(f"{label} must be one exact version, not a range or tag")
    return rendered


def _utc(value: Any, label: str) -> str:
    rendered = _text(value, label, maximum=20)
    if not _UTC.fullmatch(rendered):
        raise PackageError(f"{label} must use UTC YYYY-MM-DDTHH:MM:SSZ")
    try:
        dt.datetime.strptime(rendered, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise PackageError(f"{label} is not a valid timestamp") from error
    return rendered


def _https(value: Any, label: str) -> str:
    rendered = _text(value, label, maximum=2048)
    parsed = urlsplit(rendered)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise PackageError(f"{label} must be an HTTPS URL without credentials or a fragment")
    return rendered


def _strings(value: Any, label: str, *, allowed: set[str] | None = None, identifiers: bool = False) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise PackageError(f"{label} must be an array of strings")
    rendered = [_identifier(item, f"{label} item") if identifiers else _text(item, f"{label} item", maximum=128) for item in value]
    if len(rendered) != len(set(rendered)):
        raise PackageError(f"{label} contains duplicates")
    if allowed is not None and any(item not in allowed for item in rendered):
        raise PackageError(f"{label} contains an unsupported value")
    return rendered


def _source(value: Any, label: str) -> dict[str, str]:
    source = _keys(value, {"kind", "name", "version", "url", "integrity"}, label)
    kind = _text(source["kind"], f"{label}.kind", maximum=32)
    if kind not in {"npm", "mcpb", "github_archive"}:
        raise PackageError(f"{label}.kind is unsupported")
    name = _text(source["name"], f"{label}.name", maximum=214)
    if kind == "npm" and not _NPM_NAME.fullmatch(name):
        raise PackageError(f"{label}.name is not a valid npm package identity")
    if kind != "npm" and not re.fullmatch(r"[A-Za-z0-9@/_.-]+", name):
        raise PackageError(f"{label}.name contains unsupported characters")
    version = _version(source["version"], f"{label}.version")
    url = _https(source["url"], f"{label}.url")
    integrity = _text(source["integrity"], f"{label}.integrity", maximum=256)
    if kind == "npm":
        if not _SHA512.fullmatch(integrity):
            raise PackageError(f"{label}.integrity must be an npm sha512 SRI value")
        try:
            decoded = base64.b64decode(integrity.removeprefix("sha512-"), validate=True)
        except binascii.Error as error:
            raise PackageError(f"{label}.integrity is invalid base64") from error
        if len(decoded) != 64:
            raise PackageError(f"{label}.integrity must contain a 64-byte SHA-512 digest")
    elif not re.fullmatch(r"sha256-[0-9a-f]{64}", integrity):
        raise PackageError(f"{label}.integrity must be sha256- followed by 64 lowercase hex characters")
    return {"kind": kind, "name": name, "version": version, "url": url, "integrity": integrity}


def _repository(value: Any, label: str) -> dict[str, str]:
    repository = _keys(value, {"url", "commit"}, label)
    commit = _text(repository["commit"], f"{label}.commit", maximum=40)
    if not _COMMIT.fullmatch(commit):
        raise PackageError(f"{label}.commit must be a full lowercase Git SHA-1")
    return {"url": _https(repository["url"], f"{label}.url"), "commit": commit}


def _plugin(value: Any, index: int) -> dict[str, Any]:
    label = f"plugins[{index}]"
    plugin = _keys(
        value,
        {"id", "source", "repository", "permissions", "requires", "conflicts_with"},
        label,
    )
    return {
        "id": _identifier(plugin["id"], f"{label}.id"),
        "source": _source(plugin["source"], f"{label}.source"),
        "repository": _repository(plugin["repository"], f"{label}.repository"),
        "permissions": sorted(_strings(plugin["permissions"], f"{label}.permissions", allowed=PERMISSIONS)),
        "requires": sorted(_strings(plugin["requires"], f"{label}.requires", identifiers=True)),
        "conflicts_with": sorted(_strings(plugin["conflicts_with"], f"{label}.conflicts_with", identifiers=True)),
    }


def _package(value: Any) -> dict[str, str]:
    package = _keys(value, {"id", "name", "version", "description", "license", "created_at"}, "package")
    license_name = _text(package["license"], "package.license", maximum=128)
    if license_name != "NOASSERTION" and not _SPDX.fullmatch(license_name):
        raise PackageError("package.license must be an SPDX expression or NOASSERTION")
    return {
        "id": _identifier(package["id"], "package.id"),
        "name": _text(package["name"], "package.name", maximum=128),
        "version": _version(package["version"], "package.version"),
        "description": _text(package["description"], "package.description", maximum=512, allow_empty=True),
        "license": license_name,
        "created_at": _utc(package["created_at"], "package.created_at"),
    }


def _compatibility(value: Any) -> dict[str, Any]:
    compatibility = _keys(value, {"dsh", "node", "platforms"}, "compatibility")
    platforms = sorted(_strings(compatibility["platforms"], "compatibility.platforms"))
    if not platforms:
        raise PackageError("compatibility.platforms must not be empty")
    return {
        "dsh": _text(compatibility["dsh"], "compatibility.dsh", maximum=128),
        "node": _text(compatibility["node"], "compatibility.node", maximum=128),
        "platforms": platforms,
    }


def _provenance(value: Any) -> dict[str, str]:
    provenance = _keys(value, {"created_by", "source", "evidence"}, "provenance")
    source = _text(provenance["source"], "provenance.source", maximum=32)
    if source not in {"user_composed", "organization_release", "registry_import"}:
        raise PackageError("provenance.source is unsupported")
    evidence = _text(provenance["evidence"], "provenance.evidence", maximum=64)
    if evidence != "metadata_only_unexecuted":
        raise PackageError("This composer only accepts metadata_only_unexecuted evidence")
    return {
        "created_by": _text(provenance["created_by"], "provenance.created_by", maximum=256),
        "source": source,
        "evidence": evidence,
    }


def _canonical_value(value: Any, label: str = "payload") -> None:
    if value is None or isinstance(value, (bool, str)):
        if isinstance(value, str):
            _text(value, label, maximum=max(1, len(value)), allow_empty=True)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _canonical_value(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key.isascii():
                raise PackageError(f"{label} object keys must be ASCII strings")
            _canonical_value(item, f"{label}.{key}")
        return
    raise PackageError(f"{label} contains a number or unsupported JSON value")


def canonical_bytes(value: dict[str, Any]) -> bytes:
    """Return RFC 8785-compatible bytes for the schema's no-number profile."""

    _canonical_value(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _composition_digest(manifest: dict[str, Any]) -> str:
    composition = {
        "compatibility": manifest["compatibility"],
        "load_order": manifest["load_order"],
        "plugins": manifest["plugins"],
    }
    return "sha256:" + hashlib.sha256(canonical_bytes(composition)).hexdigest()


def _validate_relations(plugins: list[dict[str, Any]], load_order: list[str]) -> None:
    ids = [plugin["id"] for plugin in plugins]
    if len(ids) != len(set(ids)):
        raise PackageError("plugins contains duplicate IDs", "composition_conflict")
    if len(load_order) != len(ids) or set(load_order) != set(ids):
        raise PackageError("load_order must contain every plugin ID exactly once", "composition_conflict")
    present = set(ids)
    sources: dict[tuple[str, str], tuple[str, str]] = {}
    for plugin in plugins:
        plugin_id = plugin["id"]
        for relation in plugin["requires"] + plugin["conflicts_with"]:
            if relation == plugin_id:
                raise PackageError(f"{plugin_id} cannot refer to itself", "composition_conflict")
        missing = set(plugin["requires"]) - present
        if missing:
            raise PackageError(f"{plugin_id} requires missing plugins: {sorted(missing)}", "composition_conflict")
        active_conflicts = set(plugin["conflicts_with"]) & present
        if active_conflicts:
            raise PackageError(f"{plugin_id} conflicts with selected plugins: {sorted(active_conflicts)}", "composition_conflict")
        source = plugin["source"]
        identity = (source["kind"], source["name"])
        pin = (source["version"], source["integrity"])
        if identity in sources and sources[identity] != pin:
            raise PackageError(f"Multiple pins selected for {source['kind']}:{source['name']}", "composition_conflict")
        sources[identity] = pin


def compose(spec: dict[str, Any]) -> dict[str, Any]:
    root = _keys(spec, {"schema", "package", "compatibility", "plugins", "load_order", "provenance"}, "spec")
    if root["schema"] != SPEC_SCHEMA:
        raise PackageError(f"spec.schema must be {SPEC_SCHEMA}", "unsupported_schema")
    if not isinstance(root["plugins"], list) or not 1 <= len(root["plugins"]) <= MAX_PLUGINS:
        raise PackageError(f"plugins must contain between 1 and {MAX_PLUGINS} entries")
    plugins = sorted((_plugin(plugin, index) for index, plugin in enumerate(root["plugins"])), key=lambda item: item["id"])
    load_order = _strings(root["load_order"], "load_order", identifiers=True)
    _validate_relations(plugins, load_order)
    manifest: dict[str, Any] = {
        "schema": PACKAGE_SCHEMA,
        "canonicalization": CANONICALIZATION,
        "package": _package(root["package"]),
        "compatibility": _compatibility(root["compatibility"]),
        "plugins": plugins,
        "load_order": load_order,
        "provenance": _provenance(root["provenance"]),
        "composition_digest": "",
    }
    manifest["composition_digest"] = _composition_digest(manifest)
    validate_manifest(manifest)
    return manifest


def validate_manifest(value: dict[str, Any]) -> dict[str, Any]:
    manifest = _keys(
        value,
        {"schema", "canonicalization", "package", "compatibility", "plugins", "load_order", "provenance", "composition_digest"},
        "manifest",
    )
    if manifest["schema"] != PACKAGE_SCHEMA or manifest["canonicalization"] != CANONICALIZATION:
        raise PackageError("Unsupported package schema or canonicalization", "unsupported_schema")
    if not isinstance(manifest["plugins"], list) or not 1 <= len(manifest["plugins"]) <= MAX_PLUGINS:
        raise PackageError(f"plugins must contain between 1 and {MAX_PLUGINS} entries")
    normalized_plugins = [_plugin(plugin, index) for index, plugin in enumerate(manifest["plugins"])]
    if normalized_plugins != sorted(normalized_plugins, key=lambda item: item["id"]):
        raise PackageError("Manifest plugins must be sorted by ID", "noncanonical_manifest")
    normalized = {
        "schema": PACKAGE_SCHEMA,
        "canonicalization": CANONICALIZATION,
        "package": _package(manifest["package"]),
        "compatibility": _compatibility(manifest["compatibility"]),
        "plugins": normalized_plugins,
        "load_order": _strings(manifest["load_order"], "load_order", identifiers=True),
        "provenance": _provenance(manifest["provenance"]),
        "composition_digest": _text(manifest["composition_digest"], "composition_digest", maximum=71),
    }
    _validate_relations(normalized_plugins, normalized["load_order"])
    if not _SHA256.fullmatch(normalized["composition_digest"]):
        raise PackageError("composition_digest must be sha256:<64 lowercase hex>")
    expected = _composition_digest(normalized)
    if normalized["composition_digest"] != expected:
        raise PackageError("composition_digest does not match the selected plugins", "digest_mismatch")
    if normalized != manifest:
        raise PackageError("Manifest is not normalized", "noncanonical_manifest")
    canonical_bytes(normalized)
    return normalized


def _openssl() -> str:
    executable = shutil.which("openssl")
    if not executable:
        raise PackageError("OpenSSL is required for Ed25519 operations", "capability_unavailable")
    return executable


def _run_openssl(arguments: list[str], *, payload: bytes | None = None) -> bytes:
    try:
        result = subprocess.run(
            [_openssl(), *arguments], input=payload, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            check=False, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PackageError(f"OpenSSL failed: {error}", "signature_tool_failed") from error
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise PackageError(f"OpenSSL rejected the key or signature: {detail}", "signature_invalid")
    return result.stdout


def _public_der(key_path: str | Path, *, private: bool) -> bytes:
    arguments = ["pkey", "-in", str(key_path), "-pubout", "-outform", "DER"]
    if not private:
        arguments.insert(3, "-pubin")
    return _run_openssl(arguments)


def _assert_ed25519(key_path: str | Path, *, private: bool) -> None:
    arguments = ["pkey", "-in", str(key_path), "-text_pub", "-noout"]
    if not private:
        arguments.insert(3, "-pubin")
    output = _run_openssl(arguments).decode("utf-8", errors="replace")
    if "ED25519" not in output.upper():
        raise PackageError("Only Ed25519 keys are accepted", "unsupported_key")


def _key_id(der: bytes) -> str:
    return "sha256:" + hashlib.sha256(der).hexdigest()


def _pae(payload: bytes) -> bytes:
    payload_type = PAYLOAD_TYPE.encode("utf-8")
    return b"DSSEv1 " + str(len(payload_type)).encode("ascii") + b" " + payload_type + b" " + str(len(payload)).encode("ascii") + b" " + payload


def _sign_ed25519(private_key: Path, payload: bytes) -> bytes:
    with tempfile.TemporaryDirectory(prefix="dsh-forge-sign-") as temp:
        payload_path = Path(temp) / "payload.bin"
        payload_path.write_bytes(payload)
        return _run_openssl(
            ["pkeyutl", "-sign", "-rawin", "-inkey", str(private_key), "-in", str(payload_path)]
        )


def _verify_ed25519(public_key: Path, signature: Path, payload: bytes) -> None:
    payload_path = public_key.parent / "payload.bin"
    payload_path.write_bytes(payload)
    _run_openssl(
        [
            "pkeyutl", "-verify", "-pubin", "-inkey", str(public_key), "-rawin",
            "-in", str(payload_path), "-sigfile", str(signature),
        ]
    )


def sign_payload(payload: bytes, private_key: str | Path, *, payload_type: str = PAYLOAD_TYPE) -> dict[str, Any]:
    """Wrap already-canonical payload bytes in a signed DSSE envelope."""
    key_path = Path(private_key).expanduser()
    try:
        mode = stat.S_IMODE(key_path.stat().st_mode)
    except OSError as error:
        raise PackageError(f"Could not stat private key {key_path}: {error}", "local_io_error") from error
    if os.name == "posix" and mode & 0o077:
        raise PackageError("Private key must not be readable or writable by group/other", "insecure_key_permissions")
    _assert_ed25519(key_path, private=True)
    der = _public_der(key_path, private=True)
    signature = _sign_ed25519(key_path, _pae(payload))
    return {
        "payloadType": payload_type,
        "payload": base64.b64encode(payload).decode("ascii"),
        "signatures": [{"keyid": _key_id(der), "sig": base64.b64encode(signature).decode("ascii")}],
    }


def sign(manifest: dict[str, Any], private_key: str | Path) -> dict[str, Any]:
    normalized = validate_manifest(manifest)
    key_path = Path(private_key).expanduser()
    try:
        mode = stat.S_IMODE(key_path.stat().st_mode)
    except OSError as error:
        raise PackageError(f"Could not stat private key {key_path}: {error}", "local_io_error") from error
    if os.name == "posix" and mode & 0o077:
        raise PackageError("Private key must not be readable or writable by group/other", "insecure_key_permissions")
    _assert_ed25519(key_path, private=True)
    der = _public_der(key_path, private=True)
    payload = canonical_bytes(normalized)
    signature = _sign_ed25519(key_path, _pae(payload))
    return {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode("ascii"),
        "signatures": [{"keyid": _key_id(der), "sig": base64.b64encode(signature).decode("ascii")}],
    }


def create_trust_root(public_key: str | Path, root_id: str, expires_at: str) -> dict[str, Any]:
    key_path = Path(public_key).expanduser()
    _assert_ed25519(key_path, private=False)
    der = _public_der(key_path, private=False)
    try:
        pem = key_path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as error:
        raise PackageError(f"Could not read public key {key_path}: {error}", "local_io_error") from error
    if len(pem) > 8192 or "BEGIN PUBLIC KEY" not in pem:
        raise PackageError("Public key must be a bounded PEM SubjectPublicKeyInfo document", "unsupported_key")
    return {
        "schema": TRUST_ROOT_SCHEMA,
        "root_id": _identifier(root_id, "root_id"),
        "expires_at": _utc(expires_at, "expires_at"),
        "threshold": 1,
        "keys": [{"keyid": _key_id(der), "algorithm": "ed25519", "public_key_pem": pem.strip() + "\n", "status": "active"}],
    }


def _trust_root(value: dict[str, Any], *, now: dt.datetime | None = None) -> tuple[int, dict[str, str]]:
    root = _keys(value, {"schema", "root_id", "expires_at", "threshold", "keys"}, "trust root")
    if root["schema"] != TRUST_ROOT_SCHEMA:
        raise PackageError("Unsupported trust-root schema", "unsupported_schema")
    _identifier(root["root_id"], "root_id")
    expires = _utc(root["expires_at"], "expires_at")
    instant = now or dt.datetime.now(dt.timezone.utc)
    expiry = dt.datetime.strptime(expires, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    if instant >= expiry:
        raise PackageError("Trust root has expired", "trust_root_expired")
    if type(root["threshold"]) is not int or root["threshold"] < 1:
        raise PackageError("trust root threshold must be a positive integer")
    if not isinstance(root["keys"], list) or not 1 <= len(root["keys"]) <= 32:
        raise PackageError("trust root must contain between 1 and 32 keys")
    keys: dict[str, str] = {}
    seen_keyids: set[str] = set()
    for index, item in enumerate(root["keys"]):
        key = _keys(item, {"keyid", "algorithm", "public_key_pem", "status"}, f"trust root keys[{index}]")
        keyid = _text(key["keyid"], f"trust root keys[{index}].keyid", maximum=71)
        if not _SHA256.fullmatch(keyid) or keyid in seen_keyids:
            raise PackageError("trust root contains an invalid or duplicate key ID")
        seen_keyids.add(keyid)
        if key["algorithm"] != "ed25519" or key["status"] not in {"active", "revoked"}:
            raise PackageError("trust root key algorithm/status is invalid")
        pem = _text(key["public_key_pem"], f"trust root keys[{index}].public_key_pem", maximum=8192)
        with tempfile.TemporaryDirectory(prefix="dsh-forge-root-") as temp:
            public_path = Path(temp) / "public.pem"
            public_path.write_text(pem + ("" if pem.endswith("\n") else "\n"), encoding="ascii")
            _assert_ed25519(public_path, private=False)
            if _key_id(_public_der(public_path, private=False)) != keyid:
                raise PackageError("Trust-root key ID does not match its public key", "trust_root_invalid")
        if key["status"] == "active":
            keys[keyid] = pem + ("" if pem.endswith("\n") else "\n")
    if root["threshold"] > len(keys):
        raise PackageError("trust root threshold exceeds active key count")
    return root["threshold"], keys


def verify_signed_payload(
    envelope: dict[str, Any],
    trust_root: dict[str, Any],
    *,
    payload_type: str = PAYLOAD_TYPE,
    max_payload_bytes: int = MAX_JSON_BYTES,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Verify a DSSE envelope against a trust root and return its raw payload.

    This is the signature boundary only. Callers validate the decoded payload
    against whatever schema their payload type promises.
    """
    signed = _keys(envelope, {"payloadType", "payload", "signatures"}, "DSSE envelope")
    if signed["payloadType"] != payload_type:
        raise PackageError("Unexpected DSSE payload type", "unsupported_schema")
    if not isinstance(signed["payload"], str) or len(signed["payload"]) > max_payload_bytes * 2:
        raise PackageError("Invalid DSSE payload")
    try:
        payload = base64.b64decode(signed["payload"], validate=True)
    except binascii.Error as error:
        raise PackageError("DSSE payload is not valid base64", "invalid_json") from error
    if len(payload) > max_payload_bytes:
        raise PackageError("Decoded DSSE payload is too large", "input_too_large")
    if not isinstance(signed["signatures"], list) or not 1 <= len(signed["signatures"]) <= 32:
        raise PackageError("DSSE envelope must contain between 1 and 32 signatures", "signature_invalid")
    threshold, trusted_keys = _trust_root(trust_root, now=now)
    valid: set[str] = set()
    seen: set[str] = set()
    for index, item in enumerate(signed["signatures"]):
        signature = _keys(item, {"keyid", "sig"}, f"signatures[{index}]")
        keyid = _text(signature["keyid"], f"signatures[{index}].keyid", maximum=71)
        if keyid in seen:
            raise PackageError("DSSE envelope contains duplicate signer IDs", "signature_invalid")
        seen.add(keyid)
        if keyid not in trusted_keys:
            continue
        if not isinstance(signature["sig"], str) or len(signature["sig"]) > 4096:
            raise PackageError("DSSE signature is not a bounded base64 string", "signature_invalid")
        try:
            signature_bytes = base64.b64decode(signature["sig"], validate=True)
        except (binascii.Error, TypeError) as error:
            raise PackageError("DSSE signature is not valid base64", "signature_invalid") from error
        with tempfile.TemporaryDirectory(prefix="dsh-forge-verify-") as temp:
            temp_root = Path(temp)
            public_path = temp_root / "public.pem"
            signature_path = temp_root / "signature.bin"
            public_path.write_text(trusted_keys[keyid], encoding="ascii")
            signature_path.write_bytes(signature_bytes)
            _assert_ed25519(public_path, private=False)
            der = _public_der(public_path, private=False)
            if _key_id(der) != keyid:
                raise PackageError("Trust-root key ID does not match its public key", "trust_root_invalid")
            _verify_ed25519(public_path, signature_path, _pae(payload))
        valid.add(keyid)
    if len(valid) < threshold:
        raise PackageError(f"Only {len(valid)} trusted signatures passed; threshold is {threshold}", "signature_threshold")
    return {
        "payload": payload,
        "valid_signers": sorted(valid),
        "threshold": threshold,
        "payload_digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
    }


def verify(envelope: dict[str, Any], trust_root: dict[str, Any], *, now: dt.datetime | None = None) -> dict[str, Any]:
    verified = verify_signed_payload(envelope, trust_root, payload_type=PAYLOAD_TYPE, now=now)
    payload = verified["payload"]
    try:
        manifest = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PackageError(f"Signed payload is invalid UTF-8 JSON: {error}", "invalid_json") from error
    if not isinstance(manifest, dict):
        raise PackageError("Signed payload must be a JSON object", "invalid_json")
    normalized = validate_manifest(manifest)
    if canonical_bytes(normalized) != payload:
        raise PackageError("Signed payload is not canonical", "noncanonical_manifest")
    return {
        "manifest": normalized,
        "valid_signers": verified["valid_signers"],
        "threshold": verified["threshold"],
        "payload_digest": verified["payload_digest"],
    }
