"""Bounded GitHub evidence for hidden-gem discovery.

The catalog crawl only knows what a repository listing says about itself:
stars, a description, a push date. That is enough to browse but not to tell a
well-built project from an abandoned experiment. This stage reads a small,
fixed set of public facts for each promising repository through one batched
GraphQL query per 25 repositories:

- engineering: README size, test and CI presence, docs, examples, changelog,
  releases;
- activity: total commits and commits in the last 90 days;
- community: closed issues, merged pull requests, people who can be mentioned
  (an approximation of contributors);
- attention: stars, forks, watchers, and the ten most recent stargazers.

Nothing is cloned, installed, or executed. Evidence observed on an earlier day
is reused while the repository has not been pushed since, so coverage grows
across daily runs without exceeding the Actions token budget.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
import time
from typing import Any, Callable, Iterable, Mapping
from urllib.request import Request, urlopen


EVIDENCE_SCHEMA = "dsh-forge.repo-evidence/v1"
COVERAGE_SOURCE = "github-graphql/repo-evidence"
GITHUB_GRAPHQL = "https://api.github.com/graphql"
GITHUB_API = "https://api.github.com"
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
DEFAULT_BATCH_SIZE = 25
DEFAULT_MAX_REPOSITORIES = 3_000
DEFAULT_MAX_POINTS = 900
DEFAULT_DEADLINE_SECONDS = 20 * 60
# The previously deployed public API rejects registries over 64 MB expanded, so the
# published registry keeps a margin below that whatever evidence accumulates.
MAX_PUBLISHED_REGISTRY_BYTES = 60 * 1024 * 1024
REUSE_DAYS = 14
RECENT_DAYS = 90
STARGAZER_SAMPLE = 10

_SLUG = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}")
_LOGIN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}")
_TEST_DIRECTORIES = {"test", "tests", "__tests__", "spec", "specs", "testing", "e2e"}
_TEST_FILES = re.compile(
    r"^(?:(?:vitest|jest|playwright|karma|cypress)\.config\.[cm]?[jt]s|pytest\.ini|tox\.ini|conftest\.py|\.mocharc(?:\.[a-z]+)?)$"
)
_DOC_DIRECTORIES = {"docs", "doc", "documentation", "website", "site"}
_EXAMPLE_DIRECTORIES = {"examples", "example", "samples", "sample", "demo", "demos"}
_CHANGELOG = re.compile(r"^(?:changelog|changes|history|releases)(?:\.[a-z]+)?$")
_CI_FILES = {".gitlab-ci.yml", ".travis.yml", "azure-pipelines.yml", "appveyor.yml"}
_CI_DIRECTORIES = {".circleci", ".buildkite"}


class EnrichmentError(ValueError):
    """GitHub returned something this stage cannot use safely."""


def _instant(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _count(value: Any) -> int | None:
    if isinstance(value, Mapping):
        value = value.get("totalCount")
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def has_own_commits(record: Mapping[str, Any]) -> bool | None:
    """Whether a fork was pushed after it was created (None when unknown).

    A new fork inherits its parent's push time, which is never after the fork's
    creation; a minute of slack absorbs clock rounding.
    """
    created = _instant(record.get("created_at"))
    pushed = _instant(record.get("pushed_at"))
    if not created or not pushed:
        return None
    return pushed - created > dt.timedelta(minutes=1)


def _records(snapshot: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        record
        for key in ("entries", "supplemental_entries")
        for record in snapshot.get(key) or []
        if isinstance(record, Mapping) and _SLUG.fullmatch(str(record.get("full_name") or ""))
    ]


def eligible(record: Mapping[str, Any]) -> bool:
    """Whether a repository could plausibly be a gem and deserves evidence."""
    if record.get("archived") is True:
        return False
    if record.get("artifact_type") != "fork":
        return True
    if isinstance(record.get("divergence"), Mapping):
        return True
    stars = record.get("github_stars")
    if isinstance(stars, int) and stars > 0:
        return True
    # Most forks are untouched copies of upstream; skip those that were never pushed.
    return has_own_commits(record) is True


def priority(record: Mapping[str, Any], observed_at: dt.datetime) -> float:
    """A cheap prior used only to decide which repositories to read first."""
    stars = record.get("github_stars")
    stars = stars if isinstance(stars, int) and not isinstance(stars, bool) and stars > 0 else 0
    value = 2.0 * math.log1p(stars)
    pushed = _instant(record.get("pushed_at"))
    if pushed:
        age = (observed_at - pushed).days
        value += 2.0 if age <= 90 else (1.0 if age <= 365 else 0.0)
    description = str(record.get("description") or "")
    if len(description) >= 40 and not description.startswith("No repository description"):
        value += 1.0
    license_value = record.get("license") if isinstance(record.get("license"), Mapping) else {}
    if license_value.get("spdx"):
        value += 0.5
    if record.get("artifact_type") == "fork":
        divergence = record.get("divergence") if isinstance(record.get("divergence"), Mapping) else {}
        ahead = divergence.get("ahead_by")
        if isinstance(ahead, int) and ahead > 0:
            value += 1.5 + min(2.0, math.log1p(ahead) / 2)
    return value


def previous_evidence(snapshot: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Index evidence carried by an earlier published registry, by lowercase slug."""
    index: dict[str, dict[str, Any]] = {}
    if not isinstance(snapshot, Mapping):
        return index
    for record in _records(snapshot):
        evidence = record.get("evidence")
        if isinstance(evidence, Mapping) and evidence.get("schema") == EVIDENCE_SCHEMA:
            index[str(record["full_name"]).casefold()] = dict(evidence)
    return index


def reusable(evidence: Mapping[str, Any] | None, record: Mapping[str, Any], observed_at: dt.datetime) -> bool:
    if not isinstance(evidence, Mapping) or evidence.get("schema") != EVIDENCE_SCHEMA:
        return False
    seen = _instant(evidence.get("observed_at"))
    if not seen or (observed_at - seen).days > REUSE_DAYS:
        return False
    return evidence.get("pushed_at") == record.get("pushed_at")


def plan_targets(
    snapshot: Mapping[str, Any],
    previous: Mapping[str, Mapping[str, Any]],
    *,
    observed_at: dt.datetime,
    max_repositories: int = DEFAULT_MAX_REPOSITORIES,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """Return slugs to fetch (highest priority first) and evidence to reuse."""
    reused: dict[str, dict[str, Any]] = {}
    pending: list[tuple[float, str, str]] = []
    for record in _records(snapshot):
        if not eligible(record):
            continue
        slug = str(record["full_name"])
        earlier = previous.get(slug.casefold())
        if reusable(earlier, record, observed_at):
            reused[slug.casefold()] = dict(earlier)
            continue
        pending.append((-priority(record, observed_at), slug.casefold(), slug))
    pending.sort()
    return [slug for _, _, slug in pending[:max_repositories]], reused


# Optional parts of the evidence query. A token that may not read one of them
# (the Actions token is refused some user fields) makes GitHub null the whole
# repository, so a refused part is dropped for the rest of the run instead.
_SECTIONS = {
    "watchers": "  watchers { totalCount }\n",
    "issues": "  openIssues: issues(states: OPEN) { totalCount }\n  closedIssues: issues(states: CLOSED) { totalCount }\n",
    "pullRequests": "  mergedPullRequests: pullRequests(states: MERGED) { totalCount }\n",
    "releases": "  releases { totalCount }\n",
    "mentionableUsers": "  mentionableUsers { totalCount }\n",
    "licenseInfo": "  licenseInfo { spdxId }\n",
    "followers": "",  # folded into the owner selection below
    "history": None,  # needs the recent-commit date
    "root": '  root: object(expression: "HEAD:") { ... on Tree { entries { name type object { ... on Blob { byteSize } } } } }\n',
    "workflows": '  workflows: object(expression: "HEAD:.github/workflows") { ... on Tree { entries { name } } }\n',
    "stargazers": None,  # needs the sample size
}
# Names that can appear in a GraphQL error path, mapped to the section that asked for them.
_PATH_SECTIONS = {
    "watchers": "watchers", "openIssues": "issues", "closedIssues": "issues",
    "mergedPullRequests": "pullRequests", "releases": "releases",
    "mentionableUsers": "mentionableUsers", "licenseInfo": "licenseInfo",
    "followers": "followers", "defaultBranchRef": "history", "target": "history",
    "history": "history", "recent": "history", "root": "root", "workflows": "workflows",
    "stargazers": "stargazers", "edges": "stargazers", "starredAt": "stargazers",
}


def _query(slugs: list[str], since: str, omit: Iterable[str] = ()) -> str:
    omitted = set(omit)
    fields = []
    for index, slug in enumerate(slugs):
        owner, name = slug.split("/", 1)
        fields.append(
            f'r{index}: repository(owner: "{owner}", name: "{name}") {{ ...evidence }}'
        )
    parts = ["  nameWithOwner createdAt pushedAt isArchived stargazerCount forkCount\n"]
    for section, text in _SECTIONS.items():
        if section in omitted:
            continue
        if section == "history":
            parts.append(
                "  defaultBranchRef { target { ... on Commit {\n"
                "    history { totalCount }\n"
                f'    recent: history(since: "{since}") {{ totalCount }}\n'
                "  } } }\n"
            )
        elif section == "stargazers":
            parts.append(
                f"  stargazers(first: {STARGAZER_SAMPLE}, orderBy: {{field: STARRED_AT, direction: DESC}}) "
                "{ edges { starredAt node { login } } }\n"
            )
        elif text:
            parts.append(text)
    parts.append(
        "  owner { login __typename ... on User { followers { totalCount } } }\n"
        if "followers" not in omitted else "  owner { login __typename }\n"
    )
    return (
        "query RepoEvidence {\n  rateLimit { cost remaining resetAt }\n  "
        + "\n  ".join(fields)
        + "\n}\n"
        + "fragment evidence on Repository {\n"
        + "".join(parts)
        + "}\n"
    )


def _refused_sections(document: Mapping[str, Any]) -> set[str]:
    """Query sections named in error paths (for example a field the token may not read)."""
    found: set[str] = set()
    for error in document.get("errors") or []:
        if not isinstance(error, Mapping):
            continue
        for element in (error.get("path") or [])[1:]:
            section = _PATH_SECTIONS.get(str(element))
            if section:
                found.add(section)
                break
    return found


def _error_summary(document: Mapping[str, Any]) -> str:
    for error in document.get("errors") or []:
        if isinstance(error, Mapping) and error.get("message"):
            return str(error.get("type") or "") + " " + str(error["message"])[:160]
    return "GitHub GraphQL returned no repositories for this batch"


def _post(query: str, token: str, opener: Callable[..., Any]) -> Mapping[str, Any]:
    request = Request(
        GITHUB_GRAPHQL,
        data=json.dumps({"query": query}).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Accept-Encoding": "identity",
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "DSH-Forge-evidence-indexer/1",
        },
    )
    with opener(request, timeout=90) as response:
        if response.geturl() != GITHUB_GRAPHQL:
            raise EnrichmentError("GitHub GraphQL redirected away from the API")
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise EnrichmentError("GitHub GraphQL response exceeds the byte limit")
    try:
        document = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise EnrichmentError("GitHub GraphQL returned invalid JSON") from None
    if not isinstance(document, Mapping):
        raise EnrichmentError("GitHub GraphQL returned an invalid document")
    return document


def normalize(node: Mapping[str, Any], observed_at: dt.datetime) -> dict[str, Any]:
    """Reduce one GraphQL repository node to the bounded evidence record."""
    root = node.get("root") if isinstance(node.get("root"), Mapping) else {}
    entries = [entry for entry in root.get("entries") or [] if isinstance(entry, Mapping)][:2_000]
    names = {str(entry.get("name") or "").casefold(): entry for entry in entries}
    trees = {name for name, entry in names.items() if entry.get("type") == "tree"}
    blobs = {name for name, entry in names.items() if entry.get("type") == "blob"}
    readme_bytes = 0
    for name, entry in names.items():
        if name.startswith("readme") and entry.get("type") == "blob":
            size = (entry.get("object") or {}).get("byteSize") if isinstance(entry.get("object"), Mapping) else None
            if isinstance(size, int) and size > readme_bytes:
                readme_bytes = min(size, 10_000_000)
    workflows = node.get("workflows") if isinstance(node.get("workflows"), Mapping) else {}
    workflow_files = [
        entry for entry in workflows.get("entries") or []
        if isinstance(entry, Mapping) and str(entry.get("name") or "").casefold().endswith((".yml", ".yaml"))
    ]
    branch = node.get("defaultBranchRef") if isinstance(node.get("defaultBranchRef"), Mapping) else {}
    target = branch.get("target") if isinstance(branch.get("target"), Mapping) else {}
    owner = node.get("owner") if isinstance(node.get("owner"), Mapping) else {}
    stargazers = []
    for edge in ((node.get("stargazers") or {}).get("edges") or [])[:STARGAZER_SAMPLE]:
        if not isinstance(edge, Mapping):
            continue
        login = str(((edge.get("node") or {}) if isinstance(edge.get("node"), Mapping) else {}).get("login") or "")
        starred = _instant(edge.get("starredAt"))
        if _LOGIN.fullmatch(login) and starred:
            stargazers.append({"login": login, "starred_at": _iso(starred)})
    license_info = node.get("licenseInfo") if isinstance(node.get("licenseInfo"), Mapping) else {}
    spdx = license_info.get("spdxId")
    return {
        "schema": EVIDENCE_SCHEMA,
        "observed_at": _iso(observed_at),
        "created_at": _iso(_instant(node.get("createdAt"))) if _instant(node.get("createdAt")) else None,
        "pushed_at": node.get("pushedAt") if isinstance(node.get("pushedAt"), str) else None,
        "archived": node.get("isArchived") is True,
        "stars": _count(node.get("stargazerCount")),
        "forks": _count(node.get("forkCount")),
        "watchers": _count(node.get("watchers")),
        "open_issues": _count(node.get("openIssues")),
        "closed_issues": _count(node.get("closedIssues")),
        "merged_pull_requests": _count(node.get("mergedPullRequests")),
        "releases": _count(node.get("releases")),
        "contributors": _count(node.get("mentionableUsers")),
        "commits_total": _count(target.get("history")),
        "commits_recent": _count(target.get("recent")),
        "readme_bytes": readme_bytes,
        "has_tests": bool(trees & _TEST_DIRECTORIES) or any(_TEST_FILES.match(name) for name in blobs),
        "ci_workflows": len(workflow_files)
        + (1 if blobs & _CI_FILES else 0)
        + (1 if trees & _CI_DIRECTORIES else 0),
        "has_docs": bool(trees & _DOC_DIRECTORIES),
        "has_examples": bool(trees & _EXAMPLE_DIRECTORIES),
        "has_changelog": any(_CHANGELOG.match(name) for name in blobs),
        "license": spdx if isinstance(spdx, str) and spdx not in {"NOASSERTION", "OTHER"} else None,
        "owner_type": "Organization" if owner.get("__typename") == "Organization" else "User",
        "owner_followers": _count(owner.get("followers")),
        "recent_stargazers": stargazers,
    }


def fetch_evidence(
    slugs: Iterable[str],
    *,
    token: str,
    observed_at: dt.datetime,
    opener: Callable[..., Any] = urlopen,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_points: int = DEFAULT_MAX_POINTS,
    deadline_seconds: float = DEFAULT_DEADLINE_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    pause: Callable[[float], None] = time.sleep,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Fetch evidence within a point budget and deadline; never raise on a bad batch."""
    if not isinstance(token, str) or not token or len(token) > 4096:
        raise EnrichmentError("A GitHub token is required for evidence enrichment")
    if not 1 <= batch_size <= 50:
        raise EnrichmentError("Evidence batch size must be between 1 and 50")
    targets = [slug for slug in dict.fromkeys(slugs) if isinstance(slug, str) and _SLUG.fullmatch(slug)]
    since = _iso(observed_at - dt.timedelta(days=RECENT_DAYS))
    started = clock()
    omitted: set[str] = set()
    evidence: dict[str, dict[str, Any]] = {}
    spent = 0
    attempted = 0
    failures: list[str] = []
    stop_reason = ""
    queue = [targets[index:index + batch_size] for index in range(0, len(targets), batch_size)]
    while queue:
        if clock() - started > deadline_seconds:
            stop_reason = "deadline reached"
            break
        if spent >= max_points:
            stop_reason = "point budget reached"
            break
        batch = queue.pop(0)
        try:
            document = _post(_query(batch, since, omitted), token, opener)
            data = document.get("data")
            if not isinstance(data, Mapping) or not any(isinstance(data.get(f"r{i}"), Mapping) for i in range(len(batch))):
                refused = _refused_sections(document) - omitted
                if refused:
                    # Drop what the token may not read and retry the same batch.
                    omitted |= refused
                    spent += 1
                    queue.insert(0, batch)
                    continue
                # GitHub answers a timed-out query with HTTP 200, no data, and errors.
                raise EnrichmentError(_error_summary(document))
        except (OSError, EnrichmentError) as error:
            status = getattr(error, "code", None)
            if status in (403, 429):
                # A secondary rate limit: retrying in halves only makes it worse.
                failures.append(f"{batch[0]}: HTTP {status}")
                stop_reason = "GitHub rate limit reached"
                break
            # A slow or oversized batch is retried as two halves, after a pause; a
            # failed attempt still counts against the budget.
            spent += 1
            if len(batch) > 1:
                middle = len(batch) // 2
                queue[0:0] = [batch[:middle], batch[middle:]]
            else:
                failures.append(f"{batch[0]}: {type(error).__name__}: {str(error)[:160]}")
            pause(2.0)
            continue
        attempted += len(batch)
        rate = document.get("data", {}).get("rateLimit") if isinstance(document.get("data"), Mapping) else None
        if isinstance(rate, Mapping):
            cost = _count(rate.get("cost")) or 1
            spent += cost
            remaining = _count(rate.get("remaining"))
            if remaining is not None and remaining < max(10, cost * 3):
                stop_reason = "GitHub rate limit nearly exhausted"
                queue.clear()
        else:
            spent += 1
        data = document.get("data") if isinstance(document.get("data"), Mapping) else {}
        missing = []
        for index, slug in enumerate(batch):
            node = data.get(f"r{index}")
            if isinstance(node, Mapping):
                evidence[slug.casefold()] = normalize(node, observed_at)
            else:
                missing.append(slug)
        # Some repositories can be nulled by a refused field while others in the
        # batch succeed (only user-owned ones have followers): retry just those.
        refused = _refused_sections(document) - omitted
        if refused and missing:
            omitted |= refused
            queue.insert(0, missing)
        pause(0.2)
    complete = not queue and not stop_reason and not failures
    coverage = {
        "source": COVERAGE_SOURCE,
        "observed_at": _iso(observed_at),
        "status": "complete" if complete else "incomplete",
        "requested_count": len(targets),
        "attempted_count": attempted,
        "observed_count": len(evidence),
        "points_spent": spent,
        "point_budget": max_points,
    }
    if omitted:
        coverage["omitted_fields"] = sorted(omitted)
    if stop_reason:
        coverage["stopped"] = stop_reason
    if failures:
        coverage["failures"] = failures[:50]
    return evidence, coverage


def fetch_credible_accounts(
    snapshot: Mapping[str, Any],
    *,
    token: str | None,
    opener: Callable[..., Any] = urlopen,
    upstream: str = "deepseek-ai/deepseek-harness",
    plugin_star_floor: int = 50,
) -> list[str]:
    """Accounts whose star counts as an endorsement.

    Upstream Harness contributors plus authors of established plugins. These are
    people who know the ecosystem; their star on an obscure repository is a
    stronger signal than a stranger's.
    """
    accounts: set[str] = set()
    for record in _records(snapshot):
        stars = record.get("github_stars")
        if record.get("artifact_type") != "fork" and isinstance(stars, int) and stars >= plugin_star_floor:
            owner = str(record.get("owner") or "")
            if _LOGIN.fullmatch(owner):
                accounts.add(owner.casefold())
    if token:
        for page in range(1, 4):
            url = f"{GITHUB_API}/repos/{upstream}/contributors?per_page=100&page={page}"
            request = Request(url, headers={
                "Accept": "application/vnd.github+json",
                "Authorization": "Bearer " + token,
                "User-Agent": "DSH-Forge-evidence-indexer/1",
            })
            try:
                with opener(request, timeout=60) as response:
                    payload = json.loads(response.read(4 * 1024 * 1024))
            except (OSError, ValueError):
                break
            if not isinstance(payload, list) or not payload:
                break
            for item in payload:
                login = str((item or {}).get("login") or "") if isinstance(item, Mapping) else ""
                if _LOGIN.fullmatch(login) and (item.get("type") == "User"):
                    accounts.add(login.casefold())
            if len(payload) < 100:
                break
    return sorted(accounts)[:5_000]


def compact(
    raw: Mapping[str, Any],
    *,
    owner: str,
    credible_accounts: set[str],
    observed_at: dt.datetime,
) -> dict[str, Any]:
    """Resolve stargazers into endorsements and a recent-star count, then drop nulls.

    Published registries stay small: the old public API rejects registries over
    64 MB, and stargazer identities are only needed to count endorsements.
    """
    value = {key: item for key, item in raw.items() if key != "recent_stargazers" and item not in (None, False, 0, "")}
    value["schema"] = EVIDENCE_SCHEMA
    owner_key = owner.casefold()
    endorsed = []
    recent = 0
    for star in raw.get("recent_stargazers") or []:
        login = str(star.get("login") or "")
        if login.casefold() in credible_accounts and login.casefold() != owner_key:
            endorsed.append(login)
        starred = _instant(star.get("starred_at"))
        if starred and (observed_at - starred).days <= 30:
            recent += 1
    if endorsed:
        value["endorsed_by"] = endorsed[:STARGAZER_SAMPLE]
    if recent:
        value["stars_last_30d"] = recent
    return value


def apply_evidence(
    snapshot: dict[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
    *,
    credible_accounts: Iterable[str],
    coverage: Mapping[str, Any],
) -> int:
    """Attach evidence to records in place and record the discovery context."""
    applied = 0
    credible = {str(item).casefold() for item in credible_accounts}
    observed = _instant(coverage.get("observed_at")) or dt.datetime.now(dt.timezone.utc)
    for record in _records(snapshot):
        found = evidence.get(str(record["full_name"]).casefold())
        if isinstance(found, Mapping):
            # Fresh observations carry raw stargazers; reused ones are already compact.
            record["evidence"] = (
                compact(found, owner=str(record.get("owner") or ""), credible_accounts=credible, observed_at=observed)
                if "recent_stargazers" in found else dict(found)
            )
            applied += 1
        else:
            record.pop("evidence", None)  # type: ignore[union-attr]
    snapshot["discovery_context"] = {"credible_account_count": len(credible)}
    snapshot["coverage"] = [
        item for item in snapshot.get("coverage") or []
        if not (isinstance(item, Mapping) and item.get("source") == COVERAGE_SOURCE)
    ] + [dict(coverage, applied_count=applied)]
    return applied


def trim_evidence(
    snapshot: dict[str, Any],
    *,
    observed_at: dt.datetime,
    max_bytes: int = MAX_PUBLISHED_REGISTRY_BYTES,
) -> int:
    """Drop evidence from the least promising records until the registry fits.

    Returns how many records lost their evidence. Sizes are measured on the compact
    JSON encoding the feed publishes.
    """
    encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))  # noqa: E731
    total = len(encode(snapshot).encode("utf-8"))
    if total <= max_bytes:
        return 0
    carriers = sorted(
        (record for record in _records(snapshot) if isinstance(record.get("evidence"), Mapping)),
        key=lambda record: (priority(record, observed_at), str(record["full_name"]).casefold()),
    )
    dropped = 0
    for record in carriers:
        if total <= max_bytes:
            break
        total -= len(encode(record["evidence"]).encode("utf-8")) + len(',"evidence":')
        record.pop("evidence", None)  # type: ignore[union-attr]
        dropped += 1
    return dropped
