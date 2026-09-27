"""Bounded GitHub social-preview enrichment for catalog thumbnails.

Only repositories that uploaded a custom social preview get a
``social_preview_url``. GitHub's generated fallback cards are ignored because
Forge already draws deterministic cover art for every record. The pass reads
public metadata through the GraphQL API and never clones or executes anything.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Iterable, Mapping
from urllib.request import Request, urlopen


GITHUB_GRAPHQL = "https://api.github.com/graphql"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
DEFAULT_BATCH_SIZE = 60
DEFAULT_MAX_BATCHES = 700
COVERAGE_SOURCE = "github-graphql/social-preview"

_SLUG = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}")
PREVIEW_URL = re.compile(r"https://repository-images\.githubusercontent\.com/\d{1,12}/[A-Za-z0-9-]{8,64}")
AVATAR_URL = re.compile(r"https://avatars\.githubusercontent\.com/(?:u/\d{1,12}|[A-Za-z0-9-]{1,39})(?:\?[A-Za-z0-9=&._-]{0,64})?")


class PreviewError(ValueError):
    """GitHub returned a response that cannot be used safely."""


def safe_preview_url(value: Any) -> str | None:
    """Return a GitHub-hosted custom preview URL, or None."""
    return value if isinstance(value, str) and PREVIEW_URL.fullmatch(value) else None


def safe_avatar_url(value: Any) -> str | None:
    """Return a GitHub avatar URL, or None."""
    return value if isinstance(value, str) and AVATAR_URL.fullmatch(value) else None


def _query(slugs: list[str]) -> str:
    fields = []
    for index, slug in enumerate(slugs):
        owner, name = slug.split("/", 1)
        # Slugs are validated against a strict character set before this point,
        # so they cannot close the string literal.
        fields.append(
            f'r{index}: repository(owner: "{owner}", name: "{name}") '
            "{ usesCustomOpenGraphImage openGraphImageUrl }"
        )
    return "query SocialPreviews {\n  " + "\n  ".join(fields) + "\n}"


def _post(query: str, token: str, opener: Callable[..., Any]) -> Mapping[str, Any]:
    body = json.dumps({"query": query}).encode("utf-8")
    request = Request(
        GITHUB_GRAPHQL,
        data=body,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Accept-Encoding": "identity",
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "DSH-Forge-preview-indexer/1",
        },
    )
    with opener(request, timeout=60) as response:
        if response.geturl() != GITHUB_GRAPHQL:
            raise PreviewError("GitHub GraphQL redirected away from the API")
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    if len(payload) > MAX_RESPONSE_BYTES:
        raise PreviewError("GitHub GraphQL response exceeds the byte limit")
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PreviewError("GitHub GraphQL returned invalid JSON") from None
    if not isinstance(value, Mapping):
        raise PreviewError("GitHub GraphQL returned an invalid document")
    return value


def fetch_social_previews(
    slugs: Iterable[str],
    *,
    token: str,
    opener: Callable[..., Any] = urlopen,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_batches: int = DEFAULT_MAX_BATCHES,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Return ``{slug: preview_url}`` and a coverage record.

    Missing, renamed, or private repositories resolve to null in GraphQL and
    are skipped. A failed batch stops the pass and marks coverage incomplete
    rather than failing the whole catalog build.
    """
    if not isinstance(token, str) or not token or len(token) > 4096:
        raise PreviewError("A GitHub token is required for the GraphQL preview pass")
    if not 1 <= batch_size <= 100:
        raise PreviewError("Preview batch size must be between 1 and 100")
    unique = sorted({slug for slug in slugs if isinstance(slug, str) and _SLUG.fullmatch(slug)})
    previews: dict[str, str] = {}
    checked = 0
    failure = None
    batches = [unique[index:index + batch_size] for index in range(0, len(unique), batch_size)]
    for batch in batches[:max_batches]:
        try:
            document = _post(_query(batch), token, opener)
        except (OSError, PreviewError) as error:
            failure = f"{type(error).__name__}: {str(error)[:200]}"
            break
        data = document.get("data")
        if not isinstance(data, Mapping):
            failure = "GitHub GraphQL returned no data"
            break
        for index, slug in enumerate(batch):
            node = data.get(f"r{index}")
            if not isinstance(node, Mapping):
                continue
            url = safe_preview_url(node.get("openGraphImageUrl"))
            if node.get("usesCustomOpenGraphImage") is True and url:
                previews[slug] = url
        checked += len(batch)
    complete = failure is None and checked == len(unique)
    coverage = {
        "source": COVERAGE_SOURCE,
        "status": "complete" if complete else "incomplete",
        "repository_count": len(unique),
        "checked_count": checked,
        "custom_preview_count": len(previews),
    }
    if failure:
        coverage["failure"] = failure
    elif not complete:
        coverage["failure"] = f"Batch limit reached after {checked} repositories"
    return previews, coverage


def apply_social_previews(snapshot: dict[str, Any], previews: Mapping[str, str]) -> int:
    """Attach preview URLs to plugin and fork records in place."""
    applied = 0
    for key in ("entries", "supplemental_entries"):
        for entry in snapshot.get(key) or []:
            if not isinstance(entry, dict):
                continue
            url = safe_preview_url(previews.get(str(entry.get("full_name") or "")))
            if url:
                entry["social_preview_url"] = url
                applied += 1
            else:
                entry.pop("social_preview_url", None)
    return applied


def repository_slugs(snapshot: Mapping[str, Any]) -> list[str]:
    return [
        str(entry.get("full_name"))
        for key in ("entries", "supplemental_entries")
        for entry in snapshot.get(key) or []
        if isinstance(entry, Mapping) and entry.get("full_name")
    ]
