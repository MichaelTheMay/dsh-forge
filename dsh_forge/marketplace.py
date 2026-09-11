"""Import the public DSH Plugin Marketplace catalog as inert Forge metadata."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Callable, Mapping
import urllib.parse
import urllib.request


DEFAULT_CATALOG_URL = (
    "https://w2112515.github.io/dsh-plugin-marketplace/"
    "plugin-marketplace/catalog-v1.json"
)
MAX_CATALOG_BYTES = 15_000_000
MAX_ENTRIES = 50_000


class MarketplaceError(ValueError):
    """The external marketplace response was unavailable or invalid."""


def _canonical_json(value: Any) -> str:
    """Match the marketplace v1 recursively sorted JSON digest profile."""

    if value is None or isinstance(value, (bool, str)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and math.isfinite(value):
        if value.is_integer():
            return str(int(value))
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if isinstance(value, list):
        return "[" + ",".join(_canonical_json(item) for item in value) + "]"
    if isinstance(value, dict) and all(isinstance(key, str) for key in value):
        return "{" + ",".join(
            json.dumps(key, ensure_ascii=False) + ":" + _canonical_json(value[key])
            for key in sorted(value)
        ) + "}"
    raise MarketplaceError("Catalog contains a non-JSON value")


def catalog_digest(catalog: Mapping[str, Any]) -> str:
    unsigned = dict(catalog)
    integrity = unsigned.get("integrity")
    if not isinstance(integrity, dict) or integrity.get("algorithm") != "sha256":
        raise MarketplaceError("Catalog must declare SHA-256 logical integrity")
    unsigned["integrity"] = {**integrity, "digest": ""}
    return hashlib.sha256(_canonical_json(unsigned).encode("utf-8")).hexdigest()


def _text(value: Any, label: str, *, nullable: bool = False, limit: int = 10_000) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value or len(value) > limit:
        raise MarketplaceError(f"Invalid {label}")
    return value


def validate_catalog(catalog: Mapping[str, Any]) -> None:
    if catalog.get("schemaVersion") != 1:
        raise MarketplaceError("Unsupported marketplace catalog schema")
    entries = catalog.get("entries")
    summary = catalog.get("summary")
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise MarketplaceError("Invalid marketplace entry list")
    if not isinstance(summary, dict) or summary.get("entryCount") != len(entries):
        raise MarketplaceError("Catalog entry count does not match its summary")
    expected = (catalog.get("integrity") or {}).get("digest")
    if not isinstance(expected, str) or len(expected) != 64 or catalog_digest(catalog) != expected:
        raise MarketplaceError("Catalog integrity digest does not match")

    seen: set[str] = set()
    invalid = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise MarketplaceError("Catalog entry must be an object")
        repository_id = _text(entry.get("repositoryId"), "repository ID", limit=32)
        if not repository_id.isdigit() or int(repository_id) > 9_223_372_036_854_775_807 or repository_id in seen:
            raise MarketplaceError("Catalog contains an invalid or duplicate repository ID")
        seen.add(repository_id)
        repository = entry.get("repository")
        package = entry.get("package")
        validation = entry.get("validation")
        if not isinstance(repository, dict) or not isinstance(package, dict) or not isinstance(validation, dict):
            raise MarketplaceError("Catalog entry is missing repository, package, or validation metadata")
        full_name = _text(repository.get("fullName"), "repository name", limit=256)
        parts = full_name.split("/")
        if len(parts) != 2 or any(not part or not all(character.isalnum() or character in "._-" for character in part) for part in parts):
            raise MarketplaceError("Catalog repository name must be owner/repository")
        url = _text(repository.get("url"), "repository URL", limit=2048)
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.port is not None or parsed.query or parsed.fragment:
            raise MarketplaceError("Catalog repository URL must be canonical GitHub HTTPS")
        if parsed.path.strip("/") != full_name:
            raise MarketplaceError("Catalog repository URL and name disagree")
        commit = repository.get("commitSha")
        if commit is not None and (
            not isinstance(commit, str)
            or len(commit) != 40
            or any(character not in "0123456789abcdef" for character in commit)
        ):
            raise MarketplaceError("Catalog entry has an invalid commit")
        status = validation.get("status")
        if status not in {"valid", "invalid", "archived"}:
            raise MarketplaceError("Catalog entry has an invalid validation status")
        invalid += status != "valid"
        if not isinstance(entry.get("stars"), int) or isinstance(entry.get("stars"), bool) or entry["stars"] < 0:
            raise MarketplaceError("Catalog entry has an invalid star count")
        labels = [entry.get("topics"), entry.get("keywords")]
        if any(
            not isinstance(group, list)
            or len(group) > 200
            or any(not isinstance(item, str) or not item or len(item) > 128 for item in group)
            for group in labels
        ):
            raise MarketplaceError("Catalog entry has invalid discovery labels")
        for key, limit in (("name", 256), ("version", 128), ("description", 10_000), ("license", 128)):
            value = package.get(key)
            if value is not None and (not isinstance(value, str) or not value or len(value) > limit):
                raise MarketplaceError(f"Catalog entry has invalid package {key}")
        risks = entry.get("riskSignals") or []
        if not isinstance(risks, list) or len(risks) > 32 or any(
            not isinstance(item, str) or not item or len(item) > 256 for item in risks
        ):
            raise MarketplaceError("Catalog entry has invalid risk signals")
    if summary.get("invalidEntryCount") != invalid:
        raise MarketplaceError("Catalog invalid-entry count does not match its summary")


def normalize_catalog(catalog: Mapping[str, Any], source_url: str) -> dict[str, Any]:
    """Convert a verified marketplace feed into the launcher's neutral snapshot shape."""

    validate_catalog(catalog)
    plugins = []
    for entry in catalog["entries"]:
        repository = entry["repository"]
        package = entry["package"]
        validation = entry["validation"]
        full_name = repository["fullName"]
        owner, name = full_name.split("/", 1)
        commit = repository.get("commitSha")
        description = package.get("description") or "No plugin description was provided."
        labels = list(dict.fromkeys([*(entry.get("topics") or []), *(entry.get("keywords") or [])]))[:100]
        package_record = None
        if package.get("name") and package.get("version"):
            package_record = {
                "registry": "external catalog",
                "name": package["name"],
                "version": package["version"],
                "url": repository["url"],
                "integrity": None,
            }
        plugins.append({
            "artifact_id": "github:" + entry["repositoryId"],
            "github_id": int(entry["repositoryId"]),
            "node_id": None,
            "full_name": full_name,
            "owner": owner,
            "name": name,
            "artifact_type": "plugin",
            "source": "dsh-plugin-marketplace/v1",
            "repository_url": repository["url"],
            "description": description[:10_000],
            "description_origin": "external_marketplace_catalog",
            "topics": labels,
            "language": repository.get("language"),
            "github_stars": entry["stars"],
            "seed_rank": None,
            "forks_count": repository.get("forks"),
            "pushed_at": entry.get("lastCodePushAt"),
            "archived": bool(repository.get("archived")),
            "default_branch": repository.get("defaultBranch"),
            "head_sha": commit,
            "parent_repository": None,
            "source_repository": full_name,
            "license": {
                "spdx": package.get("license"),
                "status": "publisher_reported" if package.get("license") else "unknown",
            },
            "compatibility": {
                "declared_dsh_range": None,
                "observed_base": None,
                "summary": "Marketplace compatibility: " + str(entry.get("compatibility") or "unknown"),
            },
            "package": package_record,
            "risk_signals": list(entry.get("riskSignals") or [])[:32],
            "installability": entry.get("installability") or "browse-only",
            "analysis_status": "external_static_validation",
            "verification": {"metadata_only": True, "executed": False, "security_verified": False},
            "external_validation": {
                "status": validation["status"],
                "code": validation.get("code"),
                "indexed_at": entry.get("indexedAt"),
            },
        })

    generated_at = _text(catalog.get("generatedAt"), "generation time", limit=64)
    digest = catalog["integrity"]["digest"]
    return {
        "schema_version": 1,
        "snapshot_id": "dsh-plugin-marketplace-" + digest[:16],
        "fetched_at": generated_at,
        "completed_at": generated_at,
        "upstream": "deepseek-ai/deepseek-harness",
        "source_url": source_url,
        "selection": {
            "method": "external_marketplace_full_catalog",
            "topic": catalog.get("topic"),
            "limit": len(plugins),
        },
        "provenance": {
            "method": "dsh-plugin-marketplace/v1",
            "logical_integrity": "sha256:" + digest,
            "signature_status": "unsigned_external_catalog",
            "generated_at": generated_at,
            "scanner_version": catalog.get("scannerVersion"),
            "note": "Upstream logical integrity verified; no Forge signature or execution trust implied.",
        },
        "entries": [],
        "supplemental_entries": plugins,
        "package_entries": [],
    }


def fetch_catalog(
    url: str = DEFAULT_CATALOG_URL,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
        raise MarketplaceError("Marketplace URL must be credential-free HTTPS")
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "DSH-Forge-plugin-catalog/1"},
    )
    with opener(request, timeout=60) as response:
        final = urllib.parse.urlsplit(response.geturl())
        if final.scheme != "https" or final.username or final.password:
            raise MarketplaceError("Marketplace redirect left credential-free HTTPS")
        declared = response.headers.get("Content-Length")
        if declared:
            try:
                declared_size = int(declared)
            except ValueError:
                raise MarketplaceError("Marketplace returned an invalid Content-Length") from None
            if declared_size < 0 or declared_size > MAX_CATALOG_BYTES:
                raise MarketplaceError("Marketplace catalog exceeds the download limit")
        payload = response.read(MAX_CATALOG_BYTES + 1)
        final_url = response.geturl()
    if len(payload) > MAX_CATALOG_BYTES:
        raise MarketplaceError("Marketplace catalog exceeds the download limit")
    try:
        catalog = json.loads(
            payload.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(MarketplaceError(f"Invalid JSON number: {value}")),
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MarketplaceError("Marketplace catalog is not valid UTF-8 JSON") from error
    if not isinstance(catalog, dict):
        raise MarketplaceError("Marketplace catalog must be a JSON object")
    return normalize_catalog(catalog, final_url)
