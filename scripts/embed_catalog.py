#!/usr/bin/env python3
"""Validate and embed a local metadata snapshot in the existing DC export."""
import argparse
import json
import os
from pathlib import Path
import re
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = "deepseek-ai/deepseek-harness"


def validate(snapshot):
    if snapshot.get("schema_version") != 1 or snapshot.get("upstream") != UPSTREAM:
        raise ValueError("Unsupported snapshot version or upstream")
    entries = snapshot.get("entries")
    extras = snapshot.get("supplemental_entries", [])
    if not isinstance(entries, list) or len(entries) != 10:
        raise ValueError("The seed must contain exactly ten ranked forks")
    if not isinstance(extras, list) or len(extras) > 100:
        raise ValueError("Invalid supplemental entries")
    if not isinstance(snapshot.get("fetched_at"), str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", snapshot["fetched_at"]):
        raise ValueError("Expected an explicit UTC snapshot time")
    if snapshot.get("provenance", {}).get("signature_status") != "unsigned_development_seed":
        raise ValueError("This prototype does not verify signed production snapshots")
    ids = set()
    for index, entry in enumerate(entries + extras):
        github_id = entry.get("github_id")
        if type(github_id) is not int or github_id <= 0 or github_id in ids:
            raise ValueError("Invalid or duplicate GitHub ID")
        ids.add(github_id)
        if entry.get("artifact_id") != f"github:{github_id}":
            raise ValueError("Artifact identity must use the stable GitHub ID")
        slug = entry.get("full_name", "")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
            raise ValueError("Invalid repository name")
        if entry.get("repository_url") != "https://github.com/" + slug:
            raise ValueError("Only the canonical HTTPS GitHub URL is accepted")
        if entry.get("owner") + "/" + entry.get("name") != slug:
            raise ValueError("Owner/name disagree with repository identity")
        if entry.get("source") != "github" or entry.get("artifact_type") not in {"fork", "plugin", "repository"}:
            raise ValueError("Unsupported artifact source/type")
        if type(entry.get("github_stars")) is not int or entry["github_stars"] < 0:
            raise ValueError("Invalid GitHub star count")
        if not re.fullmatch(r"[0-9a-f]{40}", entry.get("head_sha", "")):
            raise ValueError("An immutable commit is required")
        if not isinstance(entry.get("description"), str) or len(entry["description"]) > 10_000:
            raise ValueError("Invalid description")
        if not isinstance(entry.get("license"), dict):
            raise ValueError("Missing license metadata")
        if not isinstance(entry.get("topics"), list) or len(entry["topics"]) > 100 or any(not isinstance(t, str) or len(t) > 200 for t in entry["topics"]):
            raise ValueError("Invalid topics")
        if entry.get("verification") != {"metadata_only": True, "executed": False, "security_verified": False}:
            raise ValueError("Only unexecuted, unverified metadata is accepted")
        if entry.get("analysis_status") != "not_analyzed":
            raise ValueError("Analysis is not implemented in this prototype")
        if index < 10:
            if entry.get("seed_rank") != index + 1 or entry["artifact_type"] != "fork":
                raise ValueError("Seed ranks must be the ten forks in GitHub order")
            if entry.get("source_repository") != UPSTREAM and entry.get("parent_repository") != UPSTREAM:
                raise ValueError("Seed entry is outside the upstream fork network")
        elif entry.get("seed_rank") is not None:
            raise ValueError("Supplemental repositories must not enter the top-ten ranking")
    stars = [entry["github_stars"] for entry in entries]
    if stars != sorted(stars, reverse=True):
        raise ValueError("Seed is not ordered by GitHub stars")


def encode(snapshot):
    # Repository text remains data even if an author includes HTML or script delimiters.
    return json.dumps(snapshot, ensure_ascii=False, indent=2).replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=ROOT / "data/public-repos.seed.json")
    parser.add_argument("--html", type=Path, default=ROOT / "web/launcher.js", help="JavaScript source containing the snapshot markers")
    args = parser.parse_args()
    if args.snapshot.stat().st_size > 2_000_000:
        raise ValueError("Snapshot exceeds 2 MB")
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    validate(snapshot)
    html = args.html.read_text(encoding="utf-8")
    start, end = "// CATALOG_SNAPSHOT_START", "// CATALOG_SNAPSHOT_END"
    if html.count(start) != 1 or html.count(end) != 1:
        raise ValueError("Missing or duplicate snapshot markers")
    prefix, rest = html.split(start, 1)
    _, suffix = rest.split(end, 1)
    result = prefix + start + "\nconst CATALOG_SNAPSHOT = " + encode(snapshot) + ";\n" + end + suffix
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=args.html.parent, delete=False) as output:
        output.write(result)
        name = output.name
    os.replace(name, args.html)
    print("Validated and embedded the local snapshot. No network or repository code was used.")


if __name__ == "__main__":
    main()
