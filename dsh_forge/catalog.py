"""Bounded, deterministic package-catalog ingestion.

Directory records are discovery leads.  Catalog packages are emitted only when
every component resolves to the separately captured GitHub/npm/MCP metadata in
the launcher seed.  No network access, archive handling, installation, or code
execution occurs here.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


SOURCE_SCHEMA = "dsh-forge.catalog-sources/v1"
FEED_SCHEMA = "dsh-forge.catalog-feed/v1"
PACKAGE_SCHEMA = "dsh-forge.catalog-package/v1"
_SHA = re.compile(r"^[0-9a-f]{40}$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")
_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?(?:\+[0-9A-Za-z][0-9A-Za-z.-]*)?$")
_RISKS = {"low", "medium", "medium-high", "high", "critical"}
_SURFACES = {"web", "headless", "tui", "mcp"}
_COMPATIBILITY = {"declared", "unknown", "incompatible"}
_DIRECTORY_KINDS = {"normalized_json", "curated_repository", "official_discussions", "registry"}
_DIRECTORY_TRUST = {"lead_only", "authoritative_metadata"}


class CatalogError(ValueError):
    """A catalog source or generated feed violates the v1 contract."""


def _exact_keys(value: Any, required: Iterable[str], context: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise CatalogError(f"{context} must be an object")
    expected = set(required)
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise CatalogError(f"{context} fields disagree (missing={missing}, extra={extra})")
    return value


def _strings(value: Any, *, context: str, minimum: int = 0, maximum: int = 32) -> List[str]:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise CatalogError(f"{context} must contain {minimum}..{maximum} values")
    if any(not isinstance(item, str) or not item or len(item) > 2048 for item in value):
        raise CatalogError(f"{context} contains an invalid string")
    if len(set(value)) != len(value):
        raise CatalogError(f"{context} must not contain duplicates")
    return value


def _https(value: Any, context: str) -> str:
    if not isinstance(value, str) or len(value) > 2048 or not value.startswith("https://"):
        raise CatalogError(f"{context} must be a bounded HTTPS URL")
    return value


def _canonical_digest(packages: List[Dict[str, Any]]) -> str:
    encoded = json.dumps(packages, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def load_json(path: Path, *, max_bytes: int) -> Dict[str, Any]:
    if path.stat().st_size > max_bytes:
        raise CatalogError(f"{path} exceeds the {max_bytes}-byte input limit")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogError(f"Cannot read JSON from {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CatalogError(f"{path} must contain a JSON object")
    return value


def validate_sources(source: Dict[str, Any]) -> None:
    _exact_keys(source, {"schema", "captured_at", "directories", "recipes"}, "catalog sources")
    if source["schema"] != SOURCE_SCHEMA or not isinstance(source["captured_at"], str) or not _TIME.fullmatch(source["captured_at"]):
        raise CatalogError("Unsupported source schema or timestamp")
    directories = source["directories"]
    if not isinstance(directories, list) or len(directories) > 32:
        raise CatalogError("At most 32 directory sources are accepted")
    directory_ids = set()
    for index, item in enumerate(directories):
        _exact_keys(item, {"id", "name", "url", "kind", "revision", "trust", "coverage"}, f"directory[{index}]")
        if not isinstance(item["id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,63}", item["id"]) or item["id"] in directory_ids:
            raise CatalogError("Directory IDs must be unique stable identifiers")
        directory_ids.add(item["id"])
        if not isinstance(item["name"], str) or not item["name"] or len(item["name"]) > 128:
            raise CatalogError("Invalid directory name")
        _https(item["url"], "directory URL")
        if item["kind"] not in _DIRECTORY_KINDS or item["trust"] not in _DIRECTORY_TRUST:
            raise CatalogError("Unsupported directory kind or trust class")
        if item["revision"] is not None and (not isinstance(item["revision"], str) or not _SHA.fullmatch(item["revision"])):
            raise CatalogError("Directory revisions must be immutable Git commits")
        if not isinstance(item["coverage"], str) or not item["coverage"] or len(item["coverage"]) > 256:
            raise CatalogError("Directory coverage must be explicit and bounded")

    recipes = source["recipes"]
    if not isinstance(recipes, list) or len(recipes) > 10_000:
        raise CatalogError("At most 10,000 recipes are accepted")
    slugs, ranks = set(), set()
    for index, recipe in enumerate(recipes):
        _exact_keys(
            recipe,
            {"slug", "name", "summary", "kind", "rank", "featured", "publisher", "components", "taxonomy", "compatibility", "risk", "directory_ids"},
            f"recipe[{index}]",
        )
        slug = recipe["slug"]
        if not isinstance(slug, str) or not _SLUG.fullmatch(slug) or slug in slugs:
            raise CatalogError("Package slugs must be unique and route-safe")
        slugs.add(slug)
        if type(recipe["rank"]) is not int or recipe["rank"] <= 0 or recipe["rank"] in ranks:
            raise CatalogError("Package ranks must be unique positive integers")
        ranks.add(recipe["rank"])
        if type(recipe["featured"]) is not bool or recipe["kind"] not in {"plugin_stack", "single_plugin"}:
            raise CatalogError("Invalid package display metadata")
        for field, limit in (("name", 96), ("summary", 512)):
            if not isinstance(recipe[field], str) or not recipe[field] or len(recipe[field]) > limit:
                raise CatalogError(f"Invalid package {field}")
        publisher = _exact_keys(recipe["publisher"], {"id", "name", "kind"}, "publisher")
        if publisher["kind"] not in {"curator", "community"} or not all(isinstance(publisher[k], str) and publisher[k] for k in ("id", "name")):
            raise CatalogError("Invalid package publisher")
        components = recipe["components"]
        if not isinstance(components, list) or not 1 <= len(components) <= 128:
            raise CatalogError("Package recipes require 1..128 components")
        if recipe["kind"] == "single_plugin" and len(components) != 1:
            raise CatalogError("single_plugin packages require exactly one component")
        if recipe["kind"] == "plugin_stack" and len(components) < 2:
            raise CatalogError("plugin_stack packages require at least two components")
        component_ids = set()
        for component in components:
            _exact_keys(component, {"artifact_id", "role"}, "recipe component")
            if not isinstance(component["artifact_id"], str) or not re.fullmatch(r"github:[1-9][0-9]*", component["artifact_id"]) or component["artifact_id"] in component_ids:
                raise CatalogError("Recipe component IDs must be unique GitHub artifact IDs")
            component_ids.add(component["artifact_id"])
            if not isinstance(component["role"], str) or not component["role"] or len(component["role"]) > 160:
                raise CatalogError("Invalid component role")
        _strings(recipe["taxonomy"], context="package taxonomy", minimum=1)
        compatibility = _exact_keys(recipe["compatibility"], {"status", "harness_versions", "node", "surfaces", "summary"}, "compatibility")
        if compatibility["status"] not in _COMPATIBILITY:
            raise CatalogError("Only declared, unknown, or incompatible compatibility may enter this unverified feed")
        _strings(compatibility["harness_versions"], context="Harness versions")
        surfaces = _strings(compatibility["surfaces"], context="surfaces", minimum=1, maximum=8)
        if any(surface not in _SURFACES for surface in surfaces):
            raise CatalogError("Unsupported Harness surface")
        if compatibility["node"] is not None and (not isinstance(compatibility["node"], str) or len(compatibility["node"]) > 64):
            raise CatalogError("Invalid Node compatibility range")
        if not isinstance(compatibility["summary"], str) or not compatibility["summary"] or len(compatibility["summary"]) > 512:
            raise CatalogError("Compatibility summary is required")
        risk = _exact_keys(recipe["risk"], {"level", "permissions", "notes"}, "risk")
        if risk["level"] not in _RISKS:
            raise CatalogError("Unsupported risk level")
        _strings(risk["permissions"], context="risk permissions")
        if not isinstance(risk["notes"], str) or not risk["notes"] or len(risk["notes"]) > 512:
            raise CatalogError("Risk notes are required")
        used_directories = _strings(recipe["directory_ids"], context="directory IDs")
        if any(item not in directory_ids for item in used_directories):
            raise CatalogError("Recipe references an unknown directory source")
    if ranks != set(range(1, len(recipes) + 1)):
        raise CatalogError("Package ranks must be contiguous")


def _validate_plugin_component(plugin: Dict[str, Any]) -> None:
    if plugin.get("artifact_type") != "plugin" or plugin.get("verification") != {
        "metadata_only": True,
        "executed": False,
        "security_verified": False,
    }:
        raise CatalogError("Package components must be unexecuted plugin metadata")
    package = plugin.get("package")
    if not isinstance(package, dict) or package.get("registry") not in {"npm", "mcpb"}:
        raise CatalogError("Package components require exact registry metadata")
    if not isinstance(package.get("version"), str) or not _VERSION.fullmatch(package["version"]):
        raise CatalogError("Package components require an exact version")
    integrity = package.get("integrity", "")
    if not (re.fullmatch(r"sha512-[A-Za-z0-9+/]+={0,2}", integrity) or re.fullmatch(r"sha256-[0-9a-f]{64}", integrity)):
        raise CatalogError("Package components require an immutable integrity value")
    if not _SHA.fullmatch(plugin.get("head_sha", "")):
        raise CatalogError("Package components require an immutable repository commit")
    _https(plugin.get("repository_url"), "component repository URL")
    _https(package.get("url"), "component package URL")
    compatibility = plugin.get("compatibility")
    if not isinstance(compatibility, dict) or not isinstance(compatibility.get("summary"), str) or not compatibility["summary"]:
        raise CatalogError("Package components require an explicit compatibility summary")


def build_feed(source: Dict[str, Any], plugin_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    validate_sources(source)
    plugins = plugin_snapshot.get("supplemental_entries")
    if not isinstance(plugins, list) or len(plugins) > 10_000:
        raise CatalogError("Invalid plugin metadata snapshot")
    by_id = {}
    for plugin in plugins:
        _validate_plugin_component(plugin)
        artifact_id = plugin.get("artifact_id")
        if artifact_id in by_id:
            raise CatalogError("Duplicate plugin identity")
        by_id[artifact_id] = plugin

    packages = []
    for recipe in sorted(source["recipes"], key=lambda item: item["rank"]):
        components = []
        expressions = []
        authoritative_sources = []
        for requested in recipe["components"]:
            try:
                plugin = by_id[requested["artifact_id"]]
            except KeyError as exc:
                raise CatalogError(f"Unknown package component: {requested['artifact_id']}") from exc
            license_expression = plugin.get("license", {}).get("spdx")
            if isinstance(license_expression, str) and license_expression:
                expressions.append(license_expression)
            package = plugin["package"]
            authoritative_sources.extend([
                plugin["repository_url"] + "/tree/" + plugin["head_sha"],
                package["url"],
            ])
            if plugin.get("discussion_url"):
                authoritative_sources.append(plugin["discussion_url"])
            components.append({
                "artifact_id": plugin["artifact_id"],
                "role": requested["role"],
                "package": {
                    "registry": package["registry"],
                    "name": package["name"],
                    "version": package["version"],
                    "integrity": package["integrity"],
                    "url": package["url"],
                },
                "repository": {
                    "full_name": plugin["full_name"],
                    "url": plugin["repository_url"],
                    "commit": plugin["head_sha"],
                },
                "compatibility": plugin["compatibility"]["summary"],
            })
        expressions = sorted(set(expressions)) or ["UNKNOWN"]
        packages.append({
            "schema": PACKAGE_SCHEMA,
            "id": "catalog-package:" + recipe["slug"],
            "slug": recipe["slug"],
            "name": recipe["name"],
            "summary": recipe["summary"],
            "kind": recipe["kind"],
            "rank": recipe["rank"],
            "featured": recipe["featured"],
            "publisher": recipe["publisher"],
            "components": components,
            "taxonomy": recipe["taxonomy"],
            "compatibility": recipe["compatibility"],
            "license": {
                "status": "unknown" if expressions == ["UNKNOWN"] else ("mixed" if len(expressions) > 1 else "reported"),
                "expressions": expressions,
            },
            "risk": recipe["risk"],
            "provenance": {
                "directory_ids": recipe["directory_ids"],
                "authoritative_sources": sorted(set(authoritative_sources)),
                "claims_verified": False,
            },
            "verification": {
                "metadata_reviewed": True,
                "artifacts_acquired": False,
                "installed": False,
                "executed": False,
                "sandbox_verified": False,
            },
            "acquisition": {
                "enabled": False,
                "label": "Acquire verified bytes",
                "status": "requires_signed_dsse",
                "reason": "No trusted DSSE envelope is published for this catalog recipe; installation and execution are not authorized.",
            },
            "page": {"route": "#packages/" + recipe["slug"]},
            "updated_at": source["captured_at"],
        })
    feed = {
        "schema": FEED_SCHEMA,
        "generated_at": source["captured_at"],
        "source_schema": SOURCE_SCHEMA,
        "signature_status": "unsigned_development_seed",
        "packages": packages,
        "catalog_digest": _canonical_digest(packages),
    }
    validate_feed(feed)
    return feed


def validate_feed(feed: Dict[str, Any]) -> None:
    _exact_keys(feed, {"schema", "generated_at", "source_schema", "signature_status", "packages", "catalog_digest"}, "catalog feed")
    if feed["schema"] != FEED_SCHEMA or feed["source_schema"] != SOURCE_SCHEMA:
        raise CatalogError("Unsupported catalog feed schema")
    if feed["signature_status"] != "unsigned_development_seed":
        raise CatalogError("A production signed-feed verifier is not implemented")
    if not isinstance(feed["generated_at"], str) or not _TIME.fullmatch(feed["generated_at"]):
        raise CatalogError("Invalid catalog generation timestamp")
    packages = feed["packages"]
    if not isinstance(packages, list) or len(packages) > 10_000:
        raise CatalogError("Invalid catalog package collection")
    ids, slugs, ranks = set(), set(), set()
    for index, package in enumerate(packages):
        _exact_keys(
            package,
            {"schema", "id", "slug", "name", "summary", "kind", "rank", "featured", "publisher", "components", "taxonomy", "compatibility", "license", "risk", "provenance", "verification", "acquisition", "page", "updated_at"},
            f"package[{index}]",
        )
        if package["schema"] != PACKAGE_SCHEMA or not _SLUG.fullmatch(package["slug"]):
            raise CatalogError("Invalid catalog package identity")
        if package["id"] != "catalog-package:" + package["slug"] or package["id"] in ids or package["slug"] in slugs:
            raise CatalogError("Duplicate or inconsistent catalog package identity")
        ids.add(package["id"]); slugs.add(package["slug"])
        for field, limit in (("name", 96), ("summary", 512)):
            if not isinstance(package[field], str) or not package[field] or len(package[field]) > limit:
                raise CatalogError(f"Invalid package {field}")
        if package["kind"] not in {"plugin_stack", "single_plugin"} or type(package["featured"]) is not bool:
            raise CatalogError("Invalid package display metadata")
        if type(package["rank"]) is not int or package["rank"] <= 0 or package["rank"] in ranks:
            raise CatalogError("Invalid package rank")
        ranks.add(package["rank"])
        publisher = _exact_keys(package["publisher"], {"id", "name", "kind"}, "package publisher")
        if publisher["kind"] not in {"curator", "community"} or not isinstance(publisher["id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,127}", publisher["id"]):
            raise CatalogError("Invalid package publisher")
        if not isinstance(publisher["name"], str) or not publisher["name"] or len(publisher["name"]) > 128:
            raise CatalogError("Invalid package publisher name")
        _strings(package["taxonomy"], context="package taxonomy", minimum=1)
        page = _exact_keys(package["page"], {"route"}, "package page")
        if page != {"route": "#packages/" + package["slug"]}:
            raise CatalogError("Dedicated package route disagrees with its slug")
        verification = _exact_keys(package["verification"], {"metadata_reviewed", "artifacts_acquired", "installed", "executed", "sandbox_verified"}, "package verification")
        if verification != {"metadata_reviewed": True, "artifacts_acquired": False, "installed": False, "executed": False, "sandbox_verified": False}:
            raise CatalogError("Unsigned catalog seeds cannot claim acquisition, installation, execution, or sandbox verification")
        acquisition = _exact_keys(package["acquisition"], {"enabled", "label", "status", "reason"}, "package acquisition")
        if acquisition["enabled"] is not False or acquisition["label"] != "Acquire verified bytes" or acquisition["status"] != "requires_signed_dsse":
            raise CatalogError("Catalog acquisition must remain fail-closed until signed publication exists")
        if not isinstance(acquisition["reason"], str) or not acquisition["reason"] or len(acquisition["reason"]) > 512:
            raise CatalogError("Package acquisition requires an explicit bounded reason")
        provenance = _exact_keys(package["provenance"], {"directory_ids", "authoritative_sources", "claims_verified"}, "package provenance")
        if provenance["claims_verified"] is not False:
            raise CatalogError("Directory and publisher claims are not verification")
        _strings(provenance["directory_ids"], context="package directory IDs")
        sources = _strings(provenance["authoritative_sources"], context="authoritative sources", minimum=1, maximum=256)
        for source in sources:
            _https(source, "authoritative source")
        compatibility = _exact_keys(package["compatibility"], {"status", "harness_versions", "node", "surfaces", "summary"}, "package compatibility")
        if compatibility["status"] not in _COMPATIBILITY:
            raise CatalogError("Unverified feed contains an unsupported compatibility status")
        host_versions = _strings(compatibility["harness_versions"], context="Harness versions")
        if any(not _VERSION.fullmatch(version) for version in host_versions):
            raise CatalogError("Harness versions must be exact semantic versions")
        if compatibility["node"] is not None and (not isinstance(compatibility["node"], str) or not compatibility["node"] or len(compatibility["node"]) > 64):
            raise CatalogError("Invalid Node compatibility range")
        surfaces = _strings(compatibility["surfaces"], context="package surfaces", minimum=1, maximum=8)
        if any(surface not in _SURFACES for surface in surfaces):
            raise CatalogError("Unsupported Harness surface")
        if not isinstance(compatibility["summary"], str) or not compatibility["summary"] or len(compatibility["summary"]) > 512:
            raise CatalogError("Compatibility summary is required")
        license_metadata = _exact_keys(package["license"], {"status", "expressions"}, "package license")
        if license_metadata["status"] not in {"reported", "mixed", "unknown"}:
            raise CatalogError("Invalid package license status")
        _strings(license_metadata["expressions"], context="license expressions", minimum=1)
        risk = _exact_keys(package["risk"], {"level", "permissions", "notes"}, "package risk")
        if risk["level"] not in _RISKS:
            raise CatalogError("Invalid package risk")
        _strings(risk["permissions"], context="risk permissions")
        if not isinstance(risk["notes"], str) or not risk["notes"] or len(risk["notes"]) > 512:
            raise CatalogError("Risk notes are required")
        if not isinstance(package["updated_at"], str) or not _TIME.fullmatch(package["updated_at"]):
            raise CatalogError("Invalid package update timestamp")
        components = package["components"]
        if not isinstance(components, list) or not 1 <= len(components) <= 128:
            raise CatalogError("Invalid package components")
        if package["kind"] == "single_plugin" and len(components) != 1:
            raise CatalogError("single_plugin packages require exactly one component")
        if package["kind"] == "plugin_stack" and len(components) < 2:
            raise CatalogError("plugin_stack packages require at least two components")
        component_ids = set()
        for component in components:
            _exact_keys(component, {"artifact_id", "role", "package", "repository", "compatibility"}, "package component")
            if not isinstance(component["artifact_id"], str) or not re.fullmatch(r"github:[1-9][0-9]*", component["artifact_id"]):
                raise CatalogError("Invalid package component identity")
            if component["artifact_id"] in component_ids:
                raise CatalogError("Duplicate package component")
            component_ids.add(component["artifact_id"])
            for field in ("role", "compatibility"):
                if not isinstance(component[field], str) or not component[field] or len(component[field]) > 512:
                    raise CatalogError(f"Invalid component {field}")
            repository = _exact_keys(component["repository"], {"full_name", "url", "commit"}, "component repository")
            if not isinstance(repository["full_name"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository["full_name"]):
                raise CatalogError("Invalid component repository identity")
            if repository["url"] != "https://github.com/" + repository["full_name"]:
                raise CatalogError("Component repository URL must be canonical")
            if not _SHA.fullmatch(repository["commit"]):
                raise CatalogError("Package component repository is not pinned")
            registry_package = _exact_keys(component["package"], {"registry", "name", "version", "integrity", "url"}, "component package")
            if registry_package["registry"] not in {"npm", "mcpb"} or not isinstance(registry_package["name"], str) or not registry_package["name"] or len(registry_package["name"]) > 214:
                raise CatalogError("Invalid component package identity")
            if not isinstance(registry_package["version"], str) or not _VERSION.fullmatch(registry_package["version"]):
                raise CatalogError("Component package version must be exact")
            _https(registry_package["url"], "component package URL")
            integrity = registry_package["integrity"]
            if not (re.fullmatch(r"sha512-[A-Za-z0-9+/]+={0,2}", integrity) or re.fullmatch(r"sha256-[0-9a-f]{64}", integrity)):
                raise CatalogError("Package component bytes are not pinned")
    if ranks != set(range(1, len(packages) + 1)):
        raise CatalogError("Package ranks must be contiguous")
    if feed["catalog_digest"] != _canonical_digest(packages):
        raise CatalogError("Catalog digest does not match canonical package metadata")


def directory_leads(payload: Dict[str, Any], *, source_id: str, max_entries: int = 5_000) -> List[Dict[str, Any]]:
    """Normalize a bounded DSH Get-style snapshot into non-authoritative leads.

    This adapter deliberately omits install commands and verification labels.
    Exact versions, commits, licenses, and integrity must be re-enriched from
    authoritative sources before a lead can become a component.
    """
    plugins = payload.get("plugins")
    if not isinstance(plugins, list) or len(plugins) > max_entries:
        raise CatalogError(f"Directory snapshot must contain at most {max_entries} plugin records")
    leads = []
    seen = set()
    for item in plugins:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str):
            continue
        match = re.fullmatch(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)(?:/.*)?", url)
        if not match:
            continue
        repository = match.group(1) + "/" + match.group(2)
        if repository.lower() in seen:
            continue
        seen.add(repository.lower())
        package_name = item.get("npm") if isinstance(item.get("npm"), str) else None
        leads.append({"source_id": source_id, "repository": repository, "package_name": package_name})
    return sorted(leads, key=lambda item: item["repository"].lower())
