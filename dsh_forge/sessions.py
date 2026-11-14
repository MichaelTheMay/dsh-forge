"""Read Harness session logs on this machine and reduce each to a few counts.

A session log (``session.jsonl.zstd``) holds everything a session said and did:
prompts, code, command output. This module exists so the rest of the app never has
to hold any of that. It streams a log once and keeps only numbers: how many test
runs, searches, reviews, retries. No message text, command or file path leaves
this module, and nothing is sent anywhere.

Logs are zstd-compressed and the project takes no dependencies, so decompression
uses whatever the machine already has: Python 3.14's standard library, the ``zstd``
program, or Node (which the Harness itself needs).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from typing import Any, Callable, Iterable, Iterator

MAX_LINE_BYTES = 2 * 1024 * 1024
MAX_SESSION_SECONDS = 20.0
LOG_NAMES = ("session.jsonl.zstd", "session.jsonl")

# Only these record kinds matter here. Most of a log is streamed text chunks, which
# are skipped before any JSON parsing.
_WANTED = (b'"session"', b'"tool/call"', b'"llm/retry"', b'"step/start"', b'"agent/inbox/spliced"',
           b'"web/deepseek-search-llm-request"')

_NODE_DECODER = (
    "const fs=require('fs'),zlib=require('zlib');"
    "if(!zlib.createZstdDecompress)process.exit(3);"
    "fs.createReadStream(process.argv[1]).pipe(zlib.createZstdDecompress()).pipe(process.stdout);"
)

# What a shell command says about the kind of work being done. Matched against the
# command text, which is then thrown away: only the tally is kept.
_COMMAND_SIGNALS = {
    "testing": re.compile(
        r"\b(pytest|vitest|jest|playwright|go test|cargo test|node --test|rspec|phpunit)\b"
        r"|-m unittest\b|\b(npm|pnpm|yarn|bun)\s+(run\s+)?test\b|\bmake\s+(test|check)\b"
    ),
    "code_search": re.compile(r"\b(rg|ag|ack)\s|\bgrep\s+-[A-Za-z]*r|\bfind\s+\.\s|\bgit\s+grep\b"),
    "review": re.compile(
        r"\bgit\s+(diff|show|log\s+-p)\b|\bgh\s+pr\s+(view|diff|review|checks)\b"
        r"|\b(eslint|ruff|flake8|pylint|biome|mypy)\b|\btsc\s+--noEmit\b"
    ),
    "security": re.compile(r"\b(npm audit|pnpm audit|pip-audit|semgrep|trivy|gitleaks|bandit|snyk)\b"),
}
_TOOL_SIGNALS = {
    "web_search": "search", "platform_search": "search",
    "grep": "code_search", "glob": "code_search",
    "memory": "memory", "report": "orchestration", "skill": "orchestration",
}
_NOTES_FILE = re.compile(r"(^|/)(NOTES|AGENTS|CLAUDE|MEMORY|TODO)\.md$", re.IGNORECASE)

SIGNALS = ("testing", "search", "code_search", "review", "security", "memory", "orchestration")


class SessionReadError(RuntimeError):
    """A session log could not be read."""


def zstd_decoder() -> tuple[str, Callable[[Path], Iterator[bytes]]] | None:
    """Pick a way to decompress session logs, or None when the machine has none."""
    try:
        from compression import zstd as stdlib_zstd  # Python 3.14+
    except ImportError:
        stdlib_zstd = None
    if stdlib_zstd is not None:
        def read_stdlib(path: Path) -> Iterator[bytes]:
            with stdlib_zstd.open(path, "rb") as handle:
                yield from handle
        return "python", read_stdlib
    program = shutil.which("zstd")
    if program:
        return "zstd", lambda path: _piped([program, "-dc", "--", str(path)])
    node = shutil.which("node")
    if node and _node_can_decompress(node):
        return "node", lambda path: _piped([node, "-e", _NODE_DECODER, str(path)])
    return None


def _node_can_decompress(node: str) -> bool:
    try:
        result = subprocess.run(
            [node, "-e", "process.exit(require('zlib').createZstdDecompress?0:3)"],
            capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _piped(command: list[str]) -> Iterator[bytes]:
    """Stream a decompressor's output line by line; never hold a whole log in memory."""
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError as error:
        raise SessionReadError(f"Cannot start the decompressor: {error}") from error
    try:
        assert process.stdout is not None
        yield from process.stdout
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.kill()
        process.wait()


def _lines(path: Path) -> Iterator[bytes]:
    if path.name.endswith(".zstd"):
        decoder = zstd_decoder()
        if decoder is None:
            raise SessionReadError("No zstd decompressor is available")
        return decoder[1](path)
    return _plain(path)


def _plain(path: Path) -> Iterator[bytes]:
    with path.open("rb") as handle:
        yield from handle


def iter_records(path: str | Path, *, deadline: float | None = None) -> Iterator[dict[str, Any]]:
    """Yield the records of one session log that this module understands.

    Stops quietly at ``deadline`` (a ``time.monotonic()`` value) and skips damaged
    or oversized lines: a partly read session still gives useful counts.
    """
    source = Path(path)
    for line in _lines(source):
        if deadline is not None and time.monotonic() > deadline:
            return
        if len(line) > MAX_LINE_BYTES or not any(marker in line for marker in _WANTED):
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if isinstance(record, dict):
            yield record


def session_files(homes: Iterable[str | Path]) -> list[Path]:
    """Every session log under the given Harness homes, newest first."""
    found: dict[Path, float] = {}
    for home in homes:
        root = Path(home).expanduser() / "sessions"
        if not root.is_dir():
            continue
        for directory, _names, files in os.walk(root, followlinks=False):
            for name in LOG_NAMES:
                if name in files:
                    path = Path(directory) / name
                    try:
                        found[path] = path.stat().st_mtime
                    except OSError:
                        pass
                    break
    return sorted(found, key=lambda path: -found[path])


def _tool_arguments(data: dict[str, Any]) -> dict[str, Any]:
    raw = data.get("arguments")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and len(raw) <= MAX_LINE_BYTES:
        try:
            parsed = json.loads(raw)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def summarize_session(path: str | Path, *, max_seconds: float = MAX_SESSION_SECONDS) -> dict[str, Any]:
    """Reduce one session log to counts. The result contains no text from the session.

    The project folder is kept only as a short one-way hash, so sessions in the same
    project can be grouped without recording where that project is.
    """
    counts = {name: 0 for name in SIGNALS}
    summary: dict[str, Any] = {
        "created_at": None, "project": "", "is_subagent": False,
        "steps": 0, "tool_calls": 0, "retries": 0, "delegations": 0,
    }
    deadline = time.monotonic() + max_seconds
    for record in iter_records(path, deadline=deadline):
        kind = record.get("type")
        data = record.get("data") if isinstance(record.get("data"), dict) else {}
        if kind == "session":
            created = record.get("createdAt")
            if isinstance(created, (int, float)) and not isinstance(created, bool):
                # Milliseconds since the epoch in current logs; seconds in old ones.
                summary["created_at"] = int(created / 1000 if created > 10**11 else created)
            cwd = record.get("cwd")
            if isinstance(cwd, str) and cwd:
                summary["project"] = hashlib.sha256(cwd.encode("utf-8", "replace")).hexdigest()[:12]
            depth = record.get("delegationDepth")
            summary["is_subagent"] = bool(record.get("parentSession")) or (isinstance(depth, int) and depth > 0)
        elif kind == "step/start":
            summary["steps"] += 1
        elif kind == "llm/retry":
            summary["retries"] += 1
        elif kind == "agent/inbox/spliced":
            summary["delegations"] += 1
        elif kind == "web/deepseek-search-llm-request":
            counts["search"] += 1
        elif kind == "tool/call":
            summary["tool_calls"] += 1
            name = data.get("name")
            if not isinstance(name, str):
                continue
            signal = _TOOL_SIGNALS.get(name)
            if signal:
                counts[signal] += 1
            arguments = _tool_arguments(data)
            if name == "bash":
                command = arguments.get("command")
                if isinstance(command, str):
                    for label, pattern in _COMMAND_SIGNALS.items():
                        if pattern.search(command):
                            counts[label] += 1
            elif name == "read":
                target = arguments.get("file_path")
                if isinstance(target, str) and _NOTES_FILE.search(target):
                    counts["memory"] += 1
    summary["signals"] = counts
    return summary
