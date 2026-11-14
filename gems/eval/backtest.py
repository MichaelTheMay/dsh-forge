"""Backtest: would the system have spotted projects before they were noticed?

Rewind to a date some weeks ago. For a sample of plugins that were obscure then,
take the code as it was on that date, score it with the automatic part of the
pipeline, and compare the score with how many stars each project has gained since.

Only public GitHub facts are read. The token is used for rate limits, not access.
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import os
from pathlib import Path
import random
import re
import shutil
from typing import Any, Callable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..fetch import FetchError, fetch_commit
from ..inspection import inspect_tree
from ..rank import substance_score

BACKTEST_SCHEMA = "dsh-forge.gem-backtest/v1"
GRAPHQL_URL = "https://api.github.com/graphql"
BATCH = 15
MAX_STARS_NOW = 400
HIDDEN_THEN = 10
STARGAZER_PAGES = 4

_SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}$")

Post = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]


class BacktestError(RuntimeError):
    pass


def github_post(token: str) -> Post:
    def post(query: str, variables: Mapping[str, Any]) -> Mapping[str, Any]:
        request = Request(
            GRAPHQL_URL,
            data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                     "User-Agent": "dsh-forge-gem-backtest/1"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                payload = json.loads(response.read(16 * 1024 * 1024))
        except (HTTPError, URLError, ValueError, TimeoutError) as error:
            raise BacktestError(f"GitHub request failed: {error}") from error
        return payload if isinstance(payload, dict) else {}
    return post


def load_population(registry_path: str | Path) -> list[dict[str, Any]]:
    """Plugins from a published registry file: name and current stars."""
    source = Path(registry_path)
    raw = source.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    registry = json.loads(raw)
    population = []
    for group in ("supplemental_entries", "entries"):
        for record in registry.get(group) or []:
            name = record.get("full_name")
            stars = record.get("github_stars")
            if (
                record.get("artifact_type") == "plugin" and isinstance(name, str) and _SLUG.match(name)
                and isinstance(stars, int) and not record.get("archived") and not record.get("parent_repository")
            ):
                population.append({"full_name": name, "stars_now": stars})
    return population


def sample(population: Sequence[Mapping[str, Any]], size: int, seed: int = 7) -> list[dict[str, Any]]:
    """A repeatable sample spread across star counts, so growth and no-growth both appear."""
    bands = [(0, 0), (1, 2), (3, 9), (10, 39), (40, MAX_STARS_NOW)]
    generator = random.Random(seed)
    chosen: list[dict[str, Any]] = []
    per_band = max(1, size // len(bands))
    for low, high in bands:
        members = sorted(
            (dict(item) for item in population if low <= item["stars_now"] <= high),
            key=lambda item: item["full_name"].casefold(),
        )
        generator.shuffle(members)
        chosen.extend(members[:per_band])
    return chosen[:size]


def _history_query(names: Sequence[str]) -> str:
    parts = []
    for index, name in enumerate(names):
        owner, repo = name.split("/", 1)
        parts.append(
            f'r{index}: repository(owner: {json.dumps(owner)}, name: {json.dumps(repo)}) {{'
            " createdAt stargazerCount"
            " defaultBranchRef { target { ... on Commit { history(first: 1, until: $until) { nodes { oid } } } } }"
            " stargazers(first: 100, orderBy: {field: STARRED_AT, direction: DESC}) {"
            " pageInfo { hasNextPage endCursor } edges { starredAt } } }"
        )
    return "query($until: GitTimestamp!) {" + " ".join(parts) + "}"


_MORE_STARS = (
    "query($owner: String!, $name: String!, $after: String!) { repository(owner: $owner, name: $name) {"
    " stargazers(first: 100, after: $after, orderBy: {field: STARRED_AT, direction: DESC}) {"
    " pageInfo { hasNextPage endCursor } edges { starredAt } } } }"
)


def collect_history(
    names: Sequence[str], then: dt.datetime, post: Post, *, report: Callable[[str], None] = lambda _line: None,
) -> dict[str, dict[str, Any]]:
    """For each repository: the commit that was current at ``then`` and star counts then and now."""
    until = then.strftime("%Y-%m-%dT%H:%M:%SZ")
    found: dict[str, dict[str, Any]] = {}
    for start in range(0, len(names), BATCH):
        batch = list(names[start:start + BATCH])
        data = post(_history_query(batch), {"until": until}).get("data") or {}
        for index, name in enumerate(batch):
            node = data.get(f"r{index}")
            if not isinstance(node, Mapping):
                continue
            created = str(node.get("createdAt") or "")
            if not created or created > until:
                continue  # did not exist yet
            history = (((node.get("defaultBranchRef") or {}).get("target") or {}).get("history") or {}).get("nodes") or []
            if not history:
                continue
            stargazers = node.get("stargazers") or {}
            times = [edge.get("starredAt") for edge in stargazers.get("edges") or []]
            page = stargazers.get("pageInfo") or {}
            owner, repo = name.split("/", 1)
            pages = 1
            # Newest first: stop paging once a page reaches back before the rewind date.
            while page.get("hasNextPage") and pages < STARGAZER_PAGES and (not times or times[-1] > until):
                more = (post(_MORE_STARS, {"owner": owner, "name": repo, "after": page["endCursor"]}).get("data") or {})
                more = ((more.get("repository") or {}).get("stargazers")) or {}
                times.extend(edge.get("starredAt") for edge in more.get("edges") or [])
                page = more.get("pageInfo") or {}
                pages += 1
            if page.get("hasNextPage") and times and times[-1] > until:
                continue  # too many recent stars to count within the page limit
            now = int(node.get("stargazerCount") or 0)
            gained = sum(1 for moment in times if isinstance(moment, str) and moment > until)
            found[name] = {"commit_then": history[0]["oid"], "stars_then": max(0, now - gained), "stars_gained": gained}
        report(f"history {min(start + BATCH, len(names))}/{len(names)}")
    return found


def collect(
    registry_path: str | Path,
    workdir: str | Path,
    *,
    post: Post,
    now: dt.datetime,
    days_back: int = 60,
    size: int = 200,
    seed: int = 7,
    fetch: Callable[..., Path] = fetch_commit,
    report: Callable[[str], None] = lambda _line: None,
) -> dict[str, Any]:
    """Build the backtest dataset: measurements as of the rewind date plus the outcome."""
    then = now - dt.timedelta(days=days_back)
    chosen = sample(load_population(registry_path), size, seed)
    history = collect_history([item["full_name"] for item in chosen], then, post, report=report)
    rows = []
    for name, facts in sorted(history.items()):
        if facts["stars_then"] > HIDDEN_THEN:
            continue  # already noticed at the rewind date
        directory = Path(workdir) / name.replace("/", "__")
        shutil.rmtree(directory, ignore_errors=True)
        try:
            fetch(name, facts["commit_then"], directory)
            inspection = inspect_tree(directory)
        except FetchError as error:
            report(f"skipped {name}: {error}")
            continue
        finally:
            shutil.rmtree(directory, ignore_errors=True)
        inspection.pop("fingerprints", None)
        rows.append({"full_name": name, **facts, "inspection": inspection})
        report(f"measured {name}")
    return {
        "schema": BACKTEST_SCHEMA,
        "rewound_to": then.strftime("%Y-%m-%d"),
        "collected_at": now.strftime("%Y-%m-%d"),
        "days": days_back,
        "sampled": len(chosen),
        "rows": rows,
    }


def score_rows(dataset: Mapping[str, Any], scorer: Callable[[Mapping[str, Any]], float] = substance_score) -> dict[str, Any]:
    """Attach the system's score to every row, ready for the scoreboard."""
    rows = [
        {"full_name": row["full_name"], "score": scorer(row["inspection"]), "stars_gained": row["stars_gained"],
         "stars_then": row["stars_then"]}
        for row in dataset.get("rows") or []
    ]
    return {"schema": BACKTEST_SCHEMA, "rewound_to": dataset.get("rewound_to"), "days": dataset.get("days"), "rows": rows}


def token_from_environment() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise BacktestError("Set GITHUB_TOKEN to collect a backtest (any read-only token)")
    return token
