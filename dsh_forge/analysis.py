"""Bounded, metadata-only source analysis for promising GitHub forks."""

from __future__ import annotations

import base64
import binascii
import copy
import datetime as dt
import hashlib
import json
import re
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode
from urllib.request import urlopen

from .registry import GITHUB_API, GITHUB_API_VERSION, RegistryError, _github_json
from .research import evaluate_artifact


ANALYZER_VERSION = "dsh-forge.github-compare/v1"
MAX_FORK_ANALYSES = 100
MAX_COMPARE_FILES = 300
MAX_COMPARE_PATH_LENGTH = 1024
MAX_MANIFEST_BYTES = 1_048_576

_COMMIT = re.compile(r"[0-9a-f]{40}")
_SLUG = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
_LIFECYCLE_SCRIPTS = {"preinstall", "install", "postinstall", "prepare"}
_BINARY_SUFFIXES = (
    ".7z", ".a", ".dll", ".dylib", ".exe", ".gz", ".jar", ".node",
    ".rar", ".so", ".tar", ".wasm", ".xz", ".zip",
)
_SURFACES = {
    "agent orchestration": ("agent", "workflow", "orchestrat"),
    "browser and web UI": ("browser", "playwright", "web/", "frontend", "ui/"),
    "CLI and commands": ("cli", "command", "bin/"),
    "configuration": ("config", "cordis", ".dsh"),
    "model providers": ("model", "provider", "llm"),
    "plugin runtime": ("plugin", "extension", "skill", "mcp"),
    "sandbox and containers": ("sandbox", "container", "docker", "apptainer"),
    "tests and evaluation": ("test", "spec", "eval"),
}


class AnalysisError(ValueError):
    """A source-analysis input or provider response failed closed."""


def _integer(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 1_000_000_000:
        raise AnalysisError(f"GitHub comparison has no valid {label}")
    return value


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _COMMIT.fullmatch(value):
        raise AnalysisError(f"GitHub returned an invalid {label} commit")
    return value


def _observed_at(headers: Mapping[str, Any]) -> str:
    value = headers.get("date")
    if isinstance(value, str):
        try:
            from email.utils import parsedate_to_datetime
            parsed = parsedate_to_datetime(value)
            return parsed.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        except (TypeError, ValueError):
            pass
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _source_head(
    record: Mapping[str, Any],
    *,
    token: str | None,
    opener: Callable[..., Any],
    cache: dict[str, tuple[str, str]],
) -> tuple[str, str]:
    source = record.get("source_repository")
    if not isinstance(source, str) or not _SLUG.fullmatch(source):
        raise AnalysisError("Fork has no valid ultimate source repository")
    if source.casefold() in cache:
        return cache[source.casefold()]
    branch = record.get("source_default_branch")
    if not isinstance(branch, str) or not branch or len(branch) > 256:
        metadata, _ = _github_json(f"{GITHUB_API}/repos/{source}", token=token, opener=opener)
        if not isinstance(metadata, Mapping) or str(metadata.get("full_name") or "").casefold() != source.casefold():
            raise AnalysisError("GitHub source identity does not match the fork lineage")
        branch = metadata.get("default_branch")
    if not isinstance(branch, str) or not branch or len(branch) > 256 or any(ord(char) < 32 for char in branch):
        raise AnalysisError("GitHub source has no valid default branch")
    commit, _ = _github_json(
        f"{GITHUB_API}/repos/{source}/commits/{quote(branch, safe='')}",
        token=token,
        opener=opener,
    )
    if not isinstance(commit, Mapping):
        raise AnalysisError("GitHub source commit response is not an object")
    result = (branch, _sha(commit.get("sha"), "source"))
    cache[source.casefold()] = result
    return result


def _fork_head(record: Mapping[str, Any], *, token: str | None, opener: Callable[..., Any]) -> tuple[str, str]:
    slug = record.get("full_name")
    branch = record.get("default_branch")
    if (
        not isinstance(slug, str) or not _SLUG.fullmatch(slug)
        or not isinstance(branch, str) or not branch or len(branch) > 256
        or any(ord(char) < 32 for char in branch)
    ):
        raise AnalysisError("Fork has no valid repository and default branch")
    commit, headers = _github_json(
        f"{GITHUB_API}/repos/{slug}/commits/{quote(branch, safe='')}",
        token=token,
        opener=opener,
    )
    if not isinstance(commit, Mapping):
        raise AnalysisError("GitHub fork commit response is not an object")
    return _sha(commit.get("sha"), "fork head"), _observed_at(headers)


def _comparison(record: Mapping[str, Any], base_sha: str, head_sha: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    status = payload.get("status")
    if status not in {"ahead", "behind", "diverged", "identical"}:
        raise AnalysisError("GitHub comparison has an unknown relationship status")
    base = payload.get("base_commit")
    merge_base = payload.get("merge_base_commit")
    if not isinstance(base, Mapping) or _sha(base.get("sha"), "comparison base") != base_sha:
        raise AnalysisError("GitHub comparison did not use the requested source commit")
    if not isinstance(merge_base, Mapping):
        raise AnalysisError("GitHub comparison has no merge base")
    files = payload.get("files") or []
    if not isinstance(files, list) or len(files) > MAX_COMPARE_FILES:
        raise AnalysisError("GitHub comparison exceeded the bounded file inventory")
    paths = []
    additions = 0
    deletions = 0
    for item in files:
        if not isinstance(item, Mapping):
            raise AnalysisError("GitHub comparison contains an invalid file")
        filename = item.get("filename")
        if (
            not isinstance(filename, str) or not filename or len(filename) > MAX_COMPARE_PATH_LENGTH
            or filename.startswith("/") or "\x00" in filename
            or any(part == ".." for part in filename.replace("\\", "/").split("/"))
        ):
            raise AnalysisError("GitHub comparison contains an unsafe path")
        paths.append(filename)
        additions += _integer(item.get("additions"), "file addition count")
        deletions += _integer(item.get("deletions"), "file deletion count")
    ahead = _integer(payload.get("ahead_by"), "ahead count")
    commits = payload.get("commits") or []
    if not isinstance(commits, list) or len(commits) > 250:
        raise AnalysisError("GitHub comparison exceeded the bounded commit inventory")
    if ahead and commits and ahead <= 250:
        last = commits[-1]
        if not isinstance(last, Mapping) or _sha(last.get("sha"), "comparison head") != head_sha:
            raise AnalysisError("Fork branch moved during comparison")
    return {
        "provider": "github-rest/compare",
        "base_repository": record["source_repository"],
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_base_sha": _sha(merge_base.get("sha"), "merge base"),
        "status": status,
        "ahead_by": ahead,
        "behind_by": _integer(payload.get("behind_by"), "behind count"),
        "total_commits": _integer(payload.get("total_commits"), "total commit count"),
        "listed_file_count": len(paths),
        "files_truncated": len(paths) == MAX_COMPARE_FILES,
        "listed_additions": additions,
        "listed_deletions": deletions,
        "diffstat_scope": "first_300_changed_files" if len(paths) == MAX_COMPARE_FILES else "all_returned_changed_files",
        "changed_paths": paths,
    }


def _manifest(slug: str, head_sha: str, *, token: str | None, opener: Callable[..., Any]) -> dict[str, Any]:
    query = urlencode({"ref": head_sha})
    payload, _ = _github_json(
        f"{GITHUB_API}/repos/{slug}/contents/package.json?{query}",
        token=token,
        opener=opener,
    )
    if not isinstance(payload, Mapping) or payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
        raise AnalysisError("GitHub package manifest is not base64 file content")
    encoded = "".join(payload["content"].split())
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise AnalysisError("GitHub package manifest is not valid base64") from error
    if len(content) > MAX_MANIFEST_BYTES:
        raise AnalysisError("GitHub package manifest exceeds the byte limit")
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AnalysisError("Fork package.json is not valid UTF-8 JSON") from error
    if not isinstance(value, Mapping):
        raise AnalysisError("Fork package.json is not an object")
    scripts = value.get("scripts") if isinstance(value.get("scripts"), Mapping) else {}
    engines = value.get("engines") if isinstance(value.get("engines"), Mapping) else {}
    dependencies: dict[str, str] = {}
    for field in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        if len(dependencies) >= 32:
            break
        group = value.get(field) if isinstance(value.get(field), Mapping) else {}
        for name, version in group.items():
            if (
                isinstance(name, str) and isinstance(version, str)
                and len(name) <= 214 and len(version) <= 256
                and any(term in name.casefold() for term in ("dsh", "deepseek", "cordis"))
            ):
                dependencies[name] = version
            if len(dependencies) >= 32:
                break
    return {
        "name": str(value.get("name") or "")[:214],
        "version": str(value.get("version") or "")[:64],
        "node_range": str(engines.get("node") or "")[:128],
        "package_manager": str(value.get("packageManager") or "")[:128],
        "dsh_dependencies": dependencies,
        "lifecycle_scripts": sorted(name for name in scripts if name in _LIFECYCLE_SCRIPTS),
    }


def _signals(paths: list[str], manifest: Mapping[str, Any] | None) -> tuple[list[str], list[str]]:
    lowered = [path.casefold() for path in paths]
    joined = "\n".join(lowered)
    surfaces = [name for name, terms in _SURFACES.items() if any(term in joined for term in terms)]
    risks = []
    if any(path.startswith(".github/workflows/") for path in lowered):
        risks.append("changes automation workflows")
    if any(path.endswith(_BINARY_SUFFIXES) for path in lowered):
        risks.append("changes binary or executable artifacts")
    if any("dockerfile" in path or path.endswith("compose.yml") or path.endswith("compose.yaml") for path in lowered):
        risks.append("changes container or build configuration")
    if manifest and manifest.get("lifecycle_scripts"):
        risks.append("declares package lifecycle scripts")
    return surfaces, risks


def _compatibility(record: Mapping[str, Any], paths: list[str], manifest: Mapping[str, Any] | None) -> dict[str, Any]:
    surfaces, _ = _signals(paths, manifest)
    value = {
        "status": "inferred_metadata",
        "observed_base": record.get("source_repository"),
        "changed_surfaces": surfaces,
        "runtime_tested": False,
        "summary": "Source-diff signals only; runtime compatibility has not been tested.",
    }
    if manifest:
        value.update({
            "package_name": manifest.get("name") or None,
            "package_version": manifest.get("version") or None,
            "node_range": manifest.get("node_range") or None,
            "package_manager": manifest.get("package_manager") or None,
            "declared_dsh_dependencies": dict(manifest.get("dsh_dependencies") or {}),
            "manifest_status": "parsed_at_head_sha",
        })
    else:
        value["manifest_status"] = "not_changed_or_unavailable"
    return value


def select_fork_leads(snapshot: Mapping[str, Any], *, limit: int = MAX_FORK_ANALYSES) -> list[str]:
    """Select metadata leads for bounded analysis without claiming they are gems."""

    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_FORK_ANALYSES:
        raise AnalysisError(f"Fork analysis limit must be between 1 and {MAX_FORK_ANALYSES}")
    values = []
    for record in [*(snapshot.get("entries") or []), *(snapshot.get("supplemental_entries") or [])]:
        if not isinstance(record, Mapping) or record.get("artifact_type") != "fork" or record.get("archived") is True:
            continue
        report = evaluate_artifact(record, snapshot.get("fetched_at"))
        license_value = record.get("license") if isinstance(record.get("license"), Mapping) else {}
        if report["score"] < 45 or not report["capabilities"] or not license_value.get("spdx"):
            continue
        stars = record.get("github_stars")
        values.append((
            -report["score"],
            stars if isinstance(stars, int) and not isinstance(stars, bool) else 10**12,
            str(record.get("artifact_id") or ""),
        ))
    values.sort()
    return [identity for _, _, identity in values[:limit]]


def enrich_github_forks(
    snapshot: Mapping[str, Any],
    *,
    token: str | None = None,
    opener: Callable[..., Any] = urlopen,
    limit: int = MAX_FORK_ANALYSES,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Any]:
    """Pin and compare a bounded lead set without cloning or executing source."""

    selected = select_fork_leads(snapshot, limit=limit)
    selected_set = set(selected)
    result = copy.deepcopy(dict(snapshot))
    source_heads: dict[str, tuple[str, str]] = {}
    succeeded = 0
    failures = []
    observed = []
    processed = 0
    for collection in ("entries", "supplemental_entries"):
        rows = result.get(collection) or []
        if not isinstance(rows, list):
            raise AnalysisError(f"Registry {collection} must be a list")
        for record in rows:
            if not isinstance(record, dict) or record.get("artifact_id") not in selected_set:
                continue
            processed += 1
            identity = str(record["artifact_id"])
            try:
                base_branch, base_sha = _source_head(
                    record, token=token, opener=opener, cache=source_heads,
                )
                head_sha, head_observed = _fork_head(record, token=token, opener=opener)
                observed.append(head_observed)
                record["head_sha"] = head_sha
                source = str(record["source_repository"])
                source_owner = source.split("/", 1)[0]
                fork_owner = str(record["full_name"]).split("/", 1)[0]
                basehead = quote(f"{source_owner}:{base_sha}...{fork_owner}:{head_sha}", safe=":.")
                compare, headers = _github_json(
                    f"{GITHUB_API}/repos/{source}/compare/{basehead}",
                    token=token,
                    opener=opener,
                )
                if not isinstance(compare, Mapping):
                    raise AnalysisError("GitHub comparison response is not an object")
                divergence = _comparison(record, base_sha, head_sha, compare)
                observed_at = _observed_at(headers)
                observed.append(observed_at)
                manifest = None
                manifest_error = None
                if "package.json" in divergence["changed_paths"]:
                    try:
                        manifest = _manifest(str(record["full_name"]), head_sha, token=token, opener=opener)
                    except (AnalysisError, RegistryError) as error:
                        manifest_error = str(error)[:240]
                compatibility = _compatibility(record, divergence["changed_paths"], manifest)
                if manifest_error:
                    compatibility["manifest_error"] = manifest_error
                _, detected_risks = _signals(divergence["changed_paths"], manifest)
                risks = list(dict.fromkeys([
                    *[item for item in (record.get("risk_signals") or []) if isinstance(item, str)],
                    *detected_risks,
                ]))[:32]
                evidence = {
                    "analyzer": ANALYZER_VERSION,
                    "api_version": GITHUB_API_VERSION,
                    "observed_at": observed_at,
                    "base_branch_observed": base_branch,
                    "divergence": divergence,
                    "compatibility": compatibility,
                    "risk_signals": risks,
                }
                digest = "sha256:" + hashlib.sha256(json.dumps(
                    evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                ).encode("utf-8")).hexdigest()
                record.update({
                    "divergence": divergence,
                    "compatibility": compatibility,
                    "risk_signals": risks,
                    "analysis_status": "github_compare_metadata",
                    "analysis_evidence": {**evidence, "digest": digest},
                    "verification": {
                        **dict(record.get("verification") or {}),
                        "metadata_only": True,
                        "source_diff_reviewed": False,
                        "executed": False,
                        "security_verified": False,
                    },
                })
                record.pop("analysis_error", None)
                succeeded += 1
            except (AnalysisError, RegistryError, KeyError) as error:
                record["analysis_status"] = "revision_pinned_compare_failed" if record.get("head_sha") else "analysis_failed"
                record["analysis_error"] = str(error)[:240]
                failures.append({"artifact_id": identity, "error": str(error)[:240]})
            if progress:
                progress(processed, len(selected), identity)

    evidence_rows = []
    for collection in ("entries", "supplemental_entries"):
        for record in result.get(collection) or []:
            if isinstance(record, Mapping) and record.get("artifact_id") in selected_set:
                evidence_rows.append("|".join([
                    str(record.get("artifact_id")), str(record.get("head_sha") or ""),
                    str((record.get("analysis_evidence") or {}).get("digest") or ""),
                    str(record.get("analysis_status") or ""),
                ]))
    digest = hashlib.sha256("\n".join(sorted(evidence_rows)).encode("utf-8")).hexdigest()[:20]
    prior_snapshot = str(snapshot.get("snapshot_id") or "registry")
    result["snapshot_id"] = f"{prior_snapshot}-analysis-{digest}"[:256]
    completed_at = max(observed) if observed else dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    result["completed_at"] = completed_at
    coverage = list(result.get("coverage") or [])
    coverage.append({
        "source": "github-rest/fork-analysis",
        "status": "complete" if processed == len(selected) and not failures else "incomplete",
        "scope": "bounded_priority_leads",
        "analyzer": ANALYZER_VERSION,
        "limit": limit,
        "selected_count": len(selected),
        "analyzed_count": succeeded,
        "failed_count": len(failures),
        "failures": failures[:100],
        "note": "Only priority leads were compared. Repositories were not cloned, installed, imported, or executed.",
    })
    result["coverage"] = coverage
    provenance = dict(result.get("provenance") or {})
    provenance["analysis"] = {
        "method": ANALYZER_VERSION,
        "input_snapshot_id": prior_snapshot,
        "selected_count": len(selected),
        "analyzed_count": succeeded,
        "signature_status": "unsigned_external_metadata",
    }
    result["provenance"] = provenance
    return result
