"""Stage 2b: verdicts from someone, or something, that read the code.

A review is a small JSON file. Who wrote it does not matter to the pipeline: a
person, a model in a chat session, or a model behind an API all produce the same
shape, named by ``source``. That is the seam where a paid model plugs in later.

Reviews are written about untrusted repositories, so every text field is treated
as untrusted too: bounded in length, stripped of control characters and markup,
and only ever shown as plain text.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping

from . import REVIEW_SCHEMA

SCORES = ("usefulness", "novelty", "craft", "works", "trust")
VERDICTS = ("gem", "solid", "skip")
SOURCES = ("human", "claude-session", "api-model")
MAX_REVIEW_BYTES = 32 * 1024

_SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
_MARKUP = re.compile(r"<[^>]{0,200}>")

RUBRIC = """\
Score each from 1 to 5. Judge the code you read, not the README's claims.

usefulness  Would a working developer install this and keep it?
            1 no real use · 3 helps in a narrow case · 5 solves a common pain well
novelty     Does it do something the well-known plugins do not?
            1 a copy or a thin wrapper · 3 a known idea done differently · 5 a new capability
craft       Is it built with care?
            1 one unstructured file, no tests · 3 organised, some tests · 5 clear design, real tests, handles errors
works       Does the code plausibly do what it says, end to end?
            1 stubs or broken wiring · 3 core path complete, gaps at the edges · 5 complete and consistent
trust       Is it safe to recommend?
            1 hides behaviour, phones home, or touches credentials without need · 3 nothing alarming, nothing verified · 5 minimal permissions, transparent

verdict     gem    genuinely good and worth featuring
            solid  fine, not special
            skip   should not be featured (broken, a copy, empty, or untrustworthy)
"""


class ReviewError(ValueError):
    """A review file does not follow the format."""


def clean_text(value: Any, limit: int) -> str:
    """Plain text only: no control characters, no markup, bounded length."""
    if not isinstance(value, str):
        raise ReviewError("Review text must be a string")
    text = _MARKUP.sub("", _CONTROL.sub(" ", value)).strip()
    text = re.sub(r"\s{2,}", " ", text)
    if not text:
        raise ReviewError("Review text is empty")
    return text[:limit].rstrip()


def validate(review: Mapping[str, Any]) -> dict[str, Any]:
    """Return a normalised copy of ``review`` or raise ReviewError."""
    if not isinstance(review, Mapping) or review.get("schema") != REVIEW_SCHEMA:
        raise ReviewError("Not a gem review")
    full_name = review.get("full_name")
    commit = review.get("commit")
    if not isinstance(full_name, str) or not _SLUG.match(full_name):
        raise ReviewError("Review names an invalid repository")
    if not isinstance(commit, str) or not _SHA.match(commit):
        raise ReviewError("Review names an invalid commit")
    if review.get("source") not in SOURCES:
        raise ReviewError("Review source is not recognised")
    if review.get("verdict") not in VERDICTS:
        raise ReviewError("Review verdict is not recognised")
    scores = review.get("scores")
    if not isinstance(scores, Mapping) or set(scores) != set(SCORES):
        raise ReviewError("Review must score exactly: " + ", ".join(SCORES))
    for name in SCORES:
        value = scores[name]
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 5:
            raise ReviewError(f"Review score {name} must be a whole number from 1 to 5")
    lists = {}
    for key, most, limit in (("concerns", 5, 200), ("evidence", 6, 200)):
        items = review.get(key, [])
        if not isinstance(items, list) or len(items) > most:
            raise ReviewError(f"Review {key} must be a short list")
        lists[key] = [clean_text(item, limit) for item in items]
    return {
        "schema": REVIEW_SCHEMA,
        "full_name": full_name,
        "commit": commit,
        "source": review["source"],
        "reviewer": clean_text(review.get("reviewer", "unknown"), 80),
        "reviewed_at": clean_text(review.get("reviewed_at", "unknown"), 32),
        "summary": clean_text(review.get("summary"), 240),
        "showcase": clean_text(review.get("showcase"), 200),
        "scores": {name: scores[name] for name in SCORES},
        "verdict": review["verdict"],
        **lists,
    }


def review_filename(full_name: str, commit: str) -> str:
    return f"{full_name.replace('/', '__')}@{commit[:12]}.json"


def load_reviews(directory: str | Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Read every review in ``directory``.

    Returns (reviews keyed by lower-cased ``owner/name``, problems). A file that
    fails validation is reported and skipped, never trusted. When a repository has
    several reviews, the most recently reviewed one wins.
    """
    reviews: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    root = Path(directory)
    if not root.is_dir():
        return reviews, problems
    for path in sorted(root.glob("*.json")):
        try:
            if path.stat().st_size > MAX_REVIEW_BYTES:
                raise ReviewError("Review file is too large")
            review = validate(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as error:
            problems.append(f"{path.name}: {error}")
            continue
        key = review["full_name"].casefold()
        current = reviews.get(key)
        if current is None or review["reviewed_at"] >= current["reviewed_at"]:
            reviews[key] = review
    return reviews, problems


def template(full_name: str, commit: str, source: str = "claude-session") -> dict[str, Any]:
    """An empty review to fill in."""
    return {
        "schema": REVIEW_SCHEMA,
        "full_name": full_name,
        "commit": commit,
        "source": source,
        "reviewer": "",
        "reviewed_at": "",
        "summary": "",
        "showcase": "",
        "scores": {name: 0 for name in SCORES},
        "verdict": "",
        "concerns": [],
        "evidence": [],
    }
