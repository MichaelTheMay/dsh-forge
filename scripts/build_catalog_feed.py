#!/usr/bin/env python3
"""Build compressed public catalog assets and their integrity index."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsh_forge.feed import build_feed_assets


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", required=True, metavar="JSON")
    parser.add_argument("--queue", required=True, metavar="JSON")
    parser.add_argument("--base-url", required=True, metavar="HTTPS_URL")
    parser.add_argument("--output-dir", required=True, metavar="DIR")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = build_feed_assets(
        args.registry,
        args.queue,
        args.output_dir,
        base_url=args.base_url,
        force=args.force,
    )
    print(json.dumps({
        "snapshot_id": result["feed"]["snapshot_id"],
        "counts": result["feed"]["counts"],
        "claims": result["feed"]["claims"],
        "paths": result["paths"],
    }, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
