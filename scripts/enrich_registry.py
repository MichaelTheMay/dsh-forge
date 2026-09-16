#!/usr/bin/env python3
"""Attach deterministic discovery tags to every record in a registry snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsh_forge.enrichment import build_facets, enrich_snapshot
from dsh_forge.packages import read_json, write_json
from dsh_forge.catalog_store import MAX_SNAPSHOT_BYTES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True, metavar="JSON")
    parser.add_argument("--output", required=True, metavar="JSON")
    parser.add_argument("--facets", metavar="JSON", help="also write the facet counts here")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    snapshot = read_json(args.snapshot, max_bytes=MAX_SNAPSHOT_BYTES)
    counts = enrich_snapshot(snapshot)
    write_json(args.output, snapshot, force=args.force, compact=True)
    if args.facets:
        write_json(args.facets, build_facets(snapshot), force=args.force, compact=True)

    print(json.dumps({
        "records": counts["records"],
        "tagged": counts["tagged"],
        "untagged": counts["untagged"],
        "coverage": counts["coverage"],
        "distinct_tags": counts["distinct_tags"],
        "differentiated": counts["differentiated"],
        "boilerplate": counts["boilerplate"],
        "differentiated_share": counts["differentiated_share"],
        "top_tags": counts["top_tags"][:10],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
