"""The steps of the gem pipeline as plain functions over files.

    queue file ──select──▶ candidates ──inspect──▶ inspections ─┐
                                              reviews folder ───┼──build──▶ gem-picks.json

Each step reads and writes JSON, so any step can be rerun, replaced or inspected
on its own.
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable, Mapping, Sequence

from . import INSPECTION_SCHEMA
from .candidates import DEFAULT_LIMIT, load_queue, select
from .fetch import FetchError, fetch_commit
from .inspection import copy_overlap, inspect_tree
from .rank import DEFAULT_WEIGHTS, Weights, not_featured, picks_document, rank
from .review import load_reviews


def write_json(path: str | Path, value: Any) -> None:
    """Write atomically so a reader never sees half a file."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=target.name + ".")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=1, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, target)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def clone_directory(workdir: str | Path, full_name: str) -> Path:
    return Path(workdir).expanduser() / full_name.replace("/", "__")


def inspect_candidates(
    candidates: Sequence[Mapping[str, Any]],
    workdir: str | Path,
    *,
    previous: Mapping[str, Any] | None = None,
    keep: bool = False,
    fetch: Callable[..., Path] = fetch_commit,
    report: Callable[[str], None] = lambda _line: None,
) -> dict[str, Any]:
    """Fetch and measure every candidate.

    A repository already measured at the same commit in ``previous`` is not fetched
    again. With ``keep`` the checkouts stay in ``workdir`` for a reviewer to read;
    otherwise each is deleted as soon as it has been measured.
    """
    earlier = (previous or {}).get("repositories") or {}
    repositories: dict[str, Any] = {}
    failures: dict[str, str] = {}
    for candidate in candidates:
        name, commit = candidate["full_name"], candidate["commit"]
        known = earlier.get(name)
        directory = clone_directory(workdir, name)
        if known and known.get("commit") == commit and (not keep or directory.is_dir()):
            repositories[name] = known
            continue
        shutil.rmtree(directory, ignore_errors=True)
        try:
            fetch(name, commit, directory)
            repositories[name] = {"commit": commit, "inspection": inspect_tree(directory)}
            report(f"inspected {name}")
        except FetchError as error:
            failures[name] = str(error)[:200]
            report(f"skipped {name}: {error}")
        finally:
            if not keep:
                shutil.rmtree(directory, ignore_errors=True)
    return {"schema": INSPECTION_SCHEMA, "repositories": repositories, "failures": failures}


def build_picks(
    queue: Mapping[str, Any],
    inspections: Mapping[str, Any],
    reviews_directory: str | Path,
    *,
    candidate_limit: int = DEFAULT_LIMIT,
    pick_limit: int = 60,
    weights: Weights = DEFAULT_WEIGHTS,
    now: dt.datetime | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Join the three inputs into the picks document. Returns (document, problems)."""
    candidates = select(queue, limit=candidate_limit)
    measured = {
        name: entry["inspection"]
        for name, entry in (inspections.get("repositories") or {}).items()
        if isinstance(entry, Mapping) and isinstance(entry.get("inspection"), Mapping)
    }
    reviews, problems = load_reviews(reviews_directory)
    overlap = copy_overlap(measured)
    picks = rank(candidates, measured, reviews, overlap, weights=weights, limit=pick_limit)
    moment = (now or dt.datetime.now(dt.timezone.utc)).replace(microsecond=0)
    document = picks_document(
        picks,
        generated_at=moment.isoformat().replace("+00:00", "Z"),
        queue=queue,
        considered=len(candidates),
        inspected=sum(1 for candidate in candidates if candidate["full_name"] in measured),
        excluded=not_featured(candidates, reviews, overlap, weights=weights),
    )
    return document, problems


def run(
    queue_path: str | Path,
    workdir: str | Path,
    reviews_directory: str | Path,
    output: str | Path,
    *,
    inspections_path: str | Path | None = None,
    candidate_limit: int = DEFAULT_LIMIT,
    keep: bool = False,
    report: Callable[[str], None] = lambda _line: None,
) -> dict[str, Any]:
    """The whole pipeline: what the daily job calls."""
    queue = load_queue(queue_path)
    candidates = select(queue, limit=candidate_limit)
    previous = None
    if inspections_path and Path(inspections_path).expanduser().is_file():
        previous = read_json(inspections_path)
    inspections = inspect_candidates(candidates, workdir, previous=previous, keep=keep, report=report)
    if inspections_path:
        write_json(inspections_path, inspections)
    document, problems = build_picks(queue, inspections, reviews_directory, candidate_limit=candidate_limit)
    write_json(output, document)
    return {"counts": document["counts"], "fetch_failures": len(inspections["failures"]), "review_problems": problems}
