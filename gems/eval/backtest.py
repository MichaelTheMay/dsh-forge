"""Backtest: would the system have spotted projects before they were noticed?

Take two dated copies of the published registry, weeks apart. Among plugins that
were obscure in the older copy, some took off by the newer one and most did not.
Fetch the code each project had at the older date, score it with the automatic
part of the pipeline, and check whether the ones that took off scored higher.

The sample deliberately over-represents projects that took off (they are rare), so
the headline number is one that does not depend on that mix: the chance that a
project which took off outscores one which did not (0.5 is a coin flip).

No GitHub API is used: star counts and commits come from the two registry files.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import random
import re
import shutil
from typing import Any, Callable, Mapping, Sequence

from ..fetch import FetchError, fetch_commit
from ..inspection import inspect_tree
from ..rank import substance_score

BACKTEST_SCHEMA = "dsh-forge.gem-backtest/v2"
HIDDEN_THEN = 10
TOOK_OFF = 5

_SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


def load_plugins(registry_path: str | Path) -> tuple[dict[str, dict[str, Any]], str]:
    """Plugins from a registry file: {lower-cased name: facts}, and its date."""
    raw = Path(registry_path).read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    registry = json.loads(raw)
    plugins: dict[str, dict[str, Any]] = {}
    for group in ("supplemental_entries", "entries"):
        for record in registry.get(group) or []:
            name = record.get("full_name")
            stars = record.get("github_stars")
            if (
                record.get("artifact_type") == "plugin" and isinstance(name, str) and _SLUG.match(name)
                and isinstance(stars, int) and not isinstance(stars, bool)
                and not record.get("archived") and not record.get("parent_repository")
            ):
                plugins[name.casefold()] = {"full_name": name, "stars": stars, "commit": str(record.get("head_sha") or "")}
    return plugins, str(registry.get("fetched_at") or "")[:10]


def outcomes(then: Mapping[str, Mapping[str, Any]], now: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Every plugin that was obscure then and still exists now, with what it gained."""
    rows = []
    for key, earlier in then.items():
        later = now.get(key)
        if later is None or earlier["stars"] > HIDDEN_THEN or not _SHA.match(earlier["commit"]):
            continue
        rows.append({
            "full_name": earlier["full_name"], "commit_then": earlier["commit"],
            "stars_then": earlier["stars"], "stars_gained": later["stars"] - earlier["stars"],
        })
    return sorted(rows, key=lambda row: row["full_name"].casefold())


def sample(rows: Sequence[Mapping[str, Any]], *, took_off: int, others: int, seed: int = 7) -> list[dict[str, Any]]:
    """A repeatable sample: up to ``took_off`` projects that took off and ``others`` that did not."""
    generator = random.Random(seed)
    risers = [dict(row) for row in rows if row["stars_gained"] >= TOOK_OFF]
    rest = [dict(row) for row in rows if row["stars_gained"] < TOOK_OFF]
    generator.shuffle(risers)
    generator.shuffle(rest)
    return sorted(risers[:took_off] + rest[:others], key=lambda row: row["full_name"].casefold())


def collect(
    registry_then: str | Path,
    registry_now: str | Path,
    workdir: str | Path,
    *,
    took_off: int = 150,
    others: int = 250,
    seed: int = 7,
    fetch: Callable[..., Path] = fetch_commit,
    report: Callable[[str], None] = lambda _line: None,
) -> dict[str, Any]:
    """Build the backtest dataset: measurements of the older code plus what happened next."""
    then, then_date = load_plugins(registry_then)
    now, now_date = load_plugins(registry_now)
    population = outcomes(then, now)
    chosen = sample(population, took_off=took_off, others=others, seed=seed)
    rows = []
    for index, row in enumerate(chosen, 1):
        directory = Path(workdir) / row["full_name"].replace("/", "__")
        shutil.rmtree(directory, ignore_errors=True)
        try:
            fetch(row["full_name"], row["commit_then"], directory)
            inspection = inspect_tree(directory)
        except FetchError as error:
            report(f"skipped {row['full_name']}: {error}")
            continue
        finally:
            shutil.rmtree(directory, ignore_errors=True)
        inspection.pop("fingerprints", None)
        rows.append({**row, "inspection": inspection})
        if index % 25 == 0:
            report(f"measured {index}/{len(chosen)}")
    return {
        "schema": BACKTEST_SCHEMA,
        "then": then_date,
        "now": now_date,
        "took_off_means": f"gained {TOOK_OFF} or more stars from {HIDDEN_THEN} or fewer",
        "population": len(population),
        "population_took_off": sum(1 for row in population if row["stars_gained"] >= TOOK_OFF),
        "rows": rows,
    }


def score_rows(dataset: Mapping[str, Any], scorer: Callable[[Mapping[str, Any]], float] = substance_score) -> dict[str, Any]:
    """Attach the system's score to every row, ready for the scoreboard."""
    rows = [
        {"full_name": row["full_name"], "score": scorer(row["inspection"]), "stars_gained": row["stars_gained"],
         "took_off": row["stars_gained"] >= TOOK_OFF}
        for row in dataset.get("rows") or []
    ]
    return {"schema": BACKTEST_SCHEMA, "then": dataset.get("then"), "now": dataset.get("now"), "rows": rows}
