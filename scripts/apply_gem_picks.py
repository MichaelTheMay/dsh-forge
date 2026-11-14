#!/usr/bin/env python3
"""Fold the gem system's picks into the discovery queue and the registry."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsh_forge.catalog_store import MAX_SNAPSHOT_BYTES
from dsh_forge.discovery import annotate
from dsh_forge.gem_picks import GemPicksError, apply_picks, load_picks
from dsh_forge.packages import read_json, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", required=True, metavar="JSON", help="hidden-gems.json, rewritten in place")
    parser.add_argument("--picks", required=True, metavar="JSON", help="gem-picks.json from `python3 -m gems build`")
    parser.add_argument("--snapshot", required=True, metavar="JSON", help="the analyzed registry snapshot")
    parser.add_argument("--annotate", required=True, metavar="JSON", help="where to write the registry with gem reports attached")
    args = parser.parse_args()

    queue = read_json(args.queue, max_bytes=MAX_SNAPSHOT_BYTES)
    try:
        picks = load_picks(args.picks)
    except GemPicksError as error:
        # The daily catalog must still publish when the gem stage has a bad day:
        # the queue keeps its statistics-only order.
        print(f"Gem picks not applied: {error}", file=sys.stderr)
        picks = {}
    matched = apply_picks(queue, picks)
    write_json(args.queue, queue, force=True, compact=True)
    snapshot = read_json(args.snapshot, max_bytes=MAX_SNAPSHOT_BYTES)
    annotated = annotate(snapshot, queue)
    write_json(args.annotate, snapshot, force=True, compact=True)
    print(json.dumps({"picks": len(picks), "applied": matched, "annotated": annotated}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
