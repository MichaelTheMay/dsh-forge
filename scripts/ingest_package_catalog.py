#!/usr/bin/env python3
"""Build the deterministic package-browser feed from bounded local metadata."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dsh_forge.catalog import build_feed, load_json  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, default=ROOT / "data/package-catalog.sources.json")
    parser.add_argument("--plugins", type=Path, default=ROOT / "data/public-repos.seed.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/package-catalog.seed.json")
    parser.add_argument("--check", action="store_true", help="fail if the committed output is stale")
    args = parser.parse_args()
    source = load_json(args.sources, max_bytes=2_000_000)
    plugins = load_json(args.plugins, max_bytes=4_000_000)
    feed = build_feed(source, plugins)
    rendered = json.dumps(feed, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        current = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if current != rendered:
            raise SystemExit("Package catalog is stale; run scripts/ingest_package_catalog.py")
        print("Package catalog matches the bounded local sources. No network or code execution was used.")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.output.parent, delete=False) as output:
        output.write(rendered)
        name = output.name
    os.replace(name, args.output)
    print(f"Wrote {len(feed['packages'])} metadata-only package records to {args.output}.")


if __name__ == "__main__":
    main()
