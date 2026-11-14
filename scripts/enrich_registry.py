#!/usr/bin/env python3
"""Attach bounded GitHub evidence to a registry snapshot for hidden-gem discovery."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import sys
import zlib
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsh_forge.catalog_store import MAX_SNAPSHOT_BYTES
from dsh_forge.enrichment import (
    DEFAULT_MAX_POINTS,
    DEFAULT_MAX_REPOSITORIES,
    apply_evidence,
    fetch_credible_accounts,
    fetch_evidence,
    plan_targets,
    previous_evidence,
    trim_evidence,
)
from dsh_forge.packages import read_json, write_json


MAX_PREVIOUS_BYTES = 128 * 1024 * 1024


def load_previous(source: str | None) -> dict | None:
    """Read an earlier registry (path or https URL, optionally gzipped); missing is fine."""
    if not source:
        return None
    try:
        if source.startswith("https://"):
            request = Request(source, headers={"User-Agent": "DSH-Forge-evidence-indexer/1"})
            with urlopen(request, timeout=120) as response:
                raw = response.read(MAX_SNAPSHOT_BYTES + 1)
        else:
            raw = Path(source).expanduser().read_bytes()
        if raw[:2] == b"\x1f\x8b":
            # Bounded inflation: a hostile or corrupt archive can't exhaust memory.
            inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
            raw = inflater.decompress(raw, MAX_PREVIOUS_BYTES + 1)
            if len(raw) > MAX_PREVIOUS_BYTES or inflater.unconsumed_tail:
                print("Previous registry is too large; no evidence reused", file=sys.stderr)
                return None
        value = json.loads(raw)
    except (OSError, EOFError, zlib.error, ValueError) as error:
        print(f"No previous registry evidence reused ({type(error).__name__})", file=sys.stderr)
        return None
    return value if isinstance(value, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, metavar="JSON")
    parser.add_argument("--previous", metavar="PATH_OR_URL", help="earlier registry whose evidence may be reused")
    parser.add_argument("--max-repositories", type=int, default=DEFAULT_MAX_REPOSITORIES)
    parser.add_argument("--max-points", type=int, default=DEFAULT_MAX_POINTS)
    parser.add_argument("--deadline-seconds", type=int, default=12 * 60)
    parser.add_argument("--output", required=True, metavar="JSON")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    snapshot = read_json(args.snapshot, max_bytes=MAX_SNAPSHOT_BYTES)
    token = os.environ.get("GITHUB_TOKEN") or None
    observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    reused_index = previous_evidence(load_previous(args.previous))
    targets, reused = plan_targets(
        snapshot, reused_index, observed_at=observed_at, max_repositories=args.max_repositories,
    )
    fetched: dict = {}
    coverage = {
        "source": "github-graphql/repo-evidence",
        "status": "incomplete",
        "requested_count": len(targets),
        "attempted_count": 0,
        "observed_count": 0,
        "stopped": "no GITHUB_TOKEN",
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
    }
    if token and targets:
        fetched, coverage = fetch_evidence(
            targets, token=token, observed_at=observed_at, max_points=args.max_points,
            deadline_seconds=args.deadline_seconds,
        )
    coverage["reused_count"] = len(reused)
    evidence = {**reused, **fetched}
    credible = fetch_credible_accounts(snapshot, token=token)
    applied = apply_evidence(snapshot, evidence, credible_accounts=credible, coverage=coverage)
    trimmed = trim_evidence(snapshot, observed_at=observed_at)
    write_json(args.output, snapshot, force=args.force, compact=True)
    print(json.dumps({
        "output": str(Path(args.output).expanduser()),
        "with_evidence": applied - trimmed,
        "trimmed_for_size": trimmed,
        "fetched": len(fetched),
        "reused": len(reused),
        "credible_accounts": len(credible),
        "coverage": coverage,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
