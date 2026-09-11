#!/usr/bin/env python3
"""Enrich a bounded fork lead set with immutable GitHub comparison evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsh_forge.analysis import MAX_FORK_ANALYSES, enrich_github_forks
from dsh_forge.catalog_store import MAX_SNAPSHOT_BYTES
from dsh_forge.packages import read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, metavar="JSON")
    parser.add_argument("--limit", type=int, default=MAX_FORK_ANALYSES)
    parser.add_argument("--output", required=True, metavar="JSON")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    snapshot = read_json(args.snapshot, max_bytes=MAX_SNAPSHOT_BYTES)
    enriched = enrich_github_forks(
        snapshot,
        token=os.environ.get("GITHUB_TOKEN"),
        limit=args.limit,
        progress=lambda done, total, identity: print(
            f"Analyzed fork lead {done}/{total}: {identity}",
            file=sys.stderr,
            flush=True,
        ),
    )
    write_json(args.output, enriched, force=args.force, compact=True)
    coverage = enriched["coverage"][-1]
    print(json.dumps({
        "output": str(Path(args.output).expanduser()),
        "snapshot_id": enriched["snapshot_id"],
        "selected_count": coverage["selected_count"],
        "analyzed_count": coverage["analyzed_count"],
        "failed_count": coverage["failed_count"],
        "executed": False,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
