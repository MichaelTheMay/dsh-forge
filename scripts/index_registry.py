#!/usr/bin/env python3
"""Build a source-neutral plugin and fork registry snapshot."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsh_forge.marketplace import DEFAULT_CATALOG_URL, fetch_catalog
from dsh_forge.packages import write_json
from dsh_forge.registry import DEFAULT_UPSTREAM, fetch_github_fork_network, merge_registry_snapshots


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marketplace-url", default=DEFAULT_CATALOG_URL)
    parser.add_argument("--skip-marketplace", action="store_true")
    parser.add_argument("--fork-network", action="append", default=[], metavar="OWNER/REPO")
    parser.add_argument("--max-fork-pages", type=int, default=500)
    parser.add_argument("--output", required=True, metavar="JSON")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    snapshots = []
    if not args.skip_marketplace:
        snapshots.append(fetch_catalog(args.marketplace_url))
    networks = args.fork_network or [DEFAULT_UPSTREAM]
    for upstream in networks:
        snapshots.append(fetch_github_fork_network(
            upstream,
            token=os.environ.get("GITHUB_TOKEN"),
            max_pages=args.max_fork_pages,
            progress=lambda pages, records, name=upstream: print(
                f"Indexed {records:,} forks from {name} across {pages} page(s)",
                file=sys.stderr,
                flush=True,
            ),
        ))
    merged = merge_registry_snapshots(*snapshots)
    write_json(args.output, merged, force=args.force, compact=True)
    counts = {
        "plugins": len(merged["supplemental_entries"]),
        "forks": len(merged["entries"]),
        "packages": len(merged["package_entries"]),
    }
    print(json.dumps({
        "output": str(Path(args.output).expanduser()),
        "snapshot_id": merged["snapshot_id"],
        "counts": counts,
        "coverage": merged["coverage"],
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
