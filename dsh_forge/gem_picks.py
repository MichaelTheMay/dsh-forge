"""Read the gem system's picks file and fold it into the published discovery queue.

This is the only place the app touches the separate ``gems`` package's output. The
contract is one JSON file (``dsh-forge.gem-picks/v1``); nothing is imported from
``gems``. Folding the picks into the queue, rather than publishing a new file,
means every existing reader (the public API, the desktop catalog store, the web
interface) shows the improved order without a contract change.

Pick text was written about untrusted repositories, so it is re-validated here.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping

PICKS_SCHEMA = "dsh-forge.gem-picks/v1"
MAX_PICKS_BYTES = 4 * 1024 * 1024
MAX_PICKS = 200
CONFIDENCES = {"reviewed", "reviewed at an earlier version", "measured"}
VERDICTS = {"gem", "solid", None}

_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
_MARKUP = re.compile(r"<[^>]{0,200}>")


class GemPicksError(ValueError):
    """The picks file is missing, malformed or outside its contract."""


def _text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return _MARKUP.sub("", _CONTROL.sub(" ", value)).strip()[:limit]


def load_picks(path: str | Path) -> dict[str, dict[str, Any]]:
    """Return {artifact_id: validated pick}, in rank order."""
    return load_document(path)[0]


def load_document(path: str | Path) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """Return (picks in rank order, artifact ids that must not be featured anywhere)."""
    source = Path(path).expanduser()
    try:
        if source.stat().st_size > MAX_PICKS_BYTES:
            raise GemPicksError("Gem picks file is too large")
        document = json.loads(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise GemPicksError(f"Cannot read gem picks: {error}") from error
    except ValueError as error:
        raise GemPicksError("Gem picks file is not valid JSON") from error
    if not isinstance(document, Mapping) or document.get("schema") != PICKS_SCHEMA:
        raise GemPicksError("Gem picks schema is unsupported")
    if document.get("claims") != {"executed": False, "security_verified": False}:
        raise GemPicksError("Gem picks make unsupported trust claims")
    entries = document.get("picks")
    if not isinstance(entries, list) or len(entries) > MAX_PICKS:
        raise GemPicksError("Gem picks list is invalid")
    picks: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise GemPicksError("Gem pick is not an object")
        identity = entry.get("artifact_id")
        score = entry.get("score")
        if not isinstance(identity, str) or not identity or len(identity) > 160 or identity in picks:
            raise GemPicksError("Gem pick has an invalid or repeated artifact id")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 100:
            raise GemPicksError("Gem pick has an invalid score")
        if entry.get("confidence") not in CONFIDENCES or entry.get("verdict") not in VERDICTS:
            raise GemPicksError("Gem pick has an unknown confidence or verdict")
        reasons = entry.get("reasons")
        if not isinstance(reasons, list) or len(reasons) > 6:
            raise GemPicksError("Gem pick reasons are invalid")
        picks[identity] = {
            # Whole numbers only: signed registry snapshots reject floats.
            "score": int(round(score)),
            "confidence": entry["confidence"],
            "verdict": entry["verdict"],
            "summary": _text(entry.get("summary"), 240),
            "reasons": [text for text in (_text(reason, 200) for reason in reasons) if text],
        }
    excluded = document.get("not_featured", [])
    if not isinstance(excluded, list) or len(excluded) > 2000 or any(
        not isinstance(item, str) or not item or len(item) > 160 for item in excluded
    ):
        raise GemPicksError("Gem picks exclusion list is invalid")
    return picks, set(excluded) - set(picks)


def apply_exclusions(queue: dict[str, Any], excluded: set[str]) -> int:
    """Keep reviewed-out projects off every featured surface, in place.

    They stop being gem candidates, leave the new and best shelves, and leave any
    pack; a pack left with fewer than three members is dropped. Returns how many
    places were changed. The projects stay searchable in the catalog.
    """
    if not excluded:
        return 0
    changed = 0
    for item in queue.get("candidates") or []:
        research = item.get("research") if isinstance(item, Mapping) else None
        if isinstance(research, dict) and str(research.get("artifact_id")) in excluded and research.get("candidate") is not False:
            research["candidate"] = False
            research["gaps"] = [*(research.get("gaps") or []), "not featured after code review"][:12]
            changed += 1
    shelves = queue.get("shelves")
    if isinstance(shelves, dict):
        for key, identity in (("new", lambda entry: entry), ("best", lambda entry: entry.get("artifact_id") if isinstance(entry, Mapping) else None)):
            entries = shelves.get(key) if isinstance(shelves.get(key), list) else []
            kept = [entry for entry in entries if identity(entry) not in excluded]
            changed += len(entries) - len(kept)
            shelves[key] = kept
    packs = []
    for pack in queue.get("packs") or []:
        if not isinstance(pack, dict):
            continue
        members = [member for member in pack.get("members") or [] if isinstance(member, Mapping)]
        kept = [member for member in members if str(member.get("artifact_id")) not in excluded]
        changed += len(members) - len(kept)
        if len(kept) >= 3:
            packs.append({**pack, "members": kept})
    if "packs" in queue:
        queue["packs"] = packs
    return changed


def apply_picks(queue: dict[str, Any], picks: Mapping[str, Mapping[str, Any]]) -> int:
    """Re-rank the queue's plugins by the gem picks, in place. Returns how many matched.

    Picked plugins come first, in pick order, and carry a ``gem`` block and the
    pick's reasons. Other plugins keep their relative order after them. Forks are
    untouched: the deep stage does not read forks.
    """
    candidates = [item for item in queue.get("candidates") or [] if isinstance(item, Mapping)]
    order = {identity: position for position, identity in enumerate(picks)}
    plugins = [item for item in candidates if (item.get("artifact") or {}).get("artifact_type") != "fork"]

    def position(item: Mapping[str, Any]) -> tuple[int, int, int]:
        research = item["research"]
        identity = str(research.get("artifact_id"))
        earlier = research.get("rank") if isinstance(research.get("rank"), int) else 10**6
        return (0, order[identity], 0) if identity in order else (1, earlier, 0)

    matched = 0
    for rank, item in enumerate(sorted(plugins, key=position), 1):
        research = item["research"]
        pick = picks.get(str(research.get("artifact_id")))
        research["rank"] = rank
        research.pop("gem", None)
        if pick:
            matched += 1
            research["gem"] = {**pick, "rank": order[str(research["artifact_id"])] + 1}
            if pick["reasons"]:
                research["reasons"] = list(pick["reasons"])
    queue["candidates"] = sorted(
        candidates,
        key=lambda item: (
            item["research"].get("rank") if isinstance(item["research"].get("rank"), int) else 10**6,
            str((item.get("artifact") or {}).get("artifact_type")),
            str((item.get("artifact") or {}).get("artifact_id")),
        ),
    )
    quality = queue.get("quality")
    if isinstance(quality, dict):
        quality["gem_picks"] = {"schema": PICKS_SCHEMA, "applied": matched}
    return matched
