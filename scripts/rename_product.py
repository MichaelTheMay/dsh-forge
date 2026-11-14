#!/usr/bin/env python3
"""Change the product's display name everywhere a person reads it.

Only the name people see ("DSH Forge") is changed. Identifiers stay as they are on
purpose, because changing them would break existing installs and saved data: the
Python package (``dsh_forge``), environment variables (``DSH_FORGE_*``), the
``dsh-forge`` command, storage keys, schema names and the repository address.

    python3 scripts/rename_product.py "New Name"            # report only
    python3 scripts/rename_product.py "New Name" --apply    # rewrite files

After applying, run ``make check``: tests that assert on-screen text are rewritten
along with it, and the embedded catalog check confirms nothing else moved.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CURRENT = "DSH Forge"
# Text people read. Data files, vendored code and recorded history are left alone.
INCLUDE = (".html", ".js", ".mjs", ".cjs", ".py", ".md", ".sh", ".yml", ".yaml", ".json", ".txt", ".cff", ".ps1", ".iss")
# The Windows packaging is left alone too: its product name is the installer's
# upgrade identity, and changing it would make an update install a second copy.
EXCLUDE_PARTS = (
    "web/vendor/", "gems/reviews/", "gems/eval/data/", "data/", "packaging/", "tests/test_workflow.py",
    "docs/decisions.md", "docs/PROBLEM.md", "docs/PLAN.md",
)
_NAME = re.compile(r"^[^\s<>&\"'`\\][^<>&\"'`\\\n]{0,38}[^\s<>&\"'`\\]$")


def tracked_files() -> list[Path]:
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    files = []
    for name in listed.decode("utf-8", "replace").split("\0"):
        if name and name.endswith(INCLUDE) and not any(part in name for part in EXCLUDE_PARTS):
            files.append(ROOT / name)
    return files


def plan(new_name: str) -> list[tuple[Path, int]]:
    """Files that mention the current display name, with how many times."""
    found = []
    for path in tracked_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        count = text.count(CURRENT)
        if count:
            found.append((path, count))
    return found


def apply(new_name: str, files: list[tuple[Path, int]]) -> int:
    changed = 0
    for path, _count in files:
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(CURRENT, new_name), encoding="utf-8")
        changed += 1
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="the new display name, 2 to 40 characters")
    parser.add_argument("--apply", action="store_true", help="rewrite the files (default: report only)")
    args = parser.parse_args(argv)
    if not _NAME.match(args.name) or args.name == CURRENT:
        print("Choose a different name of 2 to 40 characters, without quotes or markup characters.", file=sys.stderr)
        return 2
    files = plan(args.name)
    total = sum(count for _path, count in files)
    for path, count in files:
        print(f"{count:4d}  {path.relative_to(ROOT)}")
    print(f"\n{total} places in {len(files)} files say \"{CURRENT}\".")
    if not args.apply:
        print(f"Nothing changed. Add --apply to rename to \"{args.name}\".")
        return 0
    print(f"Renamed in {apply(args.name, files)} files.")
    # The catalog embedded in web/launcher.js is generated from data files that are
    # deliberately not renamed, so it is regenerated rather than left half-edited.
    subprocess.run([sys.executable, str(ROOT / "scripts" / "embed_catalog.py")], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    print("Now run: make check")
    print("Still to do by hand: the domain, the repository name, and the site address in README and docs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
