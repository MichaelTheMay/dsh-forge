"""Deterministic metadata enrichment for the public catalog.

Every published record carries GitHub metadata and little else, which leaves the
browser with nothing to facet, filter, or feature on. This module derives a
bounded tag set from metadata the crawler already collected, so enrichment costs
no extra API calls and produces the same tags for the same input.

Nothing here inspects, downloads, or executes repository code. Tags describe what
a record *claims* about itself; they are discovery aids, not verification.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, MutableMapping
from typing import Any

from .research import _mentions

ENRICHMENT_SCHEMA = "dsh-forge.enrichment/v1"
ENRICHMENT_POLICY = "dsh-forge.tags/v1"

#: Tag families. Each tag maps to the terms that evidence it. Terms are matched
#: on word boundaries against the description, topics, name, and language, so a
#: tag is only applied when the record itself mentions the concept.
TAXONOMY: dict[str, dict[str, tuple[str, ...]]] = {
    "capability": {
        "memory": ("memory", "recall", "knowledge base", "long-term context", "persistence"),
        "code-intelligence": ("code index", "symbol", "codebase", "repository map", "ast", "code graph"),
        "review": ("review", "audit", "lint", "code quality", "pull request review"),
        "security": ("security", "permission", "supply chain", "vulnerability", "sandbox", "secrets"),
        "testing": ("test", "browser automation", "playwright", "evaluation", "eval", "coverage"),
        "orchestration": ("agent team", "multi-agent", "orchestration", "workflow", "swarm", "subagent"),
        "observability": ("observability", "trace", "logging", "metrics", "telemetry", "dashboard"),
        "search": ("search", "retrieval", "index", "rag", "embedding", "semantic search"),
        "refactoring": ("refactor", "codemod", "rewrite", "migration"),
        "documentation": ("documentation", "docs", "docstring", "readme generation"),
        "debugging": ("debug", "breakpoint", "stack trace", "root cause"),
        "planning": ("planning", "task decomposition", "roadmap", "todo", "task dag"),
        "data-analysis": ("data analysis", "notebook", "dataframe", "sql", "analytics"),
        "ui-generation": ("ui generation", "component generation", "design system", "frontend scaffold"),
        "prompt-engineering": ("prompt", "system prompt", "instruction tuning", "context engineering"),
        "cost-control": ("token budget", "cost", "rate limit", "quota", "spend"),
    },
    "integration": {
        "mcp": ("mcp", "model context protocol"),
        "git": ("git", "commit", "branch", "worktree"),
        "github": ("github", "pull request", "gh cli"),
        "gitlab": ("gitlab",),
        "jira": ("jira", "linear", "issue tracker"),
        "slack": ("slack",),
        "discord": ("discord",),
        "notion": ("notion", "obsidian", "confluence"),
        "database": ("database", "postgres", "sqlite", "mysql", "redis", "mongodb"),
        "docker": ("docker", "container", "compose"),
        "kubernetes": ("kubernetes", "k8s", "helm"),
        "cloud": ("aws", "gcp", "azure", "cloudflare", "vercel"),
        "browser": ("browser", "chrome", "puppeteer", "selenium"),
        "editor": ("vscode", "neovim", "jetbrains", "emacs", "editor extension"),
        "api": ("rest api", "graphql", "webhook", "openapi"),
    },
    "runtime": {
        "cli": ("cli", "command line", "terminal", "tui"),
        "web-ui": ("web ui", "web gui", "dashboard", "browser ui", "web panel"),
        "desktop-app": ("desktop", "electron", "tauri", "native app"),
        "daemon": ("daemon", "server", "sidecar", "background service"),
        "extension": ("extension", "plugin host", "add-on"),
        "library": ("library", "sdk", "package", "module"),
    },
    "maturity": {
        "actively-maintained": (),  # derived, not keyword-matched
        "archived": (),
        "has-license": (),
        "pinned-release": (),
        "well-known": (),
        "low-visibility": (),
    },
}

#: Families whose tags come from keyword evidence rather than derived signals.
KEYWORD_FAMILIES = ("capability", "integration", "runtime")

MAX_TAGS_PER_FAMILY = 6

#: Descriptions a fork inherits verbatim from upstream carry no signal about the
#: fork itself. Anything repeated across more than this share of a corpus is
#: treated as inherited boilerplate rather than a description of that record.
BOILERPLATE_SHARE = 0.01
GENERIC_DESCRIPTIONS = frozenset({"", "no repository description provided."})


def _haystack(record: Mapping[str, Any]) -> str:
    topics = record.get("topics") if isinstance(record.get("topics"), list) else []
    parts = [
        str(record.get("description") or ""),
        str(record.get("name") or ""),
        str(record.get("language") or ""),
        *[str(item) for item in topics if isinstance(item, str)],
    ]
    package = record.get("package")
    if isinstance(package, Mapping):
        parts.append(str(package.get("name") or ""))
    # Topic slugs are hyphenated; matching treats those as word separators.
    return " ".join(parts).replace("-", " ").replace("_", " ").casefold()


def _known_license(record: Mapping[str, Any]) -> bool:
    value = record.get("license")
    spdx = value.get("spdx") if isinstance(value, Mapping) else None
    return isinstance(spdx, str) and bool(spdx) and spdx not in {"NOASSERTION", "UNKNOWN"}


def _days_since_push(record: Mapping[str, Any], observed_at: Any = None) -> int | None:
    import datetime as dt

    def parse(value: Any) -> dt.datetime | None:
        if not isinstance(value, str) or len(value) > 64:
            return None
        try:
            parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=dt.timezone.utc)

    reference = parse(observed_at) or parse(record.get("indexed_at")) or dt.datetime.now(dt.timezone.utc)
    pushed = parse(record.get("pushed_at"))
    if pushed is None:
        return None
    return max(0, (reference - pushed).days)


def derive_tags(record: Mapping[str, Any], observed_at: Any = None) -> dict[str, list[str]]:
    """Return tags grouped by family. Deterministic for a given record."""

    text = _haystack(record)
    families: dict[str, list[str]] = {}
    for family in KEYWORD_FAMILIES:
        matched = [
            tag for tag, terms in TAXONOMY[family].items()
            if any(_mentions(text, term.replace("-", " ")) for term in terms)
        ]
        if matched:
            families[family] = sorted(matched)[:MAX_TAGS_PER_FAMILY]

    maturity: list[str] = []
    age = _days_since_push(record, observed_at)
    if record.get("archived") is True:
        maturity.append("archived")
    elif age is not None and age <= 90:
        maturity.append("actively-maintained")
    if _known_license(record):
        maturity.append("has-license")
    package = record.get("package")
    if isinstance(package, Mapping) and package.get("name") and package.get("version"):
        maturity.append("pinned-release")
    stars = record.get("github_stars")
    if isinstance(stars, int) and not isinstance(stars, bool):
        maturity.append("well-known" if stars > 200 else ("low-visibility" if stars <= 50 else ""))
    maturity = [tag for tag in maturity if tag]
    if maturity:
        families["maturity"] = sorted(maturity)
    return families


def flatten_tags(families: Mapping[str, Iterable[str]]) -> list[str]:
    """Flatten grouped tags into a stable, de-duplicated list."""

    seen: list[str] = []
    for family in ("capability", "integration", "runtime", "maturity"):
        for tag in families.get(family, ()):
            if tag not in seen:
                seen.append(tag)
    return seen


def primary_capability(families: Mapping[str, Iterable[str]]) -> str:
    """The capability a record leads with, used to group best-in-class picks."""

    capabilities = list(families.get("capability", ()))
    return capabilities[0] if capabilities else ""


#: The per-record block repeats for every record in a 37,000-record feed, so it
#: carries only what varies. Everything constant — schema, policy, and the claim
#: that nothing was executed — is stated once per snapshot in
#: :func:`enrichment_metadata`. Empty fields are omitted rather than stored.
def enrich_record(record: Mapping[str, Any], observed_at: Any = None) -> dict[str, Any]:
    """Build the compact per-record enrichment block."""

    families = derive_tags(record, observed_at)
    block: dict[str, Any] = {"tags": flatten_tags(families)}
    capability = primary_capability(families)
    if capability:
        block["primary_capability"] = capability
    return block


def enrichment_metadata() -> dict[str, Any]:
    """The constant half of enrichment, stated once per snapshot."""

    return {
        "schema": ENRICHMENT_SCHEMA,
        "policy": ENRICHMENT_POLICY,
        "tag_source": "deterministic",
        "maturity_tags": sorted(TAXONOMY["maturity"]),
        "claims": {"executed": False, "code_inspected": False, "metadata_only": True},
    }


def descriptive_tags(tags: Iterable[str]) -> list[str]:
    """Tags that say what a record does, excluding the derived maturity flags."""

    maturity = set(TAXONOMY["maturity"])
    return [tag for tag in tags if tag not in maturity]


def _boilerplate_descriptions(records: Iterable[Mapping[str, Any]]) -> set[str]:
    """Descriptions shared by so many records that they describe none of them."""

    counts: dict[str, int] = {}
    total = 0
    for record in records:
        text = str(record.get("description") or "").strip().casefold()
        counts[text] = counts.get(text, 0) + 1
        total += 1
    if not total:
        return set(GENERIC_DESCRIPTIONS)
    threshold = max(2, int(total * BOILERPLATE_SHARE))
    shared = {text for text, count in counts.items() if count >= threshold}
    return shared | set(GENERIC_DESCRIPTIONS)


def differentiation(record: Mapping[str, Any], boilerplate: frozenset[str] | set[str]) -> dict[str, Any]:
    """Decide whether a record says anything about itself.

    The fork corpus is overwhelmingly unmodified clones that inherit the upstream
    description, carry no topics, and have no stars. They cannot be ranked,
    tagged, or featured, and spending analysis budget on them starves the records
    that can be. This marks the ones worth enriching further.
    """

    reasons: list[str] = []
    text = str(record.get("description") or "").strip().casefold()
    if text and text not in boilerplate:
        reasons.append("own-description")
    if record.get("topics"):
        reasons.append("own-topics")
    stars = record.get("github_stars")
    if isinstance(stars, int) and not isinstance(stars, bool) and stars > 2:
        reasons.append("attention")
    divergence = record.get("divergence")
    if isinstance(divergence, Mapping):
        ahead = divergence.get("ahead_by")
        if isinstance(ahead, int) and not isinstance(ahead, bool) and ahead > 0:
            reasons.append("diverged-from-upstream")
    package = record.get("package")
    if isinstance(package, Mapping) and package.get("name"):
        reasons.append("published-package")
    return {"differentiated": True, "signals": reasons} if reasons else {"differentiated": False}


def enrich_snapshot(snapshot: MutableMapping[str, Any], observed_at: Any = None) -> dict[str, Any]:
    """Attach an ``enrichment`` block to every record in a registry snapshot.

    Mutates the snapshot in place and returns coverage counts.
    """

    snapshot["enrichment_metadata"] = enrichment_metadata()
    observed = observed_at or snapshot.get("completed_at") or snapshot.get("fetched_at")
    counts = {"records": 0, "tagged": 0, "untagged": 0, "differentiated": 0, "boilerplate": 0}
    tag_totals: dict[str, int] = {}
    for key in ("entries", "supplemental_entries", "package_entries"):
        records = snapshot.get(key)
        if not isinstance(records, list):
            continue
        # Boilerplate is judged per corpus, so a fork network's shared upstream
        # description does not suppress a plugin that happens to reuse the words.
        boilerplate = _boilerplate_descriptions(
            record for record in records if isinstance(record, Mapping)
        )
        for record in records:
            if not isinstance(record, MutableMapping):
                continue
            enrichment = enrich_record(record, observed)
            enrichment.update(differentiation(record, boilerplate))
            record["enrichment"] = enrichment
            counts["records"] += 1
            if enrichment["tags"]:
                counts["tagged"] += 1
            else:
                counts["untagged"] += 1
            if enrichment["differentiated"]:
                counts["differentiated"] += 1
            else:
                counts["boilerplate"] += 1
            for tag in enrichment["tags"]:
                tag_totals[tag] = tag_totals.get(tag, 0) + 1
    counts["coverage"] = round(counts["tagged"] / counts["records"], 4) if counts["records"] else 0.0
    counts["distinct_tags"] = len(tag_totals)
    counts["differentiated_share"] = (
        round(counts["differentiated"] / counts["records"], 4) if counts["records"] else 0.0
    )
    counts["top_tags"] = sorted(tag_totals.items(), key=lambda item: (-item[1], item[0]))[:20]
    return counts


def build_facets(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Count facet values so the browser can show live counts without a scan."""

    facets: dict[str, dict[str, dict[str, int]]] = {}
    for key, artifact_type in (
        ("entries", "fork"),
        ("supplemental_entries", "plugin"),
        ("package_entries", "package"),
    ):
        records = snapshot.get(key)
        if not isinstance(records, list) or not records:
            continue
        bucket = facets.setdefault(artifact_type, {"tag": {}, "language": {}, "license": {}})
        for record in records:
            if not isinstance(record, Mapping):
                continue
            enrichment = record.get("enrichment")
            tags = enrichment.get("tags", []) if isinstance(enrichment, Mapping) else []
            for tag in tags:
                bucket["tag"][tag] = bucket["tag"].get(tag, 0) + 1
            language = str(record.get("language") or "").strip()
            if language:
                bucket["language"][language] = bucket["language"].get(language, 0) + 1
            license_value = record.get("license")
            spdx = license_value.get("spdx") if isinstance(license_value, Mapping) else None
            if isinstance(spdx, str) and spdx and spdx not in {"NOASSERTION", "UNKNOWN"}:
                bucket["license"][spdx] = bucket["license"].get(spdx, 0) + 1
    return {
        "schema": "dsh-forge.facets/v1",
        "policy": ENRICHMENT_POLICY,
        "facets": {
            artifact_type: {
                name: sorted(values.items(), key=lambda item: (-item[1], item[0]))
                for name, values in groups.items()
            }
            for artifact_type, groups in facets.items()
        },
    }
