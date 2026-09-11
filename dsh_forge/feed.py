"""Publish and consume a bounded, checksum-verified public catalog feed."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .catalog_store import MAX_SNAPSHOT_BYTES
from .packages import read_json, write_json


REGISTRY_FEED_SCHEMA = "dsh-forge.registry-feed/v1"
DEFAULT_FEED_URL = (
    "https://github.com/MichaelTheMay/dsh-forge/"
    "releases/download/catalog-latest/registry-feed.json"
)
MAX_FEED_BYTES = 1_048_576
MAX_COMPRESSED_BYTES = 64 * 1024 * 1024


class FeedError(ValueError):
    """A public feed failed its transport, schema, or checksum contract."""


def _url(value: Any, label: str) -> str:
    parsed = urlsplit(value) if isinstance(value, str) else None
    if (
        not parsed or parsed.scheme != "https" or not parsed.hostname
        or parsed.username or parsed.password or parsed.fragment
    ):
        raise FeedError(f"{label} must be credential-free HTTPS")
    return value


def _download(
    url: str,
    *,
    limit: int,
    accept: str,
    opener: Callable[..., Any],
) -> bytes:
    _url(url, "Catalog feed URL")
    request = Request(url, headers={
        "Accept": accept,
        "Accept-Encoding": "identity",
        "User-Agent": "DSH-Forge-catalog-feed/1",
    })
    try:
        with opener(request, timeout=60) as response:
            _url(response.geturl(), "Catalog feed redirect")
            declared = response.headers.get("Content-Length")
            if declared:
                try:
                    size = int(declared)
                except ValueError:
                    raise FeedError("Catalog feed returned an invalid Content-Length") from None
                if not 0 <= size <= limit:
                    raise FeedError("Catalog feed response exceeds the byte limit")
            payload = response.read(limit + 1)
    except FeedError:
        raise
    except OSError as error:
        raise FeedError(f"Catalog feed request failed: {error}") from error
    if len(payload) > limit:
        raise FeedError("Catalog feed response exceeds the byte limit")
    return payload


def _json(payload: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in values:
            if key in result:
                raise FeedError(f"{label} contains a duplicate JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FeedError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise FeedError(f"{label} must be a JSON object")
    return value


def _asset(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "url", "media_type", "compression", "compressed_bytes", "uncompressed_bytes",
        "compressed_sha256", "uncompressed_sha256",
    }:
        raise FeedError(f"Catalog feed {name} asset fields are invalid")
    result = dict(value)
    _url(result["url"], f"Catalog feed {name} asset URL")
    if result["media_type"] != "application/json" or result["compression"] != "gzip":
        raise FeedError(f"Catalog feed {name} asset encoding is unsupported")
    for field, maximum in (("compressed_bytes", MAX_COMPRESSED_BYTES), ("uncompressed_bytes", MAX_SNAPSHOT_BYTES)):
        size = result[field]
        if not isinstance(size, int) or isinstance(size, bool) or not 1 <= size <= maximum:
            raise FeedError(f"Catalog feed {name} {field} is invalid")
    for field in ("compressed_sha256", "uncompressed_sha256"):
        digest = result[field]
        if not isinstance(digest, str) or len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise FeedError(f"Catalog feed {name} {field} is invalid")
    return result


def validate_feed(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != {
        "schema", "snapshot_id", "published_at", "source_repository", "assets",
        "counts", "coverage", "claims",
    }:
        raise FeedError("Catalog feed fields are invalid")
    if value.get("schema") != REGISTRY_FEED_SCHEMA:
        raise FeedError("Catalog feed schema is unsupported")
    for field, maximum in (("snapshot_id", 256), ("published_at", 64)):
        text = value.get(field)
        if not isinstance(text, str) or not text or len(text) > maximum:
            raise FeedError(f"Catalog feed {field} is invalid")
    if value.get("source_repository") != "MichaelTheMay/dsh-forge":
        raise FeedError("Catalog feed publisher is unsupported")
    assets = value.get("assets")
    if not isinstance(assets, Mapping) or set(assets) != {"registry", "hidden_gems"}:
        raise FeedError("Catalog feed assets are invalid")
    counts = value.get("counts")
    if not isinstance(counts, Mapping) or set(counts) != {"plugins", "forks", "packages", "candidates"} or any(
        not isinstance(item, int) or isinstance(item, bool) or item < 0 for item in counts.values()
    ):
        raise FeedError("Catalog feed counts are invalid")
    claims = value.get("claims")
    if claims != {"signed": False, "metadata_only": True, "executed": False, "security_verified": False}:
        raise FeedError("Catalog feed trust claims are invalid")
    if not isinstance(value.get("coverage"), list) or len(value["coverage"]) > 32:
        raise FeedError("Catalog feed coverage is invalid")
    return {
        **dict(value),
        "assets": {name: _asset(assets[name], name) for name in ("registry", "hidden_gems")},
        "counts": dict(counts),
        "claims": dict(claims),
    }


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _descriptor(data: bytes, compressed: bytes, url: str) -> dict[str, Any]:
    return {
        "url": url,
        "media_type": "application/json",
        "compression": "gzip",
        "compressed_bytes": len(compressed),
        "uncompressed_bytes": len(data),
        "compressed_sha256": _digest(compressed),
        "uncompressed_sha256": _digest(data),
    }


def build_feed_assets(
    registry_path: str | Path,
    queue_path: str | Path,
    output_directory: str | Path,
    *,
    base_url: str,
    force: bool = False,
) -> dict[str, Any]:
    """Create deterministic gzip assets and their public integrity index."""

    base_url = _url(base_url, "Catalog feed base URL").rstrip("/")
    registry_path = Path(registry_path).expanduser()
    queue_path = Path(queue_path).expanduser()
    registry = read_json(registry_path, max_bytes=MAX_SNAPSHOT_BYTES)
    queue = read_json(queue_path, max_bytes=MAX_SNAPSHOT_BYTES)
    if queue.get("snapshot_id") != registry.get("snapshot_id"):
        raise FeedError("Registry and hidden-gem queue snapshot IDs differ")
    registry_bytes = registry_path.read_bytes()
    queue_bytes = queue_path.read_bytes()
    registry_gzip = gzip.compress(registry_bytes, compresslevel=9, mtime=0)
    queue_gzip = gzip.compress(queue_bytes, compresslevel=9, mtime=0)
    output = Path(output_directory).expanduser()
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "registry": output / "registry.json.gz",
        "hidden_gems": output / "hidden-gems.json.gz",
        "feed": output / "registry-feed.json",
    }
    if not force and any(path.exists() for path in paths.values()):
        raise FeedError("Catalog feed output exists; pass --force")
    paths["registry"].write_bytes(registry_gzip)
    paths["hidden_gems"].write_bytes(queue_gzip)
    entries = [*(registry.get("entries") or []), *(registry.get("supplemental_entries") or [])]
    feed = validate_feed({
        "schema": REGISTRY_FEED_SCHEMA,
        "snapshot_id": str(registry.get("snapshot_id") or ""),
        "published_at": str(registry.get("completed_at") or registry.get("fetched_at") or ""),
        "source_repository": "MichaelTheMay/dsh-forge",
        "assets": {
            "registry": _descriptor(registry_bytes, registry_gzip, base_url + "/registry.json.gz"),
            "hidden_gems": _descriptor(queue_bytes, queue_gzip, base_url + "/hidden-gems.json.gz"),
        },
        "counts": {
            "plugins": sum(item.get("artifact_type") == "plugin" for item in entries if isinstance(item, Mapping)),
            "forks": sum(item.get("artifact_type") == "fork" for item in entries if isinstance(item, Mapping)),
            "packages": len(registry.get("package_entries") or []),
            "candidates": int(queue.get("candidate_count") or 0),
        },
        "coverage": list(registry.get("coverage") or []),
        "claims": {"signed": False, "metadata_only": True, "executed": False, "security_verified": False},
    })
    write_json(paths["feed"], feed, force=force, compact=True)
    return {"feed": feed, "paths": {name: str(path) for name, path in paths.items()}}


def fetch_catalog_feed(
    url: str = DEFAULT_FEED_URL,
    *,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Download the current registry only after gzip and both hashes verify."""

    feed = validate_feed(_json(_download(
        url, limit=MAX_FEED_BYTES, accept="application/json", opener=opener,
    ), "Catalog feed"))
    asset = feed["assets"]["registry"]
    compressed = _download(
        asset["url"], limit=asset["compressed_bytes"], accept="application/gzip", opener=opener,
    )
    if len(compressed) != asset["compressed_bytes"] or _digest(compressed) != asset["compressed_sha256"]:
        raise FeedError("Catalog registry compressed checksum does not match")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as archive:
            payload = archive.read(asset["uncompressed_bytes"] + 1)
    except (OSError, EOFError) as error:
        raise FeedError("Catalog registry is not valid gzip") from error
    if len(payload) != asset["uncompressed_bytes"] or _digest(payload) != asset["uncompressed_sha256"]:
        raise FeedError("Catalog registry expanded checksum does not match")
    registry = _json(payload, "Catalog registry")
    if registry.get("snapshot_id") != feed["snapshot_id"]:
        raise FeedError("Catalog registry snapshot does not match its feed")
    provenance = dict(registry.get("provenance") or {})
    provenance["feed"] = {
        "url": url,
        "schema": feed["schema"],
        "published_at": feed["published_at"],
        "compressed_sha256": asset["compressed_sha256"],
        "signature_status": "unsigned_checksum_verified",
    }
    registry["provenance"] = provenance
    return registry
