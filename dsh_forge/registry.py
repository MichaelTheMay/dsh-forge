"""Source-neutral registry assembly and bounded GitHub fork discovery."""

from __future__ import annotations

import datetime as dt
from email.utils import parsedate_to_datetime
import hashlib
import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


GITHUB_API = "https://api.github.com"
GITHUB_API_VERSION = "2026-03-10"
DEFAULT_UPSTREAM = "deepseek-ai/deepseek-harness"
MAX_GITHUB_PAGE_BYTES = 8 * 1024 * 1024
MAX_FORK_PAGES = 500
MAX_FORKS = 50_000

_SLUG = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_NEXT = re.compile(r'<([^>]+)>;\s*rel="next"')


class RegistryError(ValueError):
    """An external registry response could not be safely normalized."""


def _github_url(url: str) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.github.com"
        or parsed.port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise RegistryError("GitHub pagination or redirect left the public API")


def _github_json(
    url: str,
    *,
    token: str | None,
    opener: Callable[..., Any],
) -> tuple[Any, dict[str, str | None]]:
    _github_url(url)
    if token is not None and (
        not isinstance(token, str)
        or not token
        or len(token) > 4096
        or any(ord(character) < 33 or ord(character) == 127 for character in token)
    ):
        raise RegistryError("GitHub token is not a bounded HTTP credential")
    headers = {
        "Accept": "application/vnd.github+json",
        "Accept-Encoding": "identity",
        "User-Agent": "DSH-Forge-registry-indexer/1",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url, headers=headers)
    try:
        with opener(request, timeout=60) as response:
            final_url = response.geturl()
            _github_url(final_url)
            declared = response.headers.get("Content-Length")
            if declared:
                try:
                    size = int(declared)
                except ValueError:
                    raise RegistryError("GitHub returned an invalid Content-Length") from None
                if size < 0 or size > MAX_GITHUB_PAGE_BYTES:
                    raise RegistryError("GitHub metadata page exceeds the byte limit")
            payload = response.read(MAX_GITHUB_PAGE_BYTES + 1)
            metadata = {
                "date": response.headers.get("Date"),
                "etag": response.headers.get("ETag"),
                "link": response.headers.get("Link"),
                "rate_limit_remaining": response.headers.get("X-RateLimit-Remaining"),
            }
    except RegistryError:
        raise
    except OSError as error:
        raise RegistryError(f"GitHub metadata request failed: {error}") from error
    if len(payload) > MAX_GITHUB_PAGE_BYTES:
        raise RegistryError("GitHub metadata page exceeds the byte limit")
    try:
        return json.loads(payload.decode("utf-8")), metadata
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RegistryError("GitHub metadata is not valid UTF-8 JSON") from error


def _next_url(header: str | None) -> str | None:
    if not header:
        return None
    match = _NEXT.search(header)
    if not match:
        return None
    url = match.group(1)
    _github_url(url)
    return url


def _count(root: Mapping[str, Any]) -> int:
    value = root.get("network_count", root.get("forks_count"))
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise RegistryError("GitHub root metadata has no valid fork-network count")
    return value


def _timestamp(date: str | None) -> str:
    try:
        parsed = parsedate_to_datetime(date) if date else None
    except (TypeError, ValueError):
        parsed = None
    instant = parsed or dt.datetime.now(dt.timezone.utc)
    return instant.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fork(
    repo: Mapping[str, Any],
    upstream: str,
    parent: str | None = None,
    source_branch: str | None = None,
) -> dict[str, Any]:
    identity = repo.get("id")
    node_id = repo.get("node_id")
    slug = repo.get("full_name")
    owner = repo.get("owner")
    if (
        not isinstance(identity, int)
        or isinstance(identity, bool)
        or identity <= 0
        or not isinstance(node_id, str)
        or not node_id
        or not isinstance(slug, str)
        or not _SLUG.fullmatch(slug)
        or not isinstance(owner, Mapping)
        or owner.get("login") != slug.split("/", 1)[0]
        or repo.get("fork") is not True
        or repo.get("private") is True
    ):
        raise RegistryError("GitHub fork response contains an invalid repository identity")
    stars = repo.get("stargazers_count")
    if not isinstance(stars, int) or isinstance(stars, bool) or stars < 0:
        raise RegistryError(f"{slug}: invalid GitHub star count")
    forks_count = repo.get("forks_count")
    if not isinstance(forks_count, int) or isinstance(forks_count, bool) or forks_count < 0:
        raise RegistryError(f"{slug}: invalid GitHub child-fork count")
    topics = repo.get("topics") or []
    if not isinstance(topics, list) or len(topics) > 200 or any(
        not isinstance(item, str) or not item or len(item) > 128 for item in topics
    ):
        raise RegistryError(f"{slug}: invalid GitHub topics")
    license_value = repo.get("license") if isinstance(repo.get("license"), Mapping) else {}
    spdx = license_value.get("spdx_id")
    if spdx in {"NOASSERTION", "OTHER"} or not isinstance(spdx, str):
        spdx = None
    name = slug.split("/", 1)[1]
    return {
        "artifact_id": f"github:{identity}",
        "github_id": identity,
        "node_id": node_id,
        "full_name": slug,
        "owner": owner["login"],
        "name": name,
        "artifact_type": "fork",
        "classifications": ["fork"],
        "source": "github-rest/fork-network",
        "repository_url": "https://github.com/" + slug,
        "description": str(repo.get("description") or "No repository description provided.")[:10_000],
        "description_origin": "github_repository_metadata",
        "topics": topics[:100],
        "language": repo.get("language") if isinstance(repo.get("language"), str) else None,
        "github_stars": stars,
        "seed_rank": None,
        "forks_count": forks_count,
        "pushed_at": repo.get("pushed_at") if isinstance(repo.get("pushed_at"), str) else None,
        "archived": bool(repo.get("archived")),
        "default_branch": repo.get("default_branch") if isinstance(repo.get("default_branch"), str) else None,
        "head_sha": None,
        "parent_repository": parent,
        "source_repository": upstream,
        "source_default_branch": source_branch,
        "license": {"spdx": spdx, "status": "github_reported" if spdx else "unknown"},
        "compatibility": {
            "declared_dsh_range": None,
            "observed_base": upstream,
            "summary": "Fork lineage only; DSH compatibility has not been analyzed.",
        },
        "installability": "browse-only",
        "analysis_status": "not_analyzed",
        "verification": {"metadata_only": True, "executed": False, "security_verified": False},
    }


def fetch_github_fork_network(
    upstream: str = DEFAULT_UPSTREAM,
    *,
    token: str | None = None,
    opener: Callable[..., Any] = urlopen,
    max_pages: int = MAX_FORK_PAGES,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, Any]:
    """Recursively collect visible forks and record why coverage is or is not proven."""

    if not isinstance(upstream, str) or not _SLUG.fullmatch(upstream):
        raise RegistryError("GitHub upstream must be owner/repository")
    if not isinstance(max_pages, int) or isinstance(max_pages, bool) or not 1 <= max_pages <= MAX_FORK_PAGES:
        raise RegistryError(f"max_pages must be between 1 and {MAX_FORK_PAGES}")
    root_url = f"{GITHUB_API}/repos/{upstream}"
    root_before, root_headers = _github_json(root_url, token=token, opener=opener)
    if not isinstance(root_before, Mapping) or root_before.get("full_name", "").casefold() != upstream.casefold():
        raise RegistryError("GitHub root metadata identity does not match the requested upstream")
    expected_before = _count(root_before)
    source_branch = root_before.get("default_branch")
    if (
        not isinstance(source_branch, str) or not source_branch or len(source_branch) > 256
        or any(ord(character) < 32 for character in source_branch)
    ):
        raise RegistryError("GitHub root metadata has no valid default branch")

    query = urlencode({"sort": "oldest", "per_page": 100, "page": 1})
    first_page = f"{root_url}/forks?{query}"
    frontier: list[tuple[str, int | None, str]] = [(upstream, None, first_page)]
    queued = {upstream.casefold()}
    seen_pages: set[str] = set()
    records: dict[int, dict[str, Any]] = {}
    direct_ids: set[int] = set()
    parent_mismatches: list[dict[str, Any]] = []
    pages = 0
    last_headers: dict[str, str | None] = {}
    expanded_parents = 0
    unfinished_page: str | None = None
    while frontier and pages < max_pages:
        parent, expected_children, next_page = frontier.pop(0)
        parent_seen = 0
        if parent != upstream:
            expanded_parents += 1
        while next_page and pages < max_pages:
            if next_page in seen_pages:
                raise RegistryError("GitHub pagination returned a cycle")
            seen_pages.add(next_page)
            payload, last_headers = _github_json(next_page, token=token, opener=opener)
            if not isinstance(payload, list) or len(payload) > 100:
                raise RegistryError("GitHub fork page is not a bounded list")
            for item in payload:
                if not isinstance(item, Mapping):
                    raise RegistryError("GitHub fork page contains a non-object")
                record = _fork(item, upstream, parent, source_branch)
                identity = record["github_id"]
                if identity in records:
                    raise RegistryError("GitHub recursive pagination returned a duplicate repository ID")
                records[identity] = record
                parent_seen += 1
                if parent == upstream:
                    direct_ids.add(identity)
                if record["forks_count"] and record["full_name"].casefold() not in queued:
                    queued.add(record["full_name"].casefold())
                    child_query = urlencode({"sort": "oldest", "per_page": 100, "page": 1})
                    frontier.append((
                        record["full_name"],
                        record["forks_count"],
                        f"{GITHUB_API}/repos/{record['full_name']}/forks?{child_query}",
                    ))
                if len(records) > MAX_FORKS:
                    raise RegistryError("GitHub fork network exceeds the configured record limit")
            pages += 1
            next_page = _next_url(last_headers.get("link"))
            if progress and (pages == 1 or pages % 10 == 0 or (next_page is None and not frontier)):
                progress(pages, len(records))
        if next_page:
            unfinished_page = next_page
            break
        if expected_children is not None and parent_seen != expected_children:
            parent_mismatches.append({"repository": parent, "reported": expected_children, "discovered": parent_seen})

    truncated = unfinished_page is not None or bool(frontier)
    root_after, end_headers = _github_json(root_url, token=token, opener=opener)
    if not isinstance(root_after, Mapping) or root_after.get("id") != root_before.get("id"):
        raise RegistryError("GitHub root identity changed while indexing")
    if root_after.get("default_branch") != source_branch:
        raise RegistryError("GitHub root default branch changed while indexing")
    expected_after = _count(root_after)
    stable = expected_before == expected_after
    complete = not truncated and stable and len(direct_ids) == expected_after and not parent_mismatches
    reasons = []
    if truncated:
        reasons.append("page budget exhausted")
    if not stable:
        reasons.append("fork-network count changed during collection")
    if len(direct_ids) != expected_after:
        reasons.append("direct visible count does not reconcile with GitHub root fork count")
    if parent_mismatches:
        reasons.append("one or more child-fork pages did not reconcile with their reported counts")
    fetched_at = _timestamp(end_headers.get("date") or root_headers.get("date"))
    digest_input = "\n".join(str(value) for value in sorted(records)).encode("ascii")
    digest = hashlib.sha256(digest_input).hexdigest()[:16]
    coverage = {
        "source": "github-rest/fork-network",
        "upstream": upstream,
        "status": "complete" if complete else "incomplete",
        "proof": "stable_recursive_page_reconciliation" if complete else "not_proven",
        "reported_count_before": expected_before,
        "reported_count_after": expected_after,
        "discovered_count": len(records),
        "direct_discovered_count": len(direct_ids),
        "descendant_count": len(records) - len(direct_ids),
        "expanded_parents": expanded_parents,
        "parent_count_mismatches": parent_mismatches[:100],
        "pages": pages,
        "truncated": truncated,
        "incomplete_reasons": reasons,
        "note": "Completeness covers visible recursive fork pages only and requires stable root and child-count reconciliation; GitHub may include inaccessible forks in reported counts.",
    }
    return {
        "schema_version": 1,
        "snapshot_id": f"github-forks-{root_before['id']}-{expected_after}-{digest}",
        "fetched_at": fetched_at,
        "completed_at": fetched_at,
        "upstream": upstream,
        "source_url": f"{root_url}/forks",
        "selection": {"method": "github_rest_recursive_pagination", "sort": "oldest", "limit": MAX_FORKS},
        "coverage": [coverage],
        "provenance": {
            "method": "github-rest/fork-network",
            "api_version": GITHUB_API_VERSION,
            "signature_status": "unsigned_external_metadata",
            "root_etag_before": root_headers.get("etag"),
            "root_etag_after": end_headers.get("etag"),
            "note": "Repository metadata only; no repository was cloned, installed, or executed.",
        },
        "entries": list(records.values()),
        "supplemental_entries": [],
        "package_entries": [],
    }


def merge_registry_snapshots(*snapshots: Mapping[str, Any]) -> dict[str, Any]:
    """Merge source adapters without duplicating repositories across classifications."""

    if not snapshots:
        raise RegistryError("At least one registry snapshot is required")
    repositories: dict[str, dict[str, Any]] = {}
    packages: dict[str, dict[str, Any]] = {}
    source_rows = []
    fetched = []
    coverage = []
    for snapshot in snapshots:
        snapshot_id = snapshot.get("snapshot_id")
        if not isinstance(snapshot_id, str) or not snapshot_id:
            raise RegistryError("Every source snapshot needs a stable snapshot_id")
        source_rows.append({
            "snapshot_id": snapshot_id,
            "source_url": snapshot.get("source_url"),
            "provenance": dict(snapshot.get("provenance") or {}),
        })
        if isinstance(snapshot.get("fetched_at"), str):
            fetched.append(snapshot["fetched_at"])
        coverage.extend(item for item in (snapshot.get("coverage") or []) if isinstance(item, Mapping))
        for raw in [*(snapshot.get("entries") or []), *(snapshot.get("supplemental_entries") or [])]:
            if not isinstance(raw, Mapping) or not isinstance(raw.get("artifact_id"), str):
                raise RegistryError("Source snapshot contains an invalid artifact")
            record = dict(raw)
            identity = record["artifact_id"]
            current = repositories.get(identity)
            if current is None:
                repositories[identity] = record
                continue
            types = list(dict.fromkeys([
                *(current.get("classifications") or [current.get("artifact_type")]),
                *(record.get("classifications") or [record.get("artifact_type")]),
            ]))
            lineage = (
                current.get("source_repository") if current.get("artifact_type") == "fork"
                else record.get("source_repository") if record.get("artifact_type") == "fork"
                else None
            )
            if record.get("artifact_type") == "plugin":
                current, record = record, current
            repositories[identity] = {
                **record,
                **current,
                "classifications": [item for item in types if isinstance(item, str) and item],
                "source_repository": lineage or current.get("source_repository") or record.get("source_repository"),
            }
        for raw in snapshot.get("package_entries") or []:
            if not isinstance(raw, Mapping) or not isinstance(raw.get("id"), str):
                raise RegistryError("Source snapshot contains an invalid package")
            if raw["id"] in packages and dict(raw) != packages[raw["id"]]:
                raise RegistryError(f"Conflicting package identity: {raw['id']}")
            packages[raw["id"]] = dict(raw)

    source_ids = "\n".join(sorted(row["snapshot_id"] for row in source_rows)).encode("utf-8")
    snapshot_id = "registry-" + hashlib.sha256(source_ids).hexdigest()[:20]
    values = list(repositories.values())
    return {
        "schema_version": 1,
        "snapshot_id": snapshot_id,
        "fetched_at": max(fetched) if fetched else "",
        "completed_at": max(fetched) if fetched else "",
        "upstream": "multiple",
        "source_url": None,
        "selection": {"method": "source_neutral_registry_merge", "source_count": len(snapshots)},
        "coverage": [dict(item) for item in coverage],
        "provenance": {
            "method": "dsh-forge.registry/v1",
            "signature_status": "unsigned_aggregate",
            "sources": source_rows,
            "note": "Source trust is preserved per adapter; aggregation does not upgrade it.",
        },
        "entries": sorted(
            (item for item in values if item.get("artifact_type") != "plugin"),
            key=lambda item: item["artifact_id"],
        ),
        "supplemental_entries": sorted(
            (item for item in values if item.get("artifact_type") == "plugin"),
            key=lambda item: item["artifact_id"],
        ),
        "package_entries": [packages[key] for key in sorted(packages)],
    }
