"""One comparable row of numbers per version of the gem system."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .metrics import pairwise_agreement, precision_at_k, spearman, top_share_lift

HISTORY = Path(__file__).resolve().parent / "history.jsonl"


def score(
    picks: Mapping[str, Any],
    labels: Mapping[str, bool],
    backtest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Measure one picks document against human labels and, if given, a backtest.

    Label metrics: of the picks a person judged, how many did they call a gem, and
    does the ranking put their gems above their non-gems.
    Backtest metrics: among projects that were obscure at an earlier date, did the
    ones this system scores highly gain more stars afterwards.
    """
    ordered = [str(pick["full_name"]).casefold() for pick in picks.get("picks") or []]
    scores = {str(pick["full_name"]).casefold(): float(pick["score"]) for pick in picks.get("picks") or []}
    p10, n10 = precision_at_k(ordered, labels, 10)
    p30, n30 = precision_at_k(ordered, labels, 30)
    row: dict[str, Any] = {
        "policy": picks.get("policy"),
        "generated_at": picks.get("generated_at"),
        "picks": len(ordered),
        "reviewed": (picks.get("counts") or {}).get("reviewed"),
        "labels": len(labels),
        "precision_at_10": p10,
        "labelled_in_top_10": n10,
        "precision_at_30": p30,
        "labelled_in_top_30": n30,
        "label_agreement": pairwise_agreement(scores, labels),
    }
    if backtest and backtest.get("rows"):
        rows = [item for item in backtest["rows"] if isinstance(item.get("score"), (int, float))]
        predicted = [float(item["score"]) for item in rows]
        gained = [float(item["stars_gained"]) for item in rows]
        row["backtest_repositories"] = len(rows)
        row["backtest_spearman"] = spearman(predicted, gained)
        row["backtest_lift_top_fifth"] = top_share_lift(predicted, gained, 0.2)
    return row


def append_history(row: Mapping[str, Any], note: str, path: str | Path = HISTORY) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({**row, "note": note[:200]}, sort_keys=True) + "\n")


def render(row: Mapping[str, Any]) -> str:
    def show(value: Any) -> str:
        return "n/a" if value is None else str(value)

    lines = [
        f"picks                  {show(row.get('picks'))}  (reviewed: {show(row.get('reviewed'))})",
        f"human labels           {show(row.get('labels'))}",
        f"precision in top 10    {show(row.get('precision_at_10'))}  ({show(row.get('labelled_in_top_10'))} labelled)",
        f"precision in top 30    {show(row.get('precision_at_30'))}  ({show(row.get('labelled_in_top_30'))} labelled)",
        f"label agreement        {show(row.get('label_agreement'))}  (0.5 is chance, 1.0 is perfect)",
    ]
    if "backtest_repositories" in row:
        lines += [
            f"backtest repositories  {show(row.get('backtest_repositories'))}",
            f"backtest correlation   {show(row.get('backtest_spearman'))}  (score vs stars gained later)",
            f"backtest lift          {show(row.get('backtest_lift_top_fifth'))}  (top fifth vs average; 1.0 is chance)",
        ]
    return "\n".join(lines)
