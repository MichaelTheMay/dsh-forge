"""Human judgements the system is scored against.

``labels.json`` maps ``owner/name`` to whether a person considers it a gem. It is
the only place a human opinion enters the system, so it is small, plain and kept
in version control.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

LABELS_SCHEMA = "dsh-forge.gem-labels/v1"
DEFAULT_PATH = Path(__file__).resolve().parent / "labels.json"

_SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}$")


def load(path: str | Path = DEFAULT_PATH) -> dict[str, bool]:
    """Return {lower-cased owner/name: is it a gem}. A missing file is no labels."""
    source = Path(path)
    if not source.is_file():
        return {}
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema") != LABELS_SCHEMA:
        raise ValueError("Not a gem labels file")
    labels: dict[str, bool] = {}
    for name, entry in (data.get("labels") or {}).items():
        if isinstance(name, str) and _SLUG.match(name) and isinstance(entry, dict) and isinstance(entry.get("gem"), bool):
            labels[name.casefold()] = entry["gem"]
    return labels


def save_one(name: str, gem: bool, *, by: str, at: str, path: str | Path = DEFAULT_PATH) -> int:
    """Record one judgement and return how many labels the file now holds."""
    if not _SLUG.match(name):
        raise ValueError("Not a valid owner/name repository")
    target = Path(path)
    data: dict[str, Any] = {"schema": LABELS_SCHEMA, "labels": {}}
    if target.is_file():
        data = json.loads(target.read_text(encoding="utf-8"))
        if data.get("schema") != LABELS_SCHEMA or not isinstance(data.get("labels"), dict):
            raise ValueError("Not a gem labels file")
    data["labels"][name] = {"gem": bool(gem), "by": by[:40], "at": at[:32]}
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
    return len(data["labels"])
