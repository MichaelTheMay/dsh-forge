"""Turn what a user has been doing into plugins worth trying.

Everything happens on the user's machine with fixed rules: no model, nothing
uploaded. The input is the per-session counts from ``sessions.py`` (never session
text). The output is a short list of catalog plugins, each with one plain sentence
of evidence built from those counts.

    session logs ──summaries (counts)──▶ needs per capability ──▶ plugins that meet them
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Iterable, Mapping, Sequence

from . import sessions
from .discovery import capability_strengths

CACHE_SCHEMA = "dsh-forge.session-signals/v1"
CACHE_NAME = "session-signals.json"
MAX_CACHED_SESSIONS = 5000

WINDOW_DAYS = 30
HALF_LIFE_DAYS = 14.0
MIN_SESSIONS = 3
MAX_NEEDS = 3
PER_NEED = 2
MIN_PLUGIN_STRENGTH = 2
RETURNING_SESSIONS = 8

# How many times something has to happen in one session before that session fully
# "counts" for a capability. One huge session therefore counts once, not fifty times.
THRESHOLDS = {
    "testing": 3, "search": 4, "code intelligence": 15, "review": 3, "security": 1,
    "memory": 2, "orchestration": 3, "observability": 3,
}


def _plural(count: int, word: str) -> str:
    return f"{count:,} {word}" if count == 1 else f"{count:,} {word}s"


# Sentence shown with a recommendation. ``total`` is the raw count behind the
# capability and ``n`` the number of sessions it appeared in.
_EVIDENCE: dict[str, Callable[[int, int], str]] = {
    "testing": lambda total, n: f"You ran tests {_plural(total, 'time')} across {_plural(n, 'session')}.",
    "search": lambda total, n: f"You searched the web {_plural(total, 'time')} across {_plural(n, 'session')}.",
    "code intelligence": lambda total, n: f"You searched your code {_plural(total, 'time')} across {_plural(n, 'session')}.",
    "review": lambda total, n: f"You checked diffs or ran linters {_plural(total, 'time')} across {_plural(n, 'session')}.",
    "security": lambda total, n: f"You ran security checks {_plural(total, 'time')} across {_plural(n, 'session')}.",
    "memory": lambda total, n: f"You kept returning to the same projects and notes: {_plural(n, 'session')} did.",
    "orchestration": lambda total, n: f"You handed work to other agents {_plural(total, 'time')} across {_plural(n, 'session')}.",
    "observability": lambda total, n: (
        f"Your sessions had to retry the model {_plural(total, 'time')} across {_plural(n, 'session')}."
    ),
}


class SessionIndex:
    """A small on-disk cache of per-session counts, so logs are read once."""

    def __init__(self, state_root: str | Path):
        self.path = Path(state_root).expanduser() / CACHE_NAME

    @staticmethod
    def _key(path: Path) -> str:
        # The log's location names the project folder, so only a hash of it is stored.
        return hashlib.sha256(str(path).encode("utf-8", "replace")).hexdigest()[:20]

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(data, dict) or data.get("schema") != CACHE_SCHEMA or not isinstance(data.get("files"), dict):
            return {}
        return data["files"]

    def _save(self, files: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(dir=self.path.parent, prefix=CACHE_NAME + ".")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump({"schema": CACHE_SCHEMA, "files": files}, stream, separators=(",", ":"))
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def refresh(self, homes: Iterable[str | Path], *, budget_seconds: float = 2.0) -> dict[str, int]:
        """Summarise new or changed logs, newest first, until the time budget runs out.

        Returns how many were read this time and how many are still waiting, so a
        caller can show partial results and call again.
        """
        started = time.monotonic()
        known = self._load()
        files: dict[str, Any] = {}
        read = waiting = 0
        for path in sessions.session_files(homes)[:MAX_CACHED_SESSIONS]:
            try:
                stat = path.stat()
            except OSError:
                continue
            key = self._key(path)
            entry = known.get(key)
            if isinstance(entry, dict) and entry.get("size") == stat.st_size and entry.get("mtime_ns") == stat.st_mtime_ns:
                files[key] = entry
                continue
            if time.monotonic() - started > budget_seconds:
                waiting += 1
                if isinstance(entry, dict):
                    files[key] = entry  # stale counts beat none until it is re-read
                continue
            try:
                summary = sessions.summarize_session(path)
            except sessions.SessionReadError:
                waiting += 1
                continue
            files[key] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "summary": summary}
            read += 1
        if read or len(files) != len(known):
            self._save(files)
        return {"read": read, "waiting": waiting, "sessions": len(files)}

    def summaries(self) -> list[dict[str, Any]]:
        return [entry["summary"] for entry in self._load().values() if isinstance(entry.get("summary"), dict)]

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


def _raw_counts(summary: Mapping[str, Any], project_sessions: Mapping[str, int]) -> dict[str, int]:
    """One session's counts, mapped onto the catalog's capability names."""
    signals = summary.get("signals") if isinstance(summary.get("signals"), Mapping) else {}

    def number(name: str) -> int:
        value = signals.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 0

    retries = summary.get("retries") if isinstance(summary.get("retries"), int) else 0
    delegations = summary.get("delegations") if isinstance(summary.get("delegations"), int) else 0
    # Coming back to one project again and again is itself a sign memory would help,
    # but a weaker one than actually reading notes, so it counts for half a session.
    returning = 1 if project_sessions.get(str(summary.get("project") or ""), 0) >= RETURNING_SESSIONS else 0
    return {
        "testing": number("testing"),
        "search": number("search"),
        "code intelligence": number("code_search"),
        "review": number("review"),
        "security": number("security"),
        "memory": number("memory") + returning,
        "orchestration": number("orchestration") + delegations,
        "observability": retries,
    }


def capability_needs(summaries: Sequence[Mapping[str, Any]], *, now: float | None = None) -> list[dict[str, Any]]:
    """Rank capabilities by how much of the user's recent work leaned on them.

    Each session adds at most 1 per capability (count / threshold, capped), weighted
    so that a session two weeks old counts half as much as one from today. Sessions
    started by another agent are left out: they repeat their parent's work. A
    capability needs at least ``MIN_SESSIONS`` sessions behind it to be reported.
    """
    moment = time.time() if now is None else now
    dated = [
        summary for summary in summaries
        if not summary.get("is_subagent") and isinstance(summary.get("created_at"), (int, float))
        and not isinstance(summary.get("created_at"), bool) and summary["created_at"] <= moment
    ]
    if not dated:
        return []
    # Someone back after a break still gets suggestions: when nothing is recent, the
    # window ends at their last session instead of today.
    newest = max(summary["created_at"] for summary in dated)
    anchor = moment if (moment - newest) / 86400 <= WINDOW_DAYS else newest
    recent = []
    for summary in dated:
        age_days = (anchor - summary["created_at"]) / 86400
        if age_days <= WINDOW_DAYS:
            recent.append((summary, 0.5 ** (age_days / HALF_LIFE_DAYS)))
    project_sessions: dict[str, int] = {}
    for summary, _weight in recent:
        project = str(summary.get("project") or "")
        if project:
            project_sessions[project] = project_sessions.get(project, 0) + 1
    total_weight = sum(weight for _summary, weight in recent)
    needs = []
    for capability, threshold in THRESHOLDS.items():
        weighted = 0.0
        raw_total = behind = 0
        for summary, weight in recent:
            count = _raw_counts(summary, project_sessions)[capability]
            if count:
                weighted += weight * min(1.0, count / threshold)
                raw_total += count
                behind += 1
        if behind < MIN_SESSIONS:
            continue
        needs.append({
            "capability": capability,
            "share": round(weighted / total_weight, 3),
            "sessions": behind,
            "count": raw_total,
            "evidence": _EVIDENCE[capability](raw_total, behind),
        })
    needs.sort(key=lambda need: (-need["share"], need["capability"]))
    return needs


def _package_name(record: Mapping[str, Any]) -> str:
    package = record.get("package") if isinstance(record.get("package"), Mapping) else {}
    return str(package.get("name") or "").casefold()


def recommend(
    needs: Sequence[Mapping[str, Any]],
    plugins: Sequence[Mapping[str, Any]],
    installed: Iterable[str],
    *,
    max_needs: int = MAX_NEEDS,
    per_need: int = PER_NEED,
) -> list[dict[str, Any]]:
    """Choose plugins for the user's strongest needs.

    ``plugins`` are catalog records already in best-first order (reviewed gems
    lead), each optionally carrying its gem report under ``hidden_gem``.
    ``installed`` holds package names the user already has. A capability the user
    already has a plugin for is skipped, and no plugin is suggested twice.
    """
    have = {name.casefold() for name in installed if isinstance(name, str)}
    by_capability: dict[str, list[tuple[int, Mapping[str, Any]]]] = {}
    covered: set[str] = set()
    for position, record in enumerate(plugins):
        if record.get("archived"):
            continue
        strengths = capability_strengths(record)
        strongest = strengths[0][1] if strengths else 0
        for capability, strength in strengths:
            # Only what the plugin is mainly about. A memory plugin whose description
            # also mentions logging is not an observability suggestion.
            if strength < MIN_PLUGIN_STRENGTH or strength < strongest:
                continue
            if _package_name(record) in have:
                covered.add(capability)
            else:
                by_capability.setdefault(capability, []).append((position, record))
    chosen: list[dict[str, Any]] = []
    used: set[str] = set()
    served = 0
    for need in needs:
        if served >= max_needs:
            break
        capability = str(need.get("capability"))
        if capability in covered:
            continue
        picks = [record for _position, record in sorted(by_capability.get(capability, []), key=lambda item: item[0])
                 if str(record.get("artifact_id")) not in used][:per_need]
        if not picks:
            continue
        served += 1
        for record in picks:
            used.add(str(record.get("artifact_id")))
            chosen.append({
                "artifact": dict(record),
                "capability": capability,
                "evidence": str(need.get("evidence") or ""),
            })
    return chosen


# --------------------------------------------------------------------- service

PREFERENCE_NAME = "recommendations.json"
SCAN_BUDGET_SECONDS = 2.0
MAX_SCAN_ROUNDS = 200
RESCAN_AFTER_SECONDS = 60.0


class RecommendationService:
    """Consent, background scanning and the final list, for the local app.

    Nothing is read until the user says yes. Saying no afterwards deletes the cache.
    Scanning runs on a background thread in short rounds so it never delays the app,
    and partial results are shown while it works.
    """

    def __init__(
        self,
        state_root: str | Path,
        homes: Callable[[], Iterable[str | Path]],
        plugins: Callable[[], Sequence[Mapping[str, Any]]],
        installed: Callable[[], Iterable[str]],
    ):
        import threading

        self._state_root = Path(state_root).expanduser()
        self._homes = homes
        self._plugins = plugins
        self._installed = installed
        self._index = SessionIndex(self._state_root)
        self._preference = self._state_root / PREFERENCE_NAME
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._waiting = 0
        self._scanned_at: float | None = None
        self._threading = threading

    # -- consent ---------------------------------------------------------------

    def consent(self) -> str:
        """``unasked``, ``on`` or ``off``."""
        try:
            value = json.loads(self._preference.read_text(encoding="utf-8")).get("enabled")
        except (OSError, ValueError, AttributeError):
            return "unasked"
        return "on" if value is True else ("off" if value is False else "unasked")

    def set_consent(self, enabled: bool) -> dict[str, Any]:
        if not isinstance(enabled, bool):
            raise ValueError("enabled must be true or false")
        self._state_root.mkdir(parents=True, exist_ok=True)
        temporary = self._preference.with_suffix(".tmp")
        temporary.write_text(json.dumps({"enabled": enabled}), encoding="utf-8")
        os.replace(temporary, self._preference)
        if enabled:
            self._start_scan()
        else:
            # Saying no removes what was derived from the user's history.
            self._index.clear()
        return self.status()

    # -- scanning --------------------------------------------------------------

    def _start_scan(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = self._threading.Thread(target=self._scan, name="recommendation-scan", daemon=True)
            self._thread.start()

    def _scan(self) -> None:
        try:
            for _round in range(MAX_SCAN_ROUNDS):
                if self.consent() != "on":
                    self._index.clear()
                    return
                try:
                    result = self._index.refresh(self._homes(), budget_seconds=SCAN_BUDGET_SECONDS)
                except OSError:
                    return
                self._waiting = result["waiting"]
                if not result["waiting"] or not result["read"]:
                    return
        finally:
            self._scanned_at = time.monotonic()

    def _scan_is_due(self) -> bool:
        return self._scanned_at is None or time.monotonic() - self._scanned_at > RESCAN_AFTER_SECONDS

    def scanning(self) -> bool:
        thread = self._thread
        return bool(thread and thread.is_alive())

    def wait(self, timeout: float = 30.0) -> None:
        """Block until the current scan finishes (tests and the command line)."""
        thread = self._thread
        if thread:
            thread.join(timeout)

    # -- result ----------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """What the home page needs: whether to ask, and what to show."""
        consent = self.consent()
        if consent != "on":
            return {"consent": consent, "state": "off", "reason": "", "items": [], "needs": [], "sessions": 0}
        if sessions.zstd_decoder() is None:
            return {
                "consent": consent, "state": "unavailable", "items": [], "needs": [], "sessions": 0,
                "reason": "Session history can't be read on this computer yet. Install the zstd tool, or Node 22.15 or newer.",
            }
        if self._scan_is_due():
            self._start_scan()
        summaries = self._index.summaries()
        needs = capability_needs(summaries)
        items = recommend(needs, self._plugins(), self._installed()) if needs else []
        return {
            "consent": consent,
            "state": "scanning" if self.scanning() else "ready",
            "reason": "",
            "items": items,
            "needs": needs[:MAX_NEEDS + 2],
            "sessions": len(summaries),
        }
