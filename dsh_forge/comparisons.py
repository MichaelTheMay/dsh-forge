"""Comparison runs: one task sent to several saved configurations at once.

A comparison is only a record that groups the sessions started for it. Each run is
an ordinary launcher session, isolated like any other; nothing here starts or
controls a process. The user reads the results side by side and may mark one as
their pick. Nothing is merged.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
from typing import Any, Iterator, Mapping, Sequence

from .file_lock import lock as lock_file, unlock as unlock_file

COMPARISON_SCHEMA_VERSION = 1
MIN_CONFIGURATIONS = 2
MAX_CONFIGURATIONS = 4
MAX_TASK_CHARACTERS = 20_000
MAX_COMPARISONS = 200

_ID = re.compile(r"^cmp_[a-f0-9]{16}$")
_CELL = re.compile(r"^cell_[a-f0-9]{6,32}$")
_CONFIGURATION = re.compile(r"^config_[a-f0-9]{20}$")


class ComparisonError(ValueError):
    """A comparison request or record is invalid."""


def validate_request(configuration_ids: Any, task: Any) -> tuple[list[str], str]:
    """Return (distinct configuration ids, task) or raise ComparisonError."""
    if not isinstance(task, str) or not task.strip():
        raise ComparisonError("Describe the task to run")
    if len(task) > MAX_TASK_CHARACTERS:
        raise ComparisonError("The task is too long")
    if not isinstance(configuration_ids, list) or any(not isinstance(item, str) for item in configuration_ids):
        raise ComparisonError("Choose the configurations to compare")
    distinct = list(dict.fromkeys(configuration_ids))
    if any(not _CONFIGURATION.match(item) for item in distinct):
        raise ComparisonError("Unknown configuration")
    if not MIN_CONFIGURATIONS <= len(distinct) <= MAX_CONFIGURATIONS:
        raise ComparisonError(f"Choose between {MIN_CONFIGURATIONS} and {MAX_CONFIGURATIONS} configurations")
    return distinct, task.strip()


class ComparisonRegistry:
    """Comparison records on disk, safe across processes."""

    def __init__(self, state_root: str | Path):
        self.state_root = Path(state_root).expanduser()
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.state_root / "comparisons.json"
        self.lock_path = self.state_root / "comparisons.lock"

    @contextmanager
    def _lock(self) -> Iterator[None]:
        descriptor = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            lock_file(descriptor)
            yield
        finally:
            unlock_file(descriptor)
            os.close(descriptor)

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        if self.path.is_symlink():
            raise ComparisonError("The comparison registry may not be a symlink")
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as error:
            raise ComparisonError(f"Could not read saved comparisons: {error}") from error
        rows = payload.get("comparisons") if isinstance(payload, dict) else None
        if not isinstance(payload, dict) or payload.get("schema_version") != COMPARISON_SCHEMA_VERSION or not isinstance(rows, list):
            raise ComparisonError("Saved comparisons are in an unsupported format")
        return [row for row in rows if isinstance(row, dict) and _ID.match(str(row.get("id")))]

    def _save(self, records: Sequence[Mapping[str, Any]]) -> None:
        payload = {"schema_version": COMPARISON_SCHEMA_VERSION, "comparisons": list(records)[-MAX_COMPARISONS:]}
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.state_root, prefix=".comparisons-", suffix=".tmp", delete=False,
            ) as handle:
                temporary = Path(handle.name)
                os.chmod(temporary, 0o600)
                handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def create(self, task: str, runs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Record a comparison. Each run names its configuration and either its session or why it did not start."""
        cleaned = []
        for run in runs:
            cell_id = run.get("cell_id")
            cleaned.append({
                "configuration_id": str(run.get("configuration_id") or "")[:64],
                "name": str(run.get("name") or "")[:120],
                "cell_id": cell_id if isinstance(cell_id, str) and _CELL.match(cell_id) else None,
                "error": str(run.get("error") or "")[:300],
            })
        record = {
            "id": "cmp_" + secrets.token_hex(8),
            "task": task[:MAX_TASK_CHARACTERS],
            "created_at": int(time.time() * 1000),
            "runs": cleaned,
            "chosen_cell_id": None,
        }
        with self._lock():
            records = self._load()
            records.append(record)
            self._save(records)
        return record

    def get(self, comparison_id: Any) -> dict[str, Any]:
        if not isinstance(comparison_id, str) or not _ID.match(comparison_id):
            raise ComparisonError("Unknown comparison")
        with self._lock():
            for record in self._load():
                if record["id"] == comparison_id:
                    return record
        raise ComparisonError("Unknown comparison")

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock():
            return list(reversed(self._load()))[:max(1, min(limit, MAX_COMPARISONS))]

    def choose(self, comparison_id: Any, cell_id: Any) -> dict[str, Any]:
        """Mark one run as the user's pick. Only a session that belongs to this comparison can be chosen."""
        if not isinstance(comparison_id, str) or not _ID.match(comparison_id):
            raise ComparisonError("Unknown comparison")
        with self._lock():
            records = self._load()
            for record in records:
                if record["id"] == comparison_id:
                    if cell_id not in {run.get("cell_id") for run in record.get("runs") or [] if run.get("cell_id")}:
                        raise ComparisonError("That session is not part of this comparison")
                    record["chosen_cell_id"] = cell_id
                    self._save(records)
                    return record
        raise ComparisonError("Unknown comparison")
