"""Stage 3: turn measurements and verdicts into the final picks.

Three inputs per repository, each on a 0-100 scale:

* stage 1: the statistics score from the published discovery queue
* substance: what the automatic inspection found inside the repository
* review: the verdict of whoever read the code, when there is one

The weights live in ``Weights`` so the evaluation suite can compare settings.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence

from . import PICKS_SCHEMA, POLICY
from .review import SCORES


@dataclass(frozen=True)
class Weights:
    # Share of the final score when a review exists.
    review: float = 0.55
    substance: float = 0.25
    stage1: float = 0.20
    # Share of the review score given to each rubric line.
    usefulness: float = 0.30
    novelty: float = 0.25
    craft: float = 0.20
    works: float = 0.15
    trust: float = 0.10
    # A repository nobody has read cannot outrank one that was read and liked.
    unreviewed_ceiling: float = 70.0
    # Above this share of copied source files, a project is not a pick.
    max_copy_overlap: float = 0.6


DEFAULT_WEIGHTS = Weights()


def _saturate(value: float, full_at: float) -> float:
    """0..1, rising quickly then flattening: twice as much is not twice as good."""
    if value <= 0:
        return 0.0
    return min(1.0, math.log1p(value) / math.log1p(full_at))


def substance_score(inspection: Mapping[str, Any], copy_overlap: float = 0.0) -> float:
    """0-100: how much real, working-looking plugin is in the repository.

    The shape and weights were chosen on the backtest (``eval/data``): on a held-out
    half, projects that later took off outscore ones that did not 81% of the time,
    against 69% for the first version of this function. What moved it: let size and
    documentation keep counting well past small projects, and treat the plugin
    wiring as a gate rather than as points, since almost every project has it.
    """
    manifest = inspection.get("manifest") or {}
    code = inspection.get("code") or {}
    tests = inspection.get("tests") or {}
    docs = inspection.get("docs") or {}
    practices = inspection.get("practices") or {}

    size = _saturate(code.get("lines") or 0, 15000)
    explained = _saturate(docs.get("bytes") or 0, 100000)
    tested = _saturate(tests.get("lines") or 0, 3000)
    kept = (
        sum(bool(practices.get(key)) for key in ("ci", "license", "changelog")) + bool(manifest.get("has_test_script"))
    ) / 4
    wiring = sum(bool(manifest.get(key)) for key in ("valid", "declares_plugin", "patch_file_present", "entry_present")) / 4
    score = 100 * (0.40 * size + 0.40 * explained + 0.10 * tested + 0.10 * kept)
    score *= 0.5 + 0.5 * wiring

    if inspection.get("kind") in {"stub", "prompt pack"}:
        score *= 0.4
    if manifest.get("lifecycle_scripts"):
        score -= 8
    score -= 6 * len(inspection.get("risk_hints") or {})
    score *= 1 - min(1.0, max(0.0, copy_overlap))
    return round(max(0.0, min(100.0, score)), 1)


def review_score(review: Mapping[str, Any], weights: Weights = DEFAULT_WEIGHTS) -> float:
    """0-100 from the five rubric lines."""
    scores = review["scores"]
    total = sum(getattr(weights, name) for name in SCORES)
    weighted = sum(getattr(weights, name) * (scores[name] - 1) / 4 for name in SCORES)
    return round(100 * weighted / total, 1)


def _reasons(candidate: Mapping[str, Any], inspection: Mapping[str, Any], review: Mapping[str, Any] | None) -> list[str]:
    reasons: list[str] = []
    if review:
        reasons.append(review["showcase"])
    code = inspection.get("code") or {}
    tests = inspection.get("tests") or {}
    if code.get("lines"):
        line = f"{code['lines']:,} lines of its own code"
        if tests.get("files"):
            line += f" with {tests['files']} test file{'s' if tests['files'] != 1 else ''}"
        reasons.append(line)
    stars = candidate.get("stars") or 0
    reasons.append("No stars yet" if stars == 0 else f"Only {stars} star{'s' if stars != 1 else ''} so far")
    return reasons[:3]


def rank(
    candidates: Sequence[Mapping[str, Any]],
    inspections: Mapping[str, Mapping[str, Any]],
    reviews: Mapping[str, Mapping[str, Any]],
    overlap: Mapping[str, float],
    *,
    weights: Weights = DEFAULT_WEIGHTS,
    limit: int = 60,
) -> list[dict[str, Any]]:
    """Order the candidates. ``inspections`` and ``overlap`` are keyed by ``owner/name``;
    ``reviews`` by its lower-cased form. Repositories that were not inspected, were
    reviewed as ``skip``, or are mostly copied are left out."""
    picks: list[dict[str, Any]] = []
    for candidate in candidates:
        name = candidate["full_name"]
        inspection = inspections.get(name)
        if inspection is None:
            continue
        copied = float(overlap.get(name, 0.0))
        review = reviews.get(name.casefold())
        if review and review["verdict"] == "skip":
            continue
        if copied > weights.max_copy_overlap:
            continue
        substance = substance_score(inspection, copied)
        stage1 = float(candidate.get("stage1", {}).get("score") or 0)
        current = bool(review) and review["commit"] == candidate["commit"]
        if review:
            read = review_score(review, weights)
            score = weights.review * read + weights.substance * substance + weights.stage1 * stage1
            score /= weights.review + weights.substance + weights.stage1
            confidence = "reviewed" if current else "reviewed at an earlier version"
        else:
            read = None
            share = weights.substance + weights.stage1
            score = (weights.substance * substance + weights.stage1 * stage1) / share
            # Scaled, not clipped, so unread repositories keep their order among themselves.
            score *= weights.unreviewed_ceiling / 100
            confidence = "measured"
        picks.append({
            "artifact_id": candidate.get("artifact_id", ""),
            "full_name": name,
            "commit": candidate["commit"],
            "score": round(score, 1),
            "confidence": confidence,
            "verdict": review["verdict"] if review else None,
            "summary": review["summary"] if review else candidate.get("description", ""),
            "reasons": _reasons(candidate, inspection, review),
            "capabilities": list(candidate.get("capabilities") or []),
            "stars": candidate.get("stars", 0),
            "parts": {"stage1": round(stage1, 1), "substance": substance, "review": read, "copy_overlap": copied},
            "review_source": review["source"] if review else None,
        })
    picks.sort(key=lambda pick: (-pick["score"], pick["full_name"].casefold()))
    for position, pick in enumerate(picks[:limit], start=1):
        pick["rank"] = position
    return picks[:limit]


def picks_document(
    picks: Sequence[Mapping[str, Any]],
    *,
    generated_at: str,
    queue: Mapping[str, Any],
    considered: int,
    inspected: int,
) -> dict[str, Any]:
    """The file the app reads."""
    return {
        "schema": PICKS_SCHEMA,
        "policy": POLICY,
        "generated_at": generated_at,
        "based_on": {
            "snapshot_id": str(queue.get("snapshot_id") or ""),
            "stage1_policy": str(queue.get("policy") or ""),
        },
        "counts": {
            "considered": considered,
            "inspected": inspected,
            "reviewed": sum(1 for pick in picks if pick.get("verdict")),
            "picks": len(picks),
        },
        "claims": {"executed": False, "security_verified": False},
        "picks": list(picks),
    }
