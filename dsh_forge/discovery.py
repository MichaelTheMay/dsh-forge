"""Hidden-gem discovery v3: measured quality against measured attention.

A hidden gem is a project that is better than its attention suggests. Both
halves are measured from public evidence, never from model judgment:

1. **How it is built.** For plugins, a ridge regression learns, across the
   whole enriched ecosystem, how creator-controlled facts (tests, CI, README
   depth, docs, releases, license, commit volume, recent activity, age) relate
   to the stars a project ends up with. Applying it to one project gives the
   attention a project *built like this one, at this age* typically gets.
   Popularity-driven facts (issues, pull requests, contributors) are kept out
   of the model so that it cannot learn popularity from popularity.
2. **How much attention it has.** Its actual stars.

The gem score combines how well a project is built (percentile of predicted
attention), how far its actual attention falls short (percentile of the gap),
and outside validation that is meaningful at low star counts (stars from
Harness contributors or established plugin authors, closed issues, merged pull
requests, other contributors). Hard gates keep out archived, unlicensed,
undocumented, stale, or already-popular projects.

Forks inherit their README, tests, and history from upstream, so those facts
say nothing about the fork. Forks are scored on what they added: fork-only
commits, the surfaces those commits touch, how recently the fork moved, a
description of their own, and the same outside validation.

Each published pick carries plain-language reasons built from the measured
values, and the queue records cross-validated accuracy of the attention model
so the method can be checked rather than trusted.
"""

from __future__ import annotations

from collections import Counter
import datetime as dt
import hashlib
import math
import re
from typing import Any, Iterable, Mapping, Sequence

from .enrichment import EVIDENCE_SCHEMA, has_own_commits
from .research import (
    DISCOVERY_QUEUE_SCHEMA,
    MAX_DISCOVERY_QUEUE,
    SELECTION_POLICY,
    _CAPABILITIES,
    _diverse_selection,
    _mentions,
    _owner,
    discovery_queue as metadata_queue,
)


POLICY = "dsh-forge.hidden-gems/v3"
MODEL = "dsh-forge.attention-ridge/v1"
PACKS_POLICY = "dsh-forge.curated-packs/v1"
RIDGE_LAMBDA = 3.0
CV_FOLDS = 5
MIN_TRAINING = 40
HIDDEN_STAR_CEILING = 50  # upper bound; the effective ceiling comes from the data
HIDDEN_STAR_PERCENTILE = 0.95
MIN_HIDDEN_CEILING = 10
MIN_README_BYTES = 800
MAX_PUSH_AGE_DAYS = 365
MAX_PLUGIN_GEMS = 160
MAX_FORK_GEMS = 40
MIN_EVIDENCE_COVERAGE = 0.05
PACK_MIN_STRENGTH = 4
MIN_MODEL_SPEARMAN = 0.15  # below this, held-out predictions are too weak to explain picks

PLUGIN_FEATURES = (
    "tests", "ci", "readme", "docs", "changelog", "releases",
    "license", "commits", "recent_commits", "fresh", "age",
)
# Age must stay last: the craft index drops it (it buys exposure, not quality).
assert PLUGIN_FEATURES[-1] == "age"

PACK_THEMES = (
    {
        "id": "memory-and-context",
        "title": "Memory & context",
        "summary": "Give your agent a memory that lasts between sessions and a map of your codebase.",
        "slots": ("memory", "code intelligence", "search"),
    },
    {
        "id": "review-and-safety",
        "title": "Review & safety net",
        "summary": "Catch bad changes before they land: code review, security checks, and tests.",
        "slots": ("review", "security", "testing"),
    },
    {
        "id": "agent-teams",
        "title": "Agent teams",
        "summary": "Run several agents together, keep shared memory, and see what each one is doing.",
        "slots": ("orchestration", "observability", "memory"),
    },
    {
        "id": "ship-faster",
        "title": "Ship faster",
        "summary": "Find your way around large repos, test as you go, and automate the busywork.",
        "slots": ("code intelligence", "testing", "orchestration"),
    },
)

SLOT_LABELS = {
    "memory": "Memory",
    "code intelligence": "Code navigation",
    "search": "Search",
    "review": "Code review",
    "security": "Security",
    "testing": "Testing",
    "orchestration": "Orchestration",
    "observability": "Observability",
}


# --------------------------------------------------------------------------- helpers
def _instant(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0


def _stars(record: Mapping[str, Any]) -> int:
    # Today's index is fresher than evidence, which may be reused for two weeks.
    stars = record.get("github_stars")
    if isinstance(stars, int) and not isinstance(stars, bool):
        return max(0, stars)
    evidence = _evidence(record)
    return _int(evidence.get("stars")) if evidence else 0


def _evidence(record: Mapping[str, Any]) -> dict[str, Any] | None:
    value = record.get("evidence")
    return dict(value) if isinstance(value, Mapping) and value.get("schema") == EVIDENCE_SCHEMA else None


def _license(record: Mapping[str, Any], evidence: Mapping[str, Any] | None) -> str | None:
    if evidence and evidence.get("license"):
        return str(evidence["license"])
    value = record.get("license") if isinstance(record.get("license"), Mapping) else {}
    spdx = value.get("spdx")
    return spdx if isinstance(spdx, str) and spdx and spdx not in {"NOASSERTION", "UNKNOWN"} else None


PRIMARY_TERMS = {
    "memory": ("memory", "memories", "recall", "remember", "long-term", "notes"),
    "code intelligence": ("code index", "symbol", "codebase", "repository map", "repo map", "code search", "code graph", "lsp"),
    "search": ("search", "retrieval", "rag", "web search"),
    "review": ("code review", "review", "reviewer", "lint", "linter"),
    "security": ("security", "permission", "permissions", "supply chain", "vulnerability", "secrets", "audit"),
    "testing": ("test", "tests", "testing", "playwright", "e2e", "evaluation", "eval"),
    "orchestration": ("multi-agent", "agent team", "agent teams", "orchestration", "orchestrator", "workflow", "subagent", "scheduler"),
    "observability": ("observability", "trace", "tracing", "logging", "metrics", "telemetry", "dashboard"),
}


def primary_capabilities(record: Mapping[str, Any]) -> list[str]:
    """Capabilities a plugin is *about*: named in its name or topics, or repeated in its description."""
    name = re_words(str(record.get("name") or ""))
    topics = " ".join(re_words(str(item)) for item in record.get("topics") or [] if isinstance(item, str))
    description = str(record.get("description") or "").casefold()
    return [capability for capability, _ in capability_strengths(record)]


def capability_strengths(record: Mapping[str, Any]) -> list[tuple[str, int]]:
    """(capability, strength) pairs, strongest first.

    Strength: 4 if the name says it, 2 per matching topic, 1 per description
    mention (capped at 3). Anything below 2 is incidental.
    """
    name = re_words(str(record.get("name") or ""))
    topic_words = [re_words(str(item)) for item in record.get("topics") or [] if isinstance(item, str)]
    description = str(record.get("description") or "").casefold()
    found = []
    for capability, terms in PRIMARY_TERMS.items():
        in_name = any(_mentions(name, term) for term in terms)
        topic_hits = sum(1 for topic in topic_words if any(_mentions(topic, term) for term in terms))
        # One alternation, longest term first, so "web search" is one mention, not two.
        pattern = r"(?<![a-z0-9])(?:" + "|".join(re.escape(term) for term in sorted(terms, key=len, reverse=True)) + r")(?![a-z0-9])"
        mentions = len(re.findall(pattern, description))
        strength = 4 * in_name + 2 * min(topic_hits, 3) + min(mentions, 3)
        if in_name or topic_hits or mentions >= 2:
            found.append((-strength, capability))
    return [(capability, -negative) for negative, capability in sorted(found)]


def re_words(value: str) -> str:
    """Lowercase with separators as spaces, so 'dsh-memory_store' matches 'memory'."""
    return re.sub(r"[-_./]+", " ", value).casefold()


def capabilities(record: Mapping[str, Any]) -> list[str]:
    description = str(record.get("description") or "")
    topics = record.get("topics") if isinstance(record.get("topics"), list) else []
    text = " ".join([description, *[str(item) for item in topics if isinstance(item, str)]]).casefold()
    return [name for name, terms in _CAPABILITIES.items() if any(_mentions(text, term) for term in terms)]


def percentiles(values: Sequence[float]) -> list[float]:
    """Mid-rank percentiles in [0, 1]; ties share a rank."""
    if not values:
        return []
    order = sorted(range(len(values)), key=lambda index: values[index])
    result = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        rank = (position + end) / 2
        for index in order[position:end + 1]:
            result[index] = rank / (len(values) - 1) if len(values) > 1 else 0.5
        position = end + 1
    return result


def spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    if len(left) != len(right) or len(left) < 3:
        return None
    a = percentiles(left)
    b = percentiles(right)
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    covariance = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    spread = math.sqrt(sum((x - mean_a) ** 2 for x in a) * sum((y - mean_b) ** 2 for y in b))
    return round(covariance / spread, 4) if spread else None


# --------------------------------------------------------------------------- ridge
def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting for a small dense system."""
    size = len(vector)
    rows = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(rows[row][column]))
        if abs(rows[pivot][column]) < 1e-12:
            continue
        rows[column], rows[pivot] = rows[pivot], rows[column]
        for row in range(size):
            if row != column and rows[row][column]:
                factor = rows[row][column] / rows[column][column]
                rows[row] = [left - factor * right for left, right in zip(rows[row], rows[column])]
    return [rows[index][size] / rows[index][index] if abs(rows[index][index]) > 1e-12 else 0.0 for index in range(size)]


class Ridge:
    """Standardized ridge regression; the intercept is not penalized."""

    def __init__(self, penalty: float = RIDGE_LAMBDA):
        self.penalty = penalty
        self.means: list[float] = []
        self.scales: list[float] = []
        self.weights: list[float] = []
        self.intercept = 0.0

    def fit(self, rows: Sequence[Sequence[float]], targets: Sequence[float]) -> "Ridge":
        width = len(rows[0])
        self.means = [sum(row[index] for row in rows) / len(rows) for index in range(width)]
        self.scales = [
            math.sqrt(sum((row[index] - self.means[index]) ** 2 for row in rows) / len(rows)) or 1.0
            for index in range(width)
        ]
        standardized = [self._standardize(row) for row in rows]
        self.intercept = sum(targets) / len(targets)
        centered = [target - self.intercept for target in targets]
        gram = [[0.0] * width for _ in range(width)]
        moment = [0.0] * width
        for row, target in zip(standardized, centered):
            for i in range(width):
                moment[i] += row[i] * target
                for j in range(width):
                    gram[i][j] += row[i] * row[j]
        for i in range(width):
            gram[i][i] += self.penalty
        self.weights = _solve(gram, moment)
        return self

    def _standardize(self, row: Sequence[float]) -> list[float]:
        return [(value - mean) / scale for value, mean, scale in zip(row, self.means, self.scales)]

    def predict(self, row: Sequence[float]) -> float:
        return self.intercept + sum(weight * value for weight, value in zip(self.weights, self._standardize(row)))

    def contributions(self, row: Sequence[float]) -> list[float]:
        return [weight * value for weight, value in zip(self.weights, self._standardize(row))]


# --------------------------------------------------------------------------- features
def plugin_features(record: Mapping[str, Any], evidence: Mapping[str, Any], observed_at: dt.datetime) -> list[float]:
    created = _instant(evidence.get("created_at")) or _instant(record.get("created_at"))
    pushed = _instant(evidence.get("pushed_at")) or _instant(record.get("pushed_at"))
    age_days = max(1.0, (observed_at - created).days) if created else 90.0
    push_age = (observed_at - pushed).days if pushed else 9999
    return [
        1.0 if evidence.get("has_tests") else 0.0,
        1.0 if _int(evidence.get("ci_workflows")) else 0.0,
        math.log1p(_int(evidence.get("readme_bytes")) / 1000),
        1.0 if evidence.get("has_docs") or evidence.get("has_examples") else 0.0,
        1.0 if evidence.get("has_changelog") else 0.0,
        math.log1p(_int(evidence.get("releases"))),
        1.0 if _license(record, evidence) else 0.0,
        math.log1p(_int(evidence.get("commits_total"))),
        math.log1p(_int(evidence.get("commits_recent"))),
        1.0 if push_age <= 90 else (0.5 if push_age <= 365 else 0.0),
        math.log1p(age_days / 30.4),
    ]


def outside_validation(record: Mapping[str, Any], evidence: Mapping[str, Any]) -> float:
    """Points (0-20) for engagement that is meaningful even at low star counts."""
    endorsements = len(evidence.get("endorsed_by") or [])
    engagement = _int(evidence.get("closed_issues")) + _int(evidence.get("merged_pull_requests"))
    others = max(0, _int(evidence.get("contributors")) - 1)
    recent_stars = _int(evidence.get("stars_last_30d"))
    value = 6 * min(endorsements, 2) + 3 * math.log1p(engagement) + 2 * math.log1p(others) + 1.5 * min(recent_stars, 4)
    return min(20.0, value)


# --------------------------------------------------------------------------- reasons
def _round_stars(value: float) -> int:
    if value < 10:
        return max(1, round(value))
    magnitude = 10 ** (len(str(int(value))) - 1)
    return int(round(value / magnitude) * magnitude)


def plugin_reasons(
    record: Mapping[str, Any], evidence: Mapping[str, Any], predicted_stars: float | None, stars: int,
) -> list[str]:
    reasons: list[tuple[float, str]] = []
    if predicted_stars is not None and predicted_stars >= stars + 3:
        reasons.append((10, f"Built like projects that usually have ~{_round_stars(predicted_stars)} stars; it has {stars}."))
    endorsed = list(evidence.get("endorsed_by") or [])
    if endorsed:
        names = ", ".join("@" + login for login in endorsed[:2])
        more = f" and {len(endorsed) - 2} more" if len(endorsed) > 2 else ""
        reasons.append((9, f"Starred by Harness contributors or plugin authors ({names}{more})."))
    tests = bool(evidence.get("has_tests"))
    ci = _int(evidence.get("ci_workflows")) > 0
    if tests and ci:
        reasons.append((8, "Has a test suite and runs CI on every change."))
    elif tests:
        reasons.append((6, "Ships with a test suite."))
    elif ci:
        reasons.append((5, "Runs CI on every change."))
    recent = _int(evidence.get("commits_recent"))
    if recent >= 5:
        reasons.append((7, f"{recent} commits in the last 90 days."))
    engagement = _int(evidence.get("closed_issues")) + _int(evidence.get("merged_pull_requests"))
    if engagement >= 3:
        reasons.append((6, f"{_int(evidence.get('closed_issues'))} issues closed and {_int(evidence.get('merged_pull_requests'))} pull requests merged."))
    releases = _int(evidence.get("releases"))
    if releases >= 2:
        reasons.append((5, f"{releases} tagged releases."))
    readme = _int(evidence.get("readme_bytes"))
    if readme >= 4000:
        reasons.append((4, f"Thorough README ({round(readme / 1000)} KB)" + (" with docs or examples." if evidence.get("has_docs") or evidence.get("has_examples") else ".")))
    reasons.sort(key=lambda item: -item[0])
    return [text for _, text in reasons[:4]]


def fork_reasons(record: Mapping[str, Any], evidence: Mapping[str, Any] | None) -> list[str]:
    divergence = record.get("divergence") if isinstance(record.get("divergence"), Mapping) else {}
    compatibility = record.get("compatibility") if isinstance(record.get("compatibility"), Mapping) else {}
    surfaces = [str(item) for item in compatibility.get("changed_surfaces") or [] if isinstance(item, str)]
    ahead = _int(divergence.get("ahead_by"))
    reasons = []
    if ahead:
        touching = f", touching {', '.join(surfaces[:3])}" if surfaces else ""
        reasons.append(f"Adds {ahead} commit{'s' if ahead != 1 else ''} on top of DeepSeek Harness{touching}.")
    files = _int(divergence.get("listed_file_count"))
    if files:
        reasons.append(f"Changes {files}{'+' if divergence.get('files_truncated') else ''} files.")
    if evidence:
        endorsed = list(evidence.get("endorsed_by") or [])
        if endorsed:
            reasons.append(f"Starred by Harness contributors ({', '.join('@' + login for login in endorsed[:2])}).")
    pushed = _instant(record.get("pushed_at"))
    if pushed:
        # Month and year stay true for as long as the published feed is current.
        reasons.append(f"Updated in {pushed:%B %Y}.")
    return reasons[:4]


# --------------------------------------------------------------------------- scoring
def _cv_folds(identities: Sequence[str]) -> list[int]:
    return [int(hashlib.sha256(identity.encode()).hexdigest()[:8], 16) % CV_FOLDS for identity in identities]


def _plugin_population(records: Iterable[Mapping[str, Any]], observed_at: dt.datetime):
    population = []
    for record in records:
        if record.get("artifact_type") == "fork":
            continue
        evidence = _evidence(record)
        if not evidence:
            continue
        population.append((record, evidence, plugin_features(record, evidence, observed_at), math.log1p(_stars(record))))
    return population


def craft_index(rows: Sequence[Sequence[float]]) -> list[float]:
    """Sum of standardized features with equal weights: a transparent quality measure."""
    if not rows:
        return []
    columns = list(zip(*rows))
    scaled = []
    for column in columns:
        mean = sum(column) / len(column)
        spread = math.sqrt(sum((value - mean) ** 2 for value in column) / len(column))
        scaled.append([(value - mean) / spread if spread else 0.0 for value in column])
    return [sum(values) for values in zip(*scaled)]


def fit_attention(records: Sequence[Mapping[str, Any]], observed_at: dt.datetime) -> tuple[Ridge | None, dict[str, Any]]:
    population = _plugin_population(records, observed_at)
    if len(population) < MIN_TRAINING:
        return None, {"model": MODEL, "status": "insufficient_evidence", "training_count": len(population)}
    rows = [item[2] for item in population]
    targets = [item[3] for item in population]
    folds = _cv_folds([str(item[0].get("artifact_id")) for item in population])
    held_out: list[tuple[float, float]] = []
    for fold in range(CV_FOLDS):
        train = [index for index, value in enumerate(folds) if value != fold]
        test = [index for index, value in enumerate(folds) if value == fold]
        if len(train) < MIN_TRAINING // 2 or not test:
            continue
        model = Ridge().fit([rows[i] for i in train], [targets[i] for i in train])
        held_out.extend((model.predict(rows[i]), targets[i]) for i in test)
    model = Ridge().fit(rows, targets)
    predicted = [pair[0] for pair in held_out]
    actual = [pair[1] for pair in held_out]
    mean = sum(actual) / len(actual) if actual else 0.0
    total = sum((value - mean) ** 2 for value in actual)
    residual = sum((p - a) ** 2 for p, a in held_out)
    weights = {name: round(weight, 4) for name, weight in zip(PLUGIN_FEATURES, model.weights)}
    return model, {
        "model": MODEL,
        "status": "fitted",
        "training_count": len(population),
        "target": "log(1 + stars)",
        "features": list(PLUGIN_FEATURES),
        "standardized_weights": weights,
        "cross_validation": {
            "folds": CV_FOLDS,
            "spearman": spearman(predicted, actual),
            "r2": round(1 - residual / total, 4) if total else None,
        },
    }


def _fork_signal(record: Mapping[str, Any], default_description: str, observed_at: dt.datetime) -> float | None:
    divergence = record.get("divergence") if isinstance(record.get("divergence"), Mapping) else None
    ahead = _int((divergence or {}).get("ahead_by"))
    if not ahead:
        return None
    compatibility = record.get("compatibility") if isinstance(record.get("compatibility"), Mapping) else {}
    surfaces = len([item for item in compatibility.get("changed_surfaces") or [] if isinstance(item, str)])
    pushed = _instant(record.get("pushed_at"))
    push_age = (observed_at - pushed).days if pushed else 9999
    description = str(record.get("description") or "")
    own_description = bool(description) and description != default_description and not description.startswith("No repository description")
    return (
        2.0 * math.log1p(ahead)
        + 0.6 * min(surfaces, 6)
        + (2.0 if push_age <= 60 else 1.0 if push_age <= 180 else 0.0)
        + (1.5 if own_description else 0.0)
    )


def hidden_ceiling(records: Sequence[Mapping[str, Any]]) -> int:
    """Stars above which a plugin is not hidden: the ecosystem's 95th percentile, clamped."""
    stars = sorted(_stars(record) for record in records if record.get("artifact_type") != "fork")
    if not stars:
        return HIDDEN_STAR_CEILING
    value = stars[min(len(stars) - 1, int(HIDDEN_STAR_PERCENTILE * len(stars)))]
    return max(MIN_HIDDEN_CEILING, min(HIDDEN_STAR_CEILING, value))


def is_fork_of_fork(record: Mapping[str, Any]) -> bool:
    parent = str(record.get("parent_repository") or "").casefold()
    source = str(record.get("source_repository") or "").casefold()
    return bool(parent and source and parent != source)


def _gate(
    record: Mapping[str, Any], evidence: Mapping[str, Any] | None, observed_at: dt.datetime, ceiling: int = HIDDEN_STAR_CEILING,
) -> list[str]:
    """Reasons a record cannot be a gem (empty when it may be)."""
    blocked = []
    if record.get("archived") is True or (evidence or {}).get("archived"):
        blocked.append("archived")
    if not _license(record, evidence):
        blocked.append("no license")
    if _stars(record) > ceiling:
        blocked.append("already well known")
    pushed = _instant((evidence or {}).get("pushed_at")) or _instant(record.get("pushed_at"))
    if not pushed or (observed_at - pushed).days > MAX_PUSH_AGE_DAYS:
        blocked.append("not updated in the last year")
    description = str(record.get("description") or "")
    if len(description) < 24 or description.startswith("No repository description"):
        blocked.append("no description")
    return blocked


def score_records(
    records: Sequence[Mapping[str, Any]], observed_at: dt.datetime,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Return a v3 report for every evidence-backed plugin and every analyzed fork."""
    model, validation = fit_attention(records, observed_at)
    ceiling = hidden_ceiling(records)
    validation = {**validation, "hidden_star_ceiling": ceiling}
    reports: dict[str, dict[str, Any]] = {}

    # Plugins: built-like percentile, attention-gap percentile, outside validation.
    population = _plugin_population(records, observed_at) if len(records) else []
    if len(population) < MIN_TRAINING:
        population = []
    cv = (validation.get("cross_validation") or {}).get("spearman")
    reliable = model is not None and isinstance(cv, (int, float)) and cv >= MIN_MODEL_SPEARMAN
    validation = {**validation, "ranking": "attention-model" if reliable else "craft-index"}
    if population:
        # "How well built" is an equal-weight craft index over creator-controlled
        # practices, so more tests, docs, or releases can only help. Age is left
        # out: it buys exposure, not quality. The model is used only to say what
        # attention a project like this usually gets.
        built = percentiles(craft_index([item[2][:-1] for item in population]))
        if reliable:
            predictions: list[float | None] = [model.predict(item[2]) for item in population]
            gaps = [prediction - item[3] for prediction, item in zip(predictions, population)]  # type: ignore[operator]
        else:
            # The model can't predict attention on this data, so no reason may claim
            # "projects like this usually have N stars"; compare ranks instead.
            star_rank = percentiles([item[3] for item in population])
            gaps = [quality - attention for quality, attention in zip(built, star_rank)]
            predictions = [None] * len(population)
        gap_rank = percentiles(gaps)
        for index, (record, evidence, _features, _target) in enumerate(population):
            stars = _stars(record)
            prediction = predictions[index]
            predicted_stars = max(0.0, math.expm1(prediction)) if prediction is not None else None
            validation_points = outside_validation(record, evidence)
            score = 45 * built[index] + 40 * gap_rank[index] + validation_points * 0.75
            blocked = _gate(record, evidence, observed_at, ceiling)
            if _int(evidence.get("readme_bytes")) < MIN_README_BYTES:
                blocked.append("README too short")
            if built[index] < 0.6:
                blocked.append("below the quality bar")
            if gaps[index] <= 0:
                blocked.append("attention already matches quality")
            reports[str(record["artifact_id"])] = {
                "score": max(0, min(100, round(score))),
                "built_percentile": round(100 * built[index]),
                "gap_percentile": round(100 * gap_rank[index]),
                "predicted_stars": round(predicted_stars, 1) if predicted_stars is not None else None,
                "outside_validation": round(validation_points, 1),
                "reasons": plugin_reasons(record, evidence, predicted_stars, stars),
                "blocked_by": blocked,
                "confidence": "evidence",
            }

    # Forks: what the fork added, plus outside validation.
    forks = [record for record in records if record.get("artifact_type") == "fork"]
    descriptions = Counter(str(record.get("description") or "") for record in forks)
    default_description = descriptions.most_common(1)[0][0] if descriptions else ""
    signals = []
    for record in forks:
        value = _fork_signal(record, default_description, observed_at)
        if value is not None:
            evidence = _evidence(record)
            value += (outside_validation(record, evidence) / 4 if evidence else 0.0)
            signals.append((record, evidence, value))
    ranks = percentiles([item[2] for item in signals])
    for (record, evidence, _value), rank in zip(signals, ranks):
        blocked = _gate(record, evidence, observed_at, ceiling)
        # Measured divergence outranks the push-time heuristic.
        if has_own_commits(record) is False and not _int(((record.get("divergence") or {}) if isinstance(record.get("divergence"), Mapping) else {}).get("ahead_by")):
            blocked.append("no commits of its own")
        if is_fork_of_fork(record):
            # Its divergence is measured against upstream, so most of it is the parent's work.
            blocked.append("copy of another fork")
        reports[str(record["artifact_id"])] = {
            "score": round(40 + 60 * rank),
            "built_percentile": None,
            "gap_percentile": None,
            "predicted_stars": None,
            "outside_validation": round(outside_validation(record, evidence), 1) if evidence else 0.0,
            "reasons": fork_reasons(record, evidence),
            "blocked_by": blocked,
            "confidence": "source-diff",
        }
    return reports, validation


def _visibility(stars: int) -> str:
    if stars <= 2:
        return "nearly unseen"
    if stars <= 10:
        return "hidden"
    if stars <= HIDDEN_STAR_CEILING:
        return "emerging"
    return "well known"


def _research(record: Mapping[str, Any], report: Mapping[str, Any]) -> dict[str, Any]:
    """A v3 report shaped so older readers of the v2 queue keep working."""
    package = record.get("package") if isinstance(record.get("package"), Mapping) else {}
    signals = [
        {"id": "built-like", "points": report["built_percentile"], "evidence": f"percentile {report['built_percentile']}"}
        if report.get("built_percentile") is not None else None,
        {"id": "attention-gap", "points": report["gap_percentile"], "evidence": f"percentile {report['gap_percentile']}"}
        if report.get("gap_percentile") is not None else None,
        {"id": "outside-validation", "points": int(round(report["outside_validation"] or 0)), "evidence": "endorsements, issues, pull requests, contributors"},
    ]
    return {
        "policy": POLICY,
        "artifact_id": str(record.get("artifact_id")),
        "subject": {
            "package_name": str(package.get("name") or "")[:214],
            "package_version": str(package.get("version") or "")[:64],
            "repository_url": str(record.get("repository_url") or "")[:512],
            "commit": str(record.get("head_sha") or "")[:40],
        },
        "score": report["score"],
        "rank": None,
        "quality_rank": None,
        "visibility": _visibility(_stars(record)),
        "confidence": report["confidence"],
        "candidate": not report["blocked_by"],
        "capabilities": capabilities(record),
        "signals": [item for item in signals if item],
        "gaps": list(report["blocked_by"])[:12],
        "reasons": list(report["reasons"]),
        "built_percentile": report.get("built_percentile"),
        "gap_percentile": report.get("gap_percentile"),
        # Whole numbers only: signed registry snapshots reject floats.
        "predicted_stars": int(round(report["predicted_stars"])) if report.get("predicted_stars") is not None else None,
        "security_verified": False,
        "executed": False,
    }


# --------------------------------------------------------------------------- packs
def _reason_kind(reason: str) -> str:
    """Reasons of one kind share their opening words ("Starred by Harness contributors …")."""
    return " ".join(re.sub(r"[^a-z ]", " ", reason.casefold()).split()[:3])


def compose_packs(
    records: Sequence[Mapping[str, Any]], reports: Mapping[str, Mapping[str, Any]], observed_at: dt.datetime,
) -> list[dict[str, Any]]:
    """Themed packs of complementary plugins, chosen by how well they are built.

    Packs favour quality over obscurity: a pack should simply be good. Each slot
    takes the best eligible plugin with that capability, with one plugin per
    owner within a pack and a preference for plugins not already used in an
    earlier pack.
    """
    pool = []
    for record in records:
        if record.get("artifact_type") == "fork":
            continue
        report = reports.get(str(record.get("artifact_id")))
        evidence = _evidence(record)
        if not report or not evidence:
            continue
        blocked = [reason for reason in report.get("blocked_by") or [] if reason not in {
            "already well known", "attention already matches quality", "below the quality bar",
        }]
        if blocked or (report.get("built_percentile") or 0) < 50:
            continue
        quality = (report.get("built_percentile") or 0) + report.get("outside_validation", 0) + 2 * math.log1p(_stars(record))
        # A pack role needs a plugin that is clearly about it: named for it, or
        # tagged and described that way. One stray topic ("web-search") is not enough.
        strong = [capability for capability, strength in capability_strengths(record) if strength >= PACK_MIN_STRENGTH]
        if strong:
            pool.append((record, report, quality, strong))
    pool.sort(key=lambda item: (-item[2], str(item[0].get("artifact_id"))))
    used: Counter[str] = Counter()
    packs = []
    for theme in PACK_THEMES:
        members = []
        owners: set[str] = set()
        chosen: set[str] = set()
        said: set[str] = set()
        for slot in theme["slots"]:
            options = [
                item for item in pool
                if item[3][0] == slot  # the plugin's main purpose, not a side feature
                and not used[str(item[0]["artifact_id"])]  # each plugin appears in one pack
                and _owner(item[0]) not in owners
            ]
            if not options:
                continue
            # Prefer plugins whose main purpose is this slot, then unused ones, then quality.
            record, report, quality, _caps = min(options, key=lambda item: (-item[2], str(item[0]["artifact_id"])))
            identity = str(record["artifact_id"])
            chosen.add(identity)
            owners.add(_owner(record))
            used[identity] += 1
            # Each member's note says something the others in the pack don't.
            reasons = list(report.get("reasons") or [])
            why = next((reason for reason in reasons if _reason_kind(reason) not in said), None)
            why = why or str(record.get("description") or "")[:140] or (reasons[0] if reasons else "")
            said.add(_reason_kind(why))
            members.append({
                "artifact_id": identity,
                "role": SLOT_LABELS.get(slot, slot.title()),
                "name": str(record.get("name") or "")[:120],
                "owner": str(record.get("owner") or "")[:80],
                "why": why,
            })
        if len(members) >= 3:
            packs.append({
                "id": theme["id"],
                "title": theme["title"],
                "summary": theme["summary"],
                "members": members,
                "policy": PACKS_POLICY,
            })
    return packs


# --------------------------------------------------------------------------- queue
def evidence_coverage(records: Sequence[Mapping[str, Any]]) -> float:
    plugins = [record for record in records if record.get("artifact_type") != "fork"]
    if not plugins:
        return 0.0
    return sum(1 for record in plugins if _evidence(record)) / len(plugins)


def discovery_queue(snapshot: Mapping[str, Any], *, limit: int = MAX_DISCOVERY_QUEUE) -> dict[str, Any]:
    """Build the published queue; falls back to the metadata policy without evidence."""
    records = [
        record for record in [*(snapshot.get("entries") or []), *(snapshot.get("supplemental_entries") or [])]
        if isinstance(record, Mapping) and record.get("artifact_id")
    ]
    coverage = evidence_coverage(records)
    with_evidence = sum(1 for record in records if record.get("artifact_type") != "fork" and _evidence(record))
    if coverage < MIN_EVIDENCE_COVERAGE or with_evidence < MIN_TRAINING:
        queue = metadata_queue(snapshot, limit=limit)
        queue["quality"]["discovery"] = {"policy": queue["policy"], "fallback": "too little evidence", "evidence_coverage": round(coverage, 4)}
        queue["packs"] = []
        return queue

    observed_at = _instant(snapshot.get("fetched_at")) or dt.datetime.now(dt.timezone.utc)
    reports, validation = score_records(records, observed_at)
    by_id = {str(record["artifact_id"]): record for record in records}
    candidates: list[dict[str, Any]] = []
    for kind, cap in (("plugin", MAX_PLUGIN_GEMS), ("fork", MAX_FORK_GEMS)):
        group = [
            (by_id[identity], _research(by_id[identity], report))
            for identity, report in reports.items()
            if (by_id[identity].get("artifact_type") == "fork") == (kind == "fork")
        ]
        group.sort(key=lambda item: (-item[1]["score"], _stars(item[0]), str(item[0]["artifact_id"])))
        for quality_rank, (_record, research) in enumerate(group, 1):
            research["quality_rank"] = quality_rank
        selected, selections = _diverse_selection(group)
        for rank, (record, research) in enumerate(selected[:cap], 1):
            research["rank"] = rank
            research["selection"] = selections.get(str(record["artifact_id"]))
            candidates.append({"artifact": dict(record), "research": research})
    candidates.sort(key=lambda item: (item["research"]["rank"], str(item["artifact"].get("artifact_type")), str(item["artifact"]["artifact_id"])))
    candidates = candidates[:limit]
    packs = compose_packs(records, reports, observed_at)
    owners = Counter(_owner(item["artifact"]) for item in candidates)
    scores = [item["research"]["score"] for item in candidates]
    return {
        "schema": DISCOVERY_QUEUE_SCHEMA,
        "policy": POLICY,
        "snapshot_id": str(snapshot.get("snapshot_id") or "")[:256],
        "fetched_at": str(snapshot.get("fetched_at") or "")[:64],
        "provenance": dict(snapshot.get("provenance")) if isinstance(snapshot.get("provenance"), Mapping) else {},
        "source_count": len(records),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "packs": packs,
        "quality": {
            "selection_policy": SELECTION_POLICY,
            "score_window": 5,
            "by_type": dict(Counter(str(item["artifact"].get("artifact_type")) for item in candidates)),
            "by_capability": dict(Counter(
                capability for item in candidates for capability in item["research"]["capabilities"] or ["other"]
            )),
            "by_visibility": dict(Counter(item["research"]["visibility"] for item in candidates)),
            "unique_owners": len(owners),
            "max_candidates_per_owner": max(owners.values(), default=0),
            "score_min": min(scores, default=None),
            "score_max": max(scores, default=None),
            "discovery": {
                "policy": POLICY,
                "evidence_coverage": round(coverage, 4),
                "scored_count": len(reports),
                "attention_model": validation,
            },
        },
        "claims": {"metadata_only": True, "security_verified": False, "executed": False},
    }


def annotate(snapshot: dict[str, Any], queue: Mapping[str, Any]) -> int:
    """Write a compact discovery summary onto scored registry records in place."""
    by_id = {
        str(item["research"]["artifact_id"]): item["research"]
        for item in queue.get("candidates") or []
        if isinstance(item, Mapping) and isinstance(item.get("research"), Mapping)
    }
    count = 0
    for key in ("entries", "supplemental_entries"):
        for record in snapshot.get(key) or []:
            if not isinstance(record, dict):
                continue
            research = by_id.get(str(record.get("artifact_id")))
            record.pop("discovery", None)
            if research:
                # The desktop store reads the registry only, so it carries the full report.
                record["discovery"] = dict(research)
                count += 1
    snapshot["discovery_policy"] = str(queue.get("policy") or "")
    snapshot["discovery_packs"] = [dict(pack) for pack in queue.get("packs") or [] if isinstance(pack, Mapping)]
    return count
