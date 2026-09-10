#!/usr/bin/env python3
"""One-shot metadata seed. No repository is cloned, installed, or executed."""
import argparse
import concurrent.futures
import datetime as dt
import json
import os
from pathlib import Path
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request

UPSTREAM = "deepseek-ai/deepseek-harness"
API = "https://api.github.com"
ENDPOINT = f"{API}/repos/{UPSTREAM}/forks?sort=stargazers&per_page=10&page=1"
ROOT = Path(__file__).resolve().parents[1]


def get_json(url):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "DSH-Forge-one-shot-seed",
               "X-GitHub-Api-Version": "2026-03-10"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
        content = response.read(2_000_001)
        if len(content) > 2_000_000:
            raise ValueError("GitHub metadata response exceeds the size limit")
        return json.loads(content), {k: response.headers.get(k) for k in ("ETag", "Date", "Link")}


def enrich(pair):
    rank, repo = pair
    slug = repo["full_name"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", slug):
        raise ValueError("Invalid GitHub repository name")
    if repo.get("private") or repo.get("fork") is not True:
        raise ValueError("Fork endpoint returned a non-public or non-fork entry")
    metadata, _ = get_json(f"{API}/repos/{slug}")
    source = metadata.get("source", {}).get("full_name")
    parent = metadata.get("parent", {}).get("full_name")
    if source != UPSTREAM and parent != UPSTREAM:
        raise ValueError(f"{slug}: upstream fork ancestry could not be confirmed")
    if metadata.get("id") != repo["id"]:
        raise ValueError("Repository identity changed while collecting metadata")
    branch = metadata["default_branch"]
    ref, _ = get_json(f"{API}/repos/{slug}/git/ref/heads/{urllib.parse.quote(branch, safe='')}")
    sha = ref.get("object", {}).get("sha", "")
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError(f"{slug}: invalid default-branch commit")
    spdx = (metadata.get("license") or {}).get("spdx_id")
    if spdx == "NOASSERTION":
        spdx = None
    return {
        "artifact_id": "github:" + str(repo["id"]),
        "github_id": repo["id"], "node_id": repo["node_id"],
        "full_name": slug, "owner": repo["owner"]["login"], "name": repo["name"],
        "artifact_type": "fork", "source": "github", "repository_url": "https://github.com/" + slug,
        "description": repo.get("description") or "No repository description provided.",
        "description_origin": "author_declared", "topics": repo.get("topics", []),
        "language": repo.get("language"), "github_stars": repo["stargazers_count"], "seed_rank": rank,
        "forks_count": repo.get("forks_count", 0), "pushed_at": repo.get("pushed_at"),
        "archived": repo.get("archived", False), "default_branch": branch,
        "head_sha": sha, "parent_repository": parent, "source_repository": source,
        "license": {"spdx": spdx, "status": "github_reported" if spdx else "unknown"},
        "compatibility": {"declared_dsh_range": None, "observed_base": None},
        "analysis_status": "not_analyzed",
        "verification": {"metadata_only": True, "executed": False, "security_verified": False},
    }


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as out:
        json.dump(value, out, indent=2, ensure_ascii=False)
        out.write("\n")
        name = out.name
    os.replace(name, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "data/public-repos.seed.json")
    args = parser.parse_args()
    preserved = {}
    if args.output.exists():
        current = json.loads(args.output.read_text(encoding="utf-8"))
        for key in ("supplemental_snapshot", "supplemental_entries", "package_entries", "package_browser"):
            if key in current:
                preserved[key] = current[key]
    fetched = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    repos, headers = get_json(ENDPOINT)
    if not isinstance(repos, list) or len(repos) != 10:
        raise ValueError("Expected exactly ten forks; existing snapshot has not been replaced")
    if len({r["id"] for r in repos}) != 10:
        raise ValueError("Duplicate GitHub repository IDs")
    stars = [r["stargazers_count"] for r in repos]
    if stars != sorted(stars, reverse=True):
        raise ValueError("GitHub results are not in descending star order")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(enrich, enumerate(repos, 1)))
    snapshot = {
        "schema_version": 1, "snapshot_id": "manual-top10-" + fetched.replace(":", ""),
        "fetched_at": fetched, "completed_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "upstream": UPSTREAM, "source_url": ENDPOINT,
        "selection": {"method": "github_forks_endpoint", "sort": "stargazers", "limit": 10,
                      "ties": "GitHub response order", "archived_included": True},
        "provenance": {"method": "one_shot_github_rest", "response_headers": headers,
                       "signature_status": "unsigned_development_seed",
                       "note": "Metadata calls are sequential snapshots, not one atomic view of GitHub."},
        "entries": entries,
        **preserved,
    }
    if "supplemental_entries" not in snapshot:
        snapshot["supplemental_entries"] = []
    if "package_entries" not in snapshot:
        snapshot["package_entries"] = []
    # Only replace the seed after every entry and its immutable reference has been validated.
    atomic_json(args.output, snapshot)
    atomic_json(args.output.with_name("github-forks.response.json"), repos)
    print(f"Saved {len(entries)} public fork metadata records to {args.output}")
    for entry in entries:
        print(entry["seed_rank"], entry["full_name"], entry["github_stars"], entry["head_sha"][:12])


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, urllib.error.URLError) as error:
        raise SystemExit(f"Seed import failed; keep the previous snapshot. {error}")
