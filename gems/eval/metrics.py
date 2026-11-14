"""Small, dependency-free ranking metrics."""

from __future__ import annotations

from typing import Mapping, Sequence


def precision_at_k(ranked: Sequence[str], labels: Mapping[str, bool], k: int) -> tuple[float | None, int]:
    """Among the first ``k`` ranked items that have a label, the share labelled good.

    Returns (precision or None when none are labelled, how many were labelled).
    """
    judged = [labels[name] for name in ranked[:k] if name in labels]
    if not judged:
        return None, 0
    return round(sum(judged) / len(judged), 3), len(judged)


def pairwise_agreement(scores: Mapping[str, float], labels: Mapping[str, bool]) -> float | None:
    """How often a labelled-good item scores above a labelled-bad one (ties count half).

    0.5 is chance, 1.0 is perfect. Items with a label but no score count as scoring
    lowest: leaving a good project out is a miss, leaving a bad one out is a hit.
    """
    floor = min(scores.values(), default=0.0) - 1.0
    good = [scores.get(name, floor) for name, label in labels.items() if label]
    bad = [scores.get(name, floor) for name, label in labels.items() if not label]
    if not good or not bad:
        return None
    wins = sum(1.0 if g > b else 0.5 if g == b else 0.0 for g in good for b in bad)
    return round(wins / (len(good) * len(bad)), 3)


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        shared = (position + end) / 2 + 1
        for index in order[position:end + 1]:
            ranks[index] = shared
        position = end + 1
    return ranks


def spearman(left: Sequence[float], right: Sequence[float]) -> float | None:
    """Rank correlation, -1..1. None when it is undefined."""
    if len(left) != len(right) or len(left) < 3:
        return None
    a, b = _ranks(left), _ranks(right)
    mean_a, mean_b = sum(a) / len(a), sum(b) / len(b)
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if not var_a or not var_b:
        return None
    return round(cov / (var_a * var_b) ** 0.5, 3)


def top_share_lift(scores: Sequence[float], outcomes: Sequence[float], share: float = 0.2) -> float | None:
    """Mean outcome of the top-scored ``share`` divided by the mean outcome overall.

    1.0 means the top of the ranking did no better than picking at random.
    """
    if len(scores) != len(outcomes) or len(scores) < 5:
        return None
    overall = sum(outcomes) / len(outcomes)
    if overall <= 0:
        return None
    count = max(1, int(round(len(scores) * share)))
    top = sorted(range(len(scores)), key=lambda index: -scores[index])[:count]
    return round((sum(outcomes[index] for index in top) / count) / overall, 3)
