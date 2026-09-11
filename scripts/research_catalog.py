#!/usr/bin/env python3
"""Fetch the external catalog and emit a bounded hidden-gem research queue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsh_forge.marketplace import DEFAULT_CATALOG_URL, fetch_catalog
from dsh_forge.packages import write_json
from dsh_forge.research import MAX_DISCOVERY_QUEUE, discovery_queue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=DEFAULT_CATALOG_URL)
    parser.add_argument("--limit", type=int, default=MAX_DISCOVERY_QUEUE)
    parser.add_argument("--output", required=True, metavar="JSON")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    queue = discovery_queue(fetch_catalog(args.url), limit=args.limit)
    write_json(args.output, queue, force=args.force)
    print(json.dumps({
        "output": str(Path(args.output).expanduser()),
        "snapshot_id": queue["snapshot_id"],
        "source_count": queue["source_count"],
        "candidate_count": queue["candidate_count"],
        "security_verified": False,
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
