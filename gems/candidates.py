"""Stage 1 hand-off: choose which repositories are worth opening.

Input is the discovery queue the daily job already publishes
(``hidden-gems.json`` or ``.json.gz``). Each entry pairs a catalog record with the
statistics-only research report for it. This module never contacts the network.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

MAX_QUEUE_BYTES = 64 * 1024 * 1024
DEFAULT_LIMIT = 120
# Above this many stars a project is no longer "hidden", whatever its quality.
STAR_CEILING = 150

_SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")


class CandidateError(ValueError):
    """The queue file is missing, malformed or too large."""


def load_queue(path: str | Path) -> dict[str, Any]:
    """Read a discovery queue from a plain or gzipped JSON file, with a size bound."""
    source = Path(path).expanduser()
    try:
        raw = source.read_bytes()
    except OSError as error:
        raise CandidateError(f"Cannot read the discovery queue: {error}") from error
    if raw[:2] == b"\x1f\x8b":
        try:
            with gzip.open(source, "rb") as handle:
                raw = handle.read(MAX_QUEUE_BYTES + 1)
        except (OSError, EOFError) as error:
            raise CandidateError("The discovery queue is not valid gzip") from error
    if len(raw) > MAX_QUEUE_BYTES:
        raise CandidateError("The discovery queue is larger than expected")
    try:
        queue = json.loads(raw)
    except ValueError as error:
        raise CandidateError("The discovery queue is not valid JSON") from error
    if not isinstance(queue, dict) or not isinstance(queue.get("candidates"), list):
        raise CandidateError("The discovery queue has no candidate list")
    return queue


def _candidate(entry: Mapping[str, Any]) -> dict[str, Any] | None:
    artifact = entry.get("artifact")
    research = entry.get("research")
    if not isinstance(artifact, Mapping) or not isinstance(research, Mapping):
        return None
    full_name = str(artifact.get("full_name") or "")
    commit = str(artifact.get("head_sha") or "")
    stars = artifact.get("github_stars")
    if not _SLUG.match(full_name) or not _SHA.match(commit):
        return None
    if not isinstance(stars, int) or isinstance(stars, bool) or stars < 0:
        stars = 0
    package = artifact.get("package") if isinstance(artifact.get("package"), Mapping) else {}
    return {
        "artifact_id": str(artifact.get("artifact_id") or ""),
        "artifact_type": str(artifact.get("artifact_type") or ""),
        "full_name": full_name,
        "commit": commit,
        "stars": stars,
        "archived": bool(artifact.get("archived")),
        "is_fork": bool(artifact.get("parent_repository")),
        "description": str(artifact.get("description") or "")[:500],
        "package_name": str(package.get("name") or "")[:214],
        "pushed_at": str(artifact.get("pushed_at") or ""),
        "capabilities": [str(item) for item in (research.get("capabilities") or [])][:8],
        "stage1": {
            "policy": str(research.get("policy") or ""),
            "score": research.get("score") if isinstance(research.get("score"), (int, float)) else 0,
            "rank": research.get("rank") if isinstance(research.get("rank"), int) else None,
            "confidence": str(research.get("confidence") or ""),
            "reasons": [str(item) for item in (research.get("reasons") or [])][:6],
        },
    }


def select(
    queue: Mapping[str, Any],
    *,
    limit: int = DEFAULT_LIMIT,
    star_ceiling: int = STAR_CEILING,
    artifact_types: Iterable[str] = ("plugin",),
) -> list[dict[str, Any]]:
    """Pick the repositories the deep stage should open, best stage-1 score first.

    Dropped: archived repositories, forks (a fork's code is mostly its parent's, so
    reading it says little about the fork), anything already well known, anything
    stage 1 itself did not consider a candidate, and a second repository from an
    owner already chosen (one voice per owner keeps the picks varied).
    """
    wanted = set(artifact_types)
    chosen: list[dict[str, Any]] = []
    owners: set[str] = set()
    def order(entry: Mapping[str, Any]) -> tuple[float, str]:
        research = entry.get("research") if isinstance(entry.get("research"), Mapping) else {}
        artifact = entry.get("artifact") if isinstance(entry.get("artifact"), Mapping) else {}
        score = research.get("score")
        return (
            -float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else 0.0,
            str(artifact.get("full_name") or "").casefold(),
        )

    ordered = sorted(
        (entry for entry in queue.get("candidates") or [] if isinstance(entry, Mapping)),
        key=order,
    )
    for entry in ordered:
        if len(chosen) >= limit:
            break
        research = entry.get("research") if isinstance(entry.get("research"), Mapping) else {}
        if research.get("candidate") is False:
            continue
        candidate = _candidate(entry)
        if candidate is None or candidate["artifact_type"] not in wanted:
            continue
        if candidate["archived"] or candidate["is_fork"] or candidate["stars"] > star_ceiling:
            continue
        owner = candidate["full_name"].split("/", 1)[0].casefold()
        if owner in owners:
            continue
        owners.add(owner)
        chosen.append(candidate)
    return chosen
