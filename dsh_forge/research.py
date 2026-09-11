"""Deterministic hidden-gem ranking and package proposal composition.

Ranking uses only bounded catalog metadata. Proposal composition resolves exact
npm registry pins but never downloads or executes package code; existing Forge
acquisition, inspection, and sandbox stages remain the certification boundary.
"""

from __future__ import annotations

import base64
import binascii
from collections import Counter
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import quote, urlsplit
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from .packages import compose, create_trust_root, sign, validate_manifest, verify, write_json


POLICY_VERSION = "dsh-forge.hidden-gems/v2"
SUPPORTED_CERTIFICATION_POLICIES = {"dsh-forge.hidden-gems/v1", POLICY_VERSION}
PROPOSAL_SCHEMA = "dsh-forge.research-proposal/v1"
CERTIFICATION_SCHEMA = "dsh-forge.package-certification/v1"
DISCOVERY_QUEUE_SCHEMA = "dsh-forge.discovery-queue/v2"
FORK_ASSESSMENT_SCHEMA = "dsh-forge.fork-assessment/v1"
JUDGMENT_SCHEMA = "dsh-forge.discovery-judgments/v1"
BENCHMARK_SCHEMA = "dsh-forge.discovery-benchmark/v1"
MAX_REGISTRY_BYTES = 1_048_576
MAX_PROPOSAL_PLUGINS = 8
MAX_DISCOVERY_QUEUE = 250
SELECTION_POLICY = "dsh-forge.discovery-diversity/v1"
DIVERSITY_SCORE_WINDOW = 5

_NPM_NAME = re.compile(r"(?:@[a-z0-9._-]+/)?[a-z0-9._-]+")
_VERSION = re.compile(r"[0-9][0-9A-Za-z.+-]{0,63}")
_SHA512 = re.compile(r"sha512-([A-Za-z0-9+/]+={0,2})")
_COMMIT = re.compile(r"[0-9a-f]{40}")
_CAPABILITIES = {
    "memory": ("memory", "recall", "knowledge", "context"),
    "code intelligence": ("code index", "symbol", "codebase", "repository map"),
    "review": ("review", "audit", "lint", "quality"),
    "security": ("security", "permission", "supply chain", "vulnerability"),
    "testing": ("test", "browser automation", "playwright", "evaluation"),
    "orchestration": ("agent team", "multi-agent", "orchestration", "workflow"),
    "observability": ("observability", "trace", "logging", "metrics"),
    "search": ("search", "retrieval", "index"),
}
_RATINGS = {"irrelevant": 0, "weak": 1, "promising": 2, "exceptional": 3}


def _mentions(text: str, term: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None


class ResearchError(ValueError):
    """A ranking, registry-enrichment, or certification input failed closed."""


def _instant(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _known_license(record: Mapping[str, Any]) -> bool:
    value = record.get("license")
    expression = value.get("spdx") if isinstance(value, Mapping) else None
    return isinstance(expression, str) and bool(expression) and expression not in {"NOASSERTION", "UNKNOWN"}


def evaluate_artifact(record: Mapping[str, Any], observed_at: Any = None) -> dict[str, Any]:
    """Return an explainable 0-100 discovery priority without executing code."""

    identity = str(record.get("artifact_id") or "")[:256]
    signals: list[dict[str, Any]] = []
    gaps: list[str] = []
    score = 0

    def add(identifier: str, points: int, evidence: str) -> None:
        nonlocal score
        score += points
        signals.append({"id": identifier, "points": points, "evidence": evidence[:240]})

    validation = record.get("external_validation") if isinstance(record.get("external_validation"), Mapping) else {}
    verification = record.get("verification") if isinstance(record.get("verification"), Mapping) else {}
    status = str(validation.get("status") or "")
    if status == "valid" or verification.get("metadata_reviewed") is True:
        add("static-validation", 20, status or "metadata reviewed")
    else:
        gaps.append("no positive static validation")
        if status == "invalid":
            add("invalid", -30, str(validation.get("code") or "invalid"))

    installability = str(record.get("installability") or "")
    if installability == "one-click-eligible":
        add("installability", 14, "upstream reports one-click eligibility")
    elif installability and installability != "browse-only":
        add("installability", 6, installability)
    else:
        gaps.append("no validated installation route")

    artifact_type = str(record.get("artifact_type") or "repository")
    source_repository = record.get("source_repository")
    divergence = record.get("divergence") if isinstance(record.get("divergence"), Mapping) else None
    if artifact_type == "fork" and isinstance(source_repository, str) and source_repository:
        add("fork-lineage", 14, f"GitHub reports fork-network lineage from {source_repository}")
        if divergence is None:
            gaps.append("fork divergence not analyzed")
        else:
            ahead = divergence.get("ahead_by")
            listed_files = divergence.get("listed_file_count")
            if isinstance(ahead, int) and not isinstance(ahead, bool) and ahead > 0:
                add(
                    "fork-divergence",
                    18,
                    f"{ahead} fork-only commit(s), {listed_files if isinstance(listed_files, int) else 'unknown'} changed file(s) listed",
                )
                if divergence.get("files_truncated") is True:
                    gaps.append("changed-file inventory truncated at provider limit")
            else:
                add("no-fork-divergence", -20, str(divergence.get("status") or "no fork-only commits"))
                gaps.append("no fork-only commits found")

    commit = record.get("head_sha")
    if isinstance(commit, str) and _COMMIT.fullmatch(commit):
        add("immutable-revision", 10, commit)
    else:
        gaps.append("no immutable source revision")

    compatibility = record.get("compatibility") if isinstance(record.get("compatibility"), Mapping) else {}
    if compatibility.get("status") == "inferred_metadata":
        add("compatibility-signals", 4, ", ".join(compatibility.get("changed_surfaces") or []) or "source-diff metadata")

    package = record.get("package") if isinstance(record.get("package"), Mapping) else {}
    if isinstance(package.get("name"), str) and isinstance(package.get("version"), str):
        add("exact-version", 10, f"{package['name']}@{package['version']}")
    else:
        gaps.append("no exact package version")

    if _known_license(record):
        add("license", 10, str(record["license"]["spdx"]))
    else:
        gaps.append("license not reported")

    description = str(record.get("description") or "").strip()
    if len(description) >= 80:
        add("description", 8, "specific description")
    elif len(description) >= 24:
        add("description", 4, "brief description")
    else:
        gaps.append("insufficient behavior description")

    reference = _instant(observed_at) or _instant(record.get("indexed_at"))
    pushed = _instant(record.get("pushed_at"))
    if reference and pushed:
        age = max(0, (reference - pushed).days)
        if age <= 90:
            add("maintenance", 10, f"pushed {age} days before snapshot")
        elif age <= 365:
            add("maintenance", 5, f"pushed {age} days before snapshot")
        else:
            gaps.append("no recent maintenance signal")
    else:
        gaps.append("maintenance recency unavailable")

    topics = record.get("topics") if isinstance(record.get("topics"), list) else []
    searchable = " ".join([
        description,
        *[str(item) for item in topics if isinstance(item, str)],
    ]).casefold()
    capabilities = [
        capability for capability, terms in _CAPABILITIES.items()
        if any(_mentions(searchable, term) for term in terms)
    ]
    if capabilities:
        add("capability", min(10, 4 + len(capabilities) * 2), ", ".join(capabilities))
    else:
        gaps.append("no recognized agentic-development capability")

    stars = record.get("github_stars")
    stars = stars if isinstance(stars, int) and not isinstance(stars, bool) and stars >= 0 else None
    if stars is None:
        visibility = "unknown"
    elif stars <= 2:
        visibility = "nearly unseen"
        add("low-visibility", 14, f"{stars} GitHub stars")
    elif stars <= 10:
        visibility = "hidden"
        add("low-visibility", 10, f"{stars} GitHub stars")
    elif stars <= 50:
        visibility = "emerging"
        add("low-visibility", 5, f"{stars} GitHub stars")
    elif stars <= 200:
        visibility = "established"
        add("low-visibility", 1, f"{stars} GitHub stars")
    else:
        visibility = "well known"

    risk_values = record.get("risk_signals") if isinstance(record.get("risk_signals"), list) else []
    risks = [str(item) for item in risk_values if isinstance(item, str)][:32]
    if risks:
        add("risk-signals", -min(20, len(risks) * 4), ", ".join(risks))
    if record.get("archived") is True:
        add("archived", -40, "repository is archived")

    score = max(0, min(100, score))
    eligible = bool(status != "invalid" and record.get("archived") is not True and _known_license(record))
    if artifact_type == "fork":
        eligible = bool(
            eligible
            and score >= 55
            and isinstance(source_repository, str)
            and source_repository
            and isinstance(commit, str)
            and _COMMIT.fullmatch(commit)
            and divergence is not None
            and isinstance(divergence.get("ahead_by"), int)
            and not isinstance(divergence.get("ahead_by"), bool)
            and divergence.get("ahead_by") > 0
            and capabilities
            and len(description) >= 40
        )
    else:
        eligible = bool(eligible and score >= 65 and isinstance(commit, str) and package)
    return {
        "policy": POLICY_VERSION,
        "artifact_id": identity,
        "subject": {
            "package_name": str(package.get("name") or "")[:214],
            "package_version": str(package.get("version") or "")[:64],
            "repository_url": str(record.get("repository_url") or "")[:512],
            "commit": str(commit or "")[:40],
        },
        "score": score,
        "rank": None,
        "visibility": visibility,
        "confidence": "source-diff-metadata" if divergence is not None else "metadata-only",
        "candidate": eligible,
        "capabilities": capabilities,
        "signals": signals,
        "gaps": gaps[:12],
        "security_verified": False,
        "executed": False,
    }


def create_fork_assessment(
    record: Mapping[str, Any],
    research: Mapping[str, Any],
    *,
    decision: str,
    reviewer: str,
    reviewed_at: str,
    reviews: Iterable[str],
    notes: str = "",
) -> dict[str, Any]:
    """Create an inert curator decision bound to one analyzed fork revision."""

    if record.get("artifact_type") != "fork":
        raise ResearchError("Fork assessment requires a fork artifact")
    identity = str(record.get("artifact_id") or "")
    repository_url = str(record.get("repository_url") or "")
    commit = str(record.get("head_sha") or "")
    evidence = record.get("analysis_evidence") if isinstance(record.get("analysis_evidence"), Mapping) else {}
    evidence_digest = evidence.get("digest")
    if not identity or not repository_url.startswith("https://github.com/") or not _COMMIT.fullmatch(commit):
        raise ResearchError("Fork assessment requires an immutable GitHub revision")
    if not isinstance(evidence_digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", evidence_digest):
        raise ResearchError("Fork assessment requires source-analysis evidence")
    if (
        not isinstance(research, Mapping)
        or research.get("policy") != POLICY_VERSION
        or research.get("artifact_id") != identity
        or not isinstance(research.get("subject"), Mapping)
        or research["subject"].get("commit") != commit
    ):
        raise ResearchError("Fork assessment research does not match the analyzed revision")
    if decision not in {"advance", "hold", "reject"}:
        raise ResearchError("Fork assessment decision must be advance, hold, or reject")
    required = {"source", "risk", "license", "compatibility"}
    completed = set(reviews)
    if completed != required:
        raise ResearchError("Fork assessment requires explicit source, risk, license, and compatibility reviews")
    reviewer = str(reviewer or "").strip()
    notes = str(notes or "").strip()
    if not 2 <= len(reviewer) <= 128 or any(ord(character) < 32 for character in reviewer):
        raise ResearchError("Reviewer must contain 2 to 128 printable characters")
    if len(notes) > 4_000 or any(ord(character) < 9 for character in notes):
        raise ResearchError("Assessment notes exceed the safe text limit")
    instant = _instant(reviewed_at)
    if instant is None or len(reviewed_at) > 64:
        raise ResearchError("Assessment reviewed-at must be an ISO 8601 timestamp with a timezone")
    payload = {
        "schema": FORK_ASSESSMENT_SCHEMA,
        "policy": POLICY_VERSION,
        "artifact_id": identity,
        "repository_url": repository_url,
        "commit": commit,
        "evidence_digest": evidence_digest,
        "research_score": research.get("score"),
        "research_rank": research.get("rank"),
        "decision": decision,
        "reviewer": reviewer,
        "reviewed_at": instant.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "attestations": {name: True for name in sorted(required)},
        "notes": notes,
        "claims": {
            "signed": False,
            "executed": False,
            "security_verified": False,
            "installation_authorized": False,
        },
    }
    payload["assessment_digest"] = "sha256:" + hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    return payload


def _owner(record: Mapping[str, Any]) -> str:
    owner = str(record.get("owner") or "").strip().casefold()
    if owner:
        return owner[:256]
    full_name = str(record.get("full_name") or "")
    return (full_name.partition("/")[0] or str(record.get("artifact_id") or "unknown"))[:256].casefold()


def _diverse_selection(
    group: list[tuple[Mapping[str, Any], dict[str, Any]]],
) -> tuple[list[tuple[Mapping[str, Any], dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Select near-equal candidates across owners and capability lanes."""

    remaining = [item for item in group if item[1]["candidate"]]
    selected: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    selections: dict[str, dict[str, Any]] = {}
    owner_counts: Counter[str] = Counter()
    capability_counts: Counter[str] = Counter()
    while remaining and len(selected) < MAX_DISCOVERY_QUEUE:
        score_floor = remaining[0][1]["score"] - DIVERSITY_SCORE_WINDOW
        window = [
            (index, record, report)
            for index, (record, report) in enumerate(remaining)
            if report["score"] >= score_floor
        ]

        def choice(item: tuple[int, Mapping[str, Any], Mapping[str, Any]]) -> tuple[Any, ...]:
            _, record, report = item
            capabilities = report.get("capabilities") or ["other"]
            lane = min(capabilities, key=lambda value: (capability_counts[str(value)], str(value)))
            stars = record.get("github_stars")
            return (
                owner_counts[_owner(record)],
                capability_counts[str(lane)],
                -report["score"],
                stars if isinstance(stars, int) and not isinstance(stars, bool) else 10**12,
                str(record.get("artifact_id") or ""),
            )

        index, record, report = min(window, key=choice)
        capabilities = report.get("capabilities") or ["other"]
        lane = str(min(capabilities, key=lambda value: (capability_counts[str(value)], str(value))))
        owner = _owner(record)
        identity = str(record["artifact_id"])
        selections[identity] = {
            "policy": SELECTION_POLICY,
            "score_window": DIVERSITY_SCORE_WINDOW,
            "capability_lane": lane,
            "owner_exposure_before": owner_counts[owner],
            "capability_exposure_before": capability_counts[lane],
        }
        owner_counts[owner] += 1
        capability_counts[lane] += 1
        selected.append(remaining.pop(index))
    return selected, selections


def rank_artifacts(records: Iterable[Mapping[str, Any]], observed_at: Any = None) -> dict[str, dict[str, Any]]:
    """Rank each artifact type, then diversify near-equal eligible results."""

    evaluated: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    for record in records:
        if not isinstance(record, Mapping) or not record.get("artifact_id"):
            continue
        evaluated.append((record, evaluate_artifact(record, observed_at)))
    result: dict[str, dict[str, Any]] = {}
    for kind in sorted({str(record.get("artifact_type") or "repository") for record, _ in evaluated}):
        group = [(record, report) for record, report in evaluated if str(record.get("artifact_type") or "repository") == kind]
        group.sort(key=lambda item: (
            -item[1]["score"],
            item[0].get("github_stars") if isinstance(item[0].get("github_stars"), int) else 10**12,
            str(item[0].get("artifact_id")),
        ))
        quality_ranks = {str(record["artifact_id"]): rank for rank, (record, _) in enumerate(group, 1)}
        selected, selections = _diverse_selection(group)
        selected_ids = {str(record["artifact_id"]) for record, _ in selected}
        ordered = selected + [item for item in group if str(item[0]["artifact_id"]) not in selected_ids]
        for rank, (record, report) in enumerate(ordered, 1):
            identity = str(record["artifact_id"])
            result[str(record["artifact_id"])] = {
                **report,
                "quality_rank": quality_ranks[identity],
                "rank": rank,
                "candidate": identity in selected_ids,
                "selection": selections.get(identity),
            }
    return result


def _queue_quality(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    owners = Counter(_owner(item["artifact"]) for item in candidates)
    capabilities = Counter(
        str(capability)
        for item in candidates
        for capability in item["research"].get("capabilities") or ["other"]
    )
    types = Counter(str(item["artifact"].get("artifact_type") or "repository") for item in candidates)
    visibility = Counter(str(item["research"].get("visibility") or "unknown") for item in candidates)
    scores = [int(item["research"]["score"]) for item in candidates]
    return {
        "selection_policy": SELECTION_POLICY,
        "score_window": DIVERSITY_SCORE_WINDOW,
        "by_type": dict(sorted(types.items())),
        "by_capability": dict(sorted(capabilities.items())),
        "by_visibility": dict(sorted(visibility.items())),
        "unique_owners": len(owners),
        "max_candidates_per_owner": max(owners.values(), default=0),
        "score_min": min(scores, default=None),
        "score_max": max(scores, default=None),
    }


def discovery_queue(snapshot: Mapping[str, Any], *, limit: int = MAX_DISCOVERY_QUEUE) -> dict[str, Any]:
    """Build a bounded, portable metadata-research queue from a neutral snapshot."""

    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_DISCOVERY_QUEUE:
        raise ResearchError(f"Discovery queue limit must be between 1 and {MAX_DISCOVERY_QUEUE}")
    records = [
        record for record in [
            *(snapshot.get("entries") or []),
            *(snapshot.get("supplemental_entries") or []),
        ]
        if isinstance(record, Mapping) and record.get("artifact_id")
    ]
    reports = rank_artifacts(records, snapshot.get("fetched_at"))
    candidates = [
        {"artifact": dict(record), "research": reports[str(record["artifact_id"])]}
        for record in records
        if reports[str(record["artifact_id"])]["candidate"]
    ]
    candidates.sort(key=lambda item: (
        item["research"]["rank"],
        str(item["artifact"].get("artifact_type") or "repository"),
        str(item["artifact"]["artifact_id"]),
    ))
    selected = candidates[:limit]
    return {
        "schema": DISCOVERY_QUEUE_SCHEMA,
        "policy": POLICY_VERSION,
        "snapshot_id": str(snapshot.get("snapshot_id") or "")[:256],
        "fetched_at": str(snapshot.get("fetched_at") or "")[:64],
        "provenance": dict(snapshot.get("provenance")) if isinstance(snapshot.get("provenance"), Mapping) else {},
        "source_count": len(records),
        "candidate_count": len(selected),
        "candidates": selected,
        "quality": _queue_quality(selected),
        "claims": {
            "metadata_only": True,
            "security_verified": False,
            "executed": False,
        },
    }


def record_judgment(
    queue: Mapping[str, Any],
    ledger: Mapping[str, Any] | None,
    *,
    artifact_id: str,
    rating: str,
    reviewer: str,
    reviewed_at: str,
    notes: str = "",
) -> dict[str, Any]:
    """Record one unsigned curator relevance label bound to an exact queue snapshot."""

    if queue.get("schema") != DISCOVERY_QUEUE_SCHEMA or queue.get("policy") != POLICY_VERSION:
        raise ResearchError("Judgment requires the current discovery queue schema and policy")
    candidates = {
        str(item.get("artifact", {}).get("artifact_id") or ""): item
        for item in queue.get("candidates") or []
        if isinstance(item, Mapping) and isinstance(item.get("artifact"), Mapping)
    }
    candidate = candidates.get(str(artifact_id or ""))
    if candidate is None:
        raise ResearchError("Judgment artifact is not in this discovery queue")
    if rating not in _RATINGS:
        raise ResearchError("Judgment rating must be irrelevant, weak, promising, or exceptional")
    reviewer = str(reviewer or "").strip()
    notes = str(notes or "").strip()
    instant = _instant(reviewed_at)
    if not 2 <= len(reviewer) <= 128 or any(ord(character) < 32 for character in reviewer):
        raise ResearchError("Reviewer must contain 2 to 128 printable characters")
    if instant is None or len(reviewed_at) > 64:
        raise ResearchError("Judgment reviewed-at must be an ISO 8601 timestamp with a timezone")
    if len(notes) > 4_000 or any(ord(character) < 9 for character in notes):
        raise ResearchError("Judgment notes exceed the safe text limit")
    if ledger:
        if (
            ledger.get("schema") != JUDGMENT_SCHEMA
            or ledger.get("snapshot_id") != queue.get("snapshot_id")
            or ledger.get("policy") != POLICY_VERSION
            or not isinstance(ledger.get("judgments"), list)
            or len(ledger["judgments"]) > MAX_DISCOVERY_QUEUE
            or any(not isinstance(item, Mapping) for item in ledger["judgments"])
        ):
            raise ResearchError("Judgment ledger does not match this discovery snapshot")
        judgments = [dict(item) for item in ledger["judgments"] if isinstance(item, Mapping)]
    else:
        judgments = []
    research = candidate.get("research") if isinstance(candidate.get("research"), Mapping) else {}
    subject = research.get("subject")
    if not isinstance(subject, Mapping):
        raise ResearchError("Judgment candidate has no stable subject")
    judgment = {
        "artifact_id": artifact_id,
        "subject": dict(subject),
        "rating": rating,
        "relevance": _RATINGS[rating],
        "reviewer": reviewer,
        "reviewed_at": instant.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "notes": notes,
    }
    judgments = [item for item in judgments if item.get("artifact_id") != artifact_id]
    judgments.append(judgment)
    judgments.sort(key=lambda item: str(item.get("artifact_id") or ""))
    return {
        "schema": JUDGMENT_SCHEMA,
        "policy": POLICY_VERSION,
        "snapshot_id": queue.get("snapshot_id"),
        "judgments": judgments,
        "claims": {
            "signed": False,
            "executed": False,
            "security_verified": False,
            "installation_authorized": False,
        },
    }


def benchmark_queue(queue: Mapping[str, Any], ledger: Mapping[str, Any]) -> dict[str, Any]:
    """Measure ranked relevance using snapshot-bound curator judgments."""

    if (
        queue.get("schema") != DISCOVERY_QUEUE_SCHEMA
        or ledger.get("schema") != JUDGMENT_SCHEMA
        or queue.get("policy") != POLICY_VERSION
        or ledger.get("policy") != POLICY_VERSION
        or queue.get("snapshot_id") != ledger.get("snapshot_id")
    ):
        raise ResearchError("Benchmark inputs do not describe the same current discovery snapshot")
    candidates = [
        item for item in queue.get("candidates") or []
        if isinstance(item, Mapping) and isinstance(item.get("artifact"), Mapping)
    ]
    subjects = {
        str(item["artifact"].get("artifact_id") or ""): (
            item.get("research", {}).get("subject")
            if isinstance(item.get("research"), Mapping) else None
        )
        for item in candidates
    }
    ratings: dict[str, int] = {}
    for item in ledger.get("judgments") or []:
        if not isinstance(item, Mapping):
            raise ResearchError("Judgment ledger contains an invalid entry")
        identity = str(item.get("artifact_id") or "")
        relevance = item.get("relevance")
        rating = item.get("rating")
        if (
            identity in ratings
            or identity not in subjects
            or not isinstance(relevance, int)
            or isinstance(relevance, bool)
            or rating not in _RATINGS
            or _RATINGS[rating] != relevance
            or item.get("subject") != subjects[identity]
        ):
            raise ResearchError("Judgment ledger contains duplicate or invalid relevance")
        ratings[identity] = int(relevance)
    positions = [ratings.get(str(item["artifact"].get("artifact_id") or "")) for item in candidates]

    def metrics(cutoff: int) -> dict[str, Any]:
        values = positions[:cutoff]
        judged = [value for value in values if value is not None]
        gains = [0 if value is None else 2 ** value - 1 for value in values]
        dcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(gains))
        ideal = sorted((2 ** value - 1 for value in ratings.values()), reverse=True)[:len(values)]
        idcg = sum(gain / math.log2(index + 2) for index, gain in enumerate(ideal))
        relevant = sum(value >= 2 for value in judged)
        return {
            "cutoff": cutoff,
            "judged": len(judged),
            "judgment_coverage": round(len(judged) / len(values), 4) if values else 0.0,
            "precision": round(relevant / len(values), 4) if values else 0.0,
            "precision_among_judged": round(relevant / len(judged), 4) if judged else None,
            "ndcg": round(dcg / idcg, 4) if idcg else None,
        }

    cutoffs = sorted({min(value, len(candidates)) for value in (10, 25, 100) if candidates})
    return {
        "schema": BENCHMARK_SCHEMA,
        "policy": POLICY_VERSION,
        "snapshot_id": queue.get("snapshot_id"),
        "candidate_count": len(candidates),
        "judged_count": sum(value is not None for value in positions),
        "ratings": {name: sum(value == score for value in ratings.values()) for name, score in _RATINGS.items()},
        "metrics": [metrics(cutoff) for cutoff in cutoffs],
        "queue_quality": dict(queue.get("quality") or {}),
        "claims": {"metadata_only": True, "executed": False, "security_verified": False},
    }


def fetch_npm_pin(
    name: str,
    version: str,
    *,
    opener: Callable[..., Any] | None = None,
) -> dict[str, str]:
    """Resolve one exact npm version to its authoritative tarball and SRI pin."""

    if not isinstance(name, str) or not _NPM_NAME.fullmatch(name) or not isinstance(version, str) or not _VERSION.fullmatch(version):
        raise ResearchError("Proposal requires a valid npm package name and exact version")
    encoded_name = quote(name, safe="")
    url = f"https://registry.npmjs.org/{encoded_name}/{quote(version, safe='')}"
    request = Request(url, headers={"Accept": "application/json", "Accept-Encoding": "identity", "User-Agent": "DSH-Forge-research/1"})
    open_request = opener or build_opener(ProxyHandler({}), HTTPSHandler()).open
    try:
        with open_request(request, timeout=30) as response:
            final = urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != "registry.npmjs.org" or final.port not in {None, 443}:
                raise ResearchError("npm metadata redirect left the public registry")
            raw_length = response.headers.get("Content-Length")
            if raw_length:
                try:
                    if not 0 <= int(raw_length) <= MAX_REGISTRY_BYTES:
                        raise ResearchError("npm metadata exceeds the byte limit")
                except ValueError:
                    raise ResearchError("npm metadata returned an invalid Content-Length") from None
            payload = response.read(MAX_REGISTRY_BYTES + 1)
    except ResearchError:
        raise
    except OSError as error:
        raise ResearchError(f"Could not resolve {name}@{version} from npm: {error}") from error
    if len(payload) > MAX_REGISTRY_BYTES:
        raise ResearchError("npm metadata exceeds the byte limit")
    try:
        metadata = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ResearchError("npm metadata is not valid UTF-8 JSON") from error
    if not isinstance(metadata, dict) or metadata.get("name") != name or metadata.get("version") != version:
        raise ResearchError("npm metadata identity does not match the requested package")
    dist = metadata.get("dist")
    if not isinstance(dist, dict):
        raise ResearchError("npm metadata is missing distribution pins")
    integrity = dist.get("integrity")
    match = _SHA512.fullmatch(integrity) if isinstance(integrity, str) else None
    try:
        digest = base64.b64decode(match.group(1), validate=True) if match else b""
    except binascii.Error as error:
        raise ResearchError("npm integrity is not valid base64") from error
    if len(digest) != 64:
        raise ResearchError("npm metadata is missing a valid SHA-512 SRI pin")
    tarball = dist.get("tarball")
    parsed = urlsplit(tarball) if isinstance(tarball, str) else None
    if not parsed or parsed.scheme != "https" or parsed.hostname != "registry.npmjs.org" or parsed.port not in {None, 443}:
        raise ResearchError("npm tarball is outside the public registry")
    if not parsed.path.endswith(".tgz") or f"-{version}.tgz" not in parsed.path or parsed.query or parsed.fragment:
        raise ResearchError("npm tarball URL does not encode the exact version")
    return {"kind": "npm", "name": name, "version": version, "url": tarball, "integrity": integrity}


def compose_proposal(
    records: Iterable[Mapping[str, Any]],
    *,
    package_id: str,
    name: str,
    version: str,
    description: str,
    created_at: str,
    pin_resolver: Callable[[str, str], dict[str, str]] = fetch_npm_pin,
    evidence: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compose a reviewable exact-pin manifest from ranked catalog records."""

    selected = list(records)
    if not 1 <= len(selected) <= MAX_PROPOSAL_PLUGINS:
        raise ResearchError(f"Choose between 1 and {MAX_PROPOSAL_PLUGINS} artifacts")
    reports = (
        {str(identity): dict(report) for identity, report in evidence.items()}
        if evidence is not None
        else rank_artifacts(selected, created_at)
    )
    plugins = []
    licenses = set()
    seen_ids: set[str] = set()
    for record in selected:
        identity = str(record.get("artifact_id") or "")
        report = reports.get(identity)
        if not report or report.get("candidate") is not True:
            raise ResearchError(f"{identity or 'Artifact'} does not meet the metadata candidate threshold")
        package = record.get("package") if isinstance(record.get("package"), Mapping) else {}
        repository_url = str(record.get("repository_url") or "")
        commit = str(record.get("head_sha") or "")
        if not repository_url.startswith("https://github.com/") or not _COMMIT.fullmatch(commit):
            raise ResearchError(f"{identity} has no canonical repository commit")
        source = pin_resolver(str(package.get("name") or ""), str(package.get("version") or ""))
        plugin_id = re.sub(r"[^a-z0-9._-]+", "-", source["name"].casefold().lstrip("@")).strip("-")[:128]
        if len(plugin_id) < 2 or plugin_id in seen_ids:
            raise ResearchError("Selected packages do not produce unique plugin identities")
        seen_ids.add(plugin_id)
        license_value = record.get("license") if isinstance(record.get("license"), Mapping) else {}
        if isinstance(license_value.get("spdx"), str):
            licenses.add(license_value["spdx"])
        plugins.append({
            "id": plugin_id,
            "source": source,
            "repository": {"url": repository_url, "commit": commit},
            # Conservative draft. Curator should narrow permissions before certification.
            "permissions": [
                "browser:control", "environment:read", "filesystem:read", "filesystem:write",
                "model:invoke", "network:outbound", "process:spawn", "session:read", "session:write",
            ],
            "requires": [],
            "conflicts_with": [],
        })
    license_name = next(iter(licenses)) if len(licenses) == 1 else "NOASSERTION"
    spec = {
        "schema": "dsh-forge.package-spec/v1",
        "package": {
            "id": package_id,
            "name": name,
            "version": version,
            "description": description,
            "license": license_name,
            "created_at": created_at,
        },
        "compatibility": {"dsh": "unverified", "node": "unverified", "platforms": ["linux"]},
        "plugins": plugins,
        "load_order": [plugin["id"] for plugin in plugins],
        "provenance": {
            "created_by": f"DSH Forge {POLICY_VERSION}",
            "source": "registry_import",
            "evidence": "metadata_only_unexecuted",
        },
    }
    manifest = compose(spec)
    report_list = [reports[str(record["artifact_id"])] for record in selected]
    return {
        "schema": PROPOSAL_SCHEMA,
        "policy": POLICY_VERSION,
        "created_at": created_at,
        "status": "pending_curator_review",
        "manifest": manifest,
        "research": report_list,
        "required_reviews": ["source", "permissions", "license", "compatibility"],
        "security_verified": False,
        "sandbox_verified": False,
    }, report_list


def signed_review_statement(reviewer: str, policy: str = POLICY_VERSION) -> str:
    """Return the curator assertion embedded in the signed manifest."""

    if policy not in SUPPORTED_CERTIFICATION_POLICIES:
        raise ResearchError("Package certification policy is unsupported")
    return f"{reviewer} | reviewed source, permissions, license, compatibility | {policy}"


def certify_proposal(
    proposal: Mapping[str, Any],
    *,
    private_key: str | Path,
    public_key: str | Path,
    root_id: str,
    expires_at: str,
    reviewer: str,
    reviews: Iterable[str],
    destination_root: str | Path,
) -> dict[str, Any]:
    """Sign and atomically publish a curator-reviewed proposal locally."""

    if not isinstance(proposal, Mapping) or set(proposal) != {
        "schema", "policy", "created_at", "status", "manifest", "research",
        "required_reviews", "security_verified", "sandbox_verified",
    }:
        raise ResearchError("Proposal fields do not match the certification schema")
    if proposal.get("schema") != PROPOSAL_SCHEMA or proposal.get("policy") != POLICY_VERSION:
        raise ResearchError("Unsupported research proposal")
    if proposal.get("status") != "pending_curator_review":
        raise ResearchError("Only pending research proposals can be certified")
    if proposal.get("security_verified") is not False or proposal.get("sandbox_verified") is not False:
        raise ResearchError("A metadata proposal cannot claim security or sandbox verification")
    required = proposal.get("required_reviews")
    if required != ["source", "permissions", "license", "compatibility"]:
        raise ResearchError("Proposal does not require the complete curator review checklist")
    if set(reviews) != set(required):
        raise ResearchError("Certification requires explicit source, permissions, license, and compatibility reviews")
    reviewer = str(reviewer or "").strip()
    if not 2 <= len(reviewer) <= 128 or any(ord(character) < 32 for character in reviewer):
        raise ResearchError("Reviewer must contain 2 to 128 printable characters")
    manifest = validate_manifest(dict(proposal.get("manifest") or {}))
    reports = proposal.get("research")
    plugin_ids = {item["id"] for item in manifest["plugins"]}
    if not isinstance(reports, list) or len(reports) != len(plugin_ids) or any(
        not isinstance(item, Mapping)
        or item.get("policy") != POLICY_VERSION
        or item.get("candidate") is not True
        or item.get("security_verified") is not False
        or item.get("executed") is not False
        or not isinstance(item.get("subject"), Mapping)
        for item in reports
    ):
        raise ResearchError("Proposal research evidence is incomplete or unsafe")
    manifest_subjects = {
        (
            plugin["source"]["name"], plugin["source"]["version"],
            plugin["repository"]["url"], plugin["repository"]["commit"],
        )
        for plugin in manifest["plugins"]
    }
    report_subjects = {
        (
            item["subject"].get("package_name"), item["subject"].get("package_version"),
            item["subject"].get("repository_url"), item["subject"].get("commit"),
        )
        for item in reports
    }
    if report_subjects != manifest_subjects:
        raise ResearchError("Proposal research evidence does not match its exact package and repository pins")

    # Bind the reviewer and completed checklist to the signed bytes. The
    # adjacent certification receipt is readable metadata; this statement is
    # what prevents that receipt from changing the approval attached to a key.
    review_statement = signed_review_statement(reviewer)
    manifest["provenance"] = {**manifest["provenance"], "created_by": review_statement}
    manifest = validate_manifest(manifest)
    envelope = sign(manifest, private_key)
    trust_root = create_trust_root(public_key, root_id, expires_at)
    verification = verify(envelope, trust_root)
    package_id = manifest["package"]["id"]
    destination_root = Path(destination_root).expanduser().absolute()
    destination_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination_root.is_symlink():
        raise ResearchError("Publication root may not be a symlink")
    destination = destination_root / package_id
    if destination.exists():
        raise ResearchError(f"Certified package already exists: {package_id}")
    certification = {
        "schema": CERTIFICATION_SCHEMA,
        "policy": POLICY_VERSION,
        "package_id": package_id,
        "package_name": manifest["package"]["name"],
        "package_version": manifest["package"]["version"],
        "component_count": len(manifest["plugins"]),
        "reviewer": reviewer,
        "signed_review_statement": review_statement,
        "reviewed_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "attestations": {item: True for item in required},
        "payload_digest": verification["payload_digest"],
        "valid_signers": verification["valid_signers"],
        "metadata_candidate": True,
        "security_verified": False,
        "sandbox_verified": False,
        "install_policy": "acquire-inspect-networkless-apptainer-smoke-test-then-promote",
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{package_id}-", dir=destination_root))
    try:
        write_json(temporary / "envelope.json", envelope)
        write_json(temporary / "trust-root.json", trust_root)
        write_json(temporary / "proposal.json", dict(proposal))
        write_json(temporary / "certification.json", certification)
        os.replace(temporary, destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"package_id": package_id, "directory": str(destination), "certification": certification}
