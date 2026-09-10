"""Local catalog store: a bounded SQLite mirror of an imported catalog snapshot.

The embedded snapshot in `web/launcher.js` stays the corpus for the
disconnected preview, which must remain a single self-contained file. It cannot
grow to the size of the real fork network, so a connected sidecar reads from
this store instead: an FTS5-indexed SQLite database built from a validated
snapshot.

Importing is offline and inert. It parses metadata, writes rows, and builds a
text index. It never fetches, unpacks, or executes anything, and it never
upgrades an unsigned development snapshot into a verified one — the recorded
provenance is carried through to every reader verbatim.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import time
from typing import Any, Iterable, Iterator, Mapping, Sequence

from .packages import PackageError, sign_payload, verify_signed_payload


STORE_SCHEMA_VERSION = 1
CATALOG_STORE_SCHEMA = "dsh-forge.catalog-store/v1"

MAX_QUERY_LENGTH = 200
MAX_QUERY_TERMS = 12
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50
# Offset paging is stable because a store generation is immutable, but it stays
# bounded so a caller cannot walk the whole corpus one deep page at a time.
MAX_OFFSET = 10_000

ARTIFACT_TYPES = ("package", "plugin", "fork")
SORTS = ("relevance", "rank", "stars", "recent", "name")

_TOKEN = re.compile(r"[0-9A-Za-z@._/+-]+")
_SORT_COLUMNS = {
    "rank": "rank_value ASC, stars DESC, artifact_id ASC",
    "stars": "stars DESC, rank_value ASC, artifact_id ASC",
    "recent": "pushed_at DESC, artifact_id ASC",
    "name": "name_key ASC, artifact_id ASC",
}


class CatalogStoreError(RuntimeError):
    """The catalog store is missing, stale, or was asked for something invalid."""


CATALOG_PAYLOAD_TYPE = "application/vnd.dsh-forge.catalog-snapshot.v1+json"
# A catalog snapshot is orders of magnitude larger than a package manifest.
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024


def _canonical_snapshot_value(value: Any, label: str = "snapshot") -> None:
    """Reject anything without exactly one JSON spelling.

    The package profile forbids numbers outright, but a catalog is full of star
    counts and ranks. Integers have a single representation, so they are
    allowed; floats are not, because their spelling varies between writers.
    """
    if value is None or isinstance(value, (bool, str)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _canonical_snapshot_value(item, f"{label}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key.isascii():
                raise CatalogStoreError(f"{label} object keys must be ASCII strings")
            _canonical_snapshot_value(item, f"{label}.{key}")
        return
    raise CatalogStoreError(f"{label} contains a float or unsupported JSON value")


def canonical_snapshot_bytes(snapshot: Mapping[str, Any]) -> bytes:
    """Deterministic bytes for a catalog snapshot payload."""
    if not isinstance(snapshot, Mapping):
        raise CatalogStoreError("A catalog snapshot must be a JSON object")
    _canonical_snapshot_value(dict(snapshot))
    encoded = json.dumps(dict(snapshot), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise CatalogStoreError("Catalog snapshot exceeds the signing size limit")
    return encoded


def sign_snapshot(snapshot: Mapping[str, Any], private_key: str | Path) -> dict[str, Any]:
    """Wrap a catalog snapshot in a signed DSSE envelope."""
    try:
        return sign_payload(
            canonical_snapshot_bytes(snapshot), private_key, payload_type=CATALOG_PAYLOAD_TYPE
        )
    except PackageError as error:
        raise CatalogStoreError(f"Could not sign the catalog snapshot: {error}") from error


def verify_snapshot(
    envelope: Mapping[str, Any],
    trust_root: Mapping[str, Any],
    *,
    now: Any = None,
) -> dict[str, Any]:
    """Verify a signed catalog snapshot and return it with its signer evidence.

    Verification is the only thing that may raise the recorded trust of an
    imported catalog above 'unsigned'.
    """
    try:
        verified = verify_signed_payload(
            dict(envelope), dict(trust_root),
            payload_type=CATALOG_PAYLOAD_TYPE,
            max_payload_bytes=MAX_SNAPSHOT_BYTES,
            now=now,
        )
    except PackageError as error:
        raise CatalogStoreError(f"Catalog snapshot signature rejected: {error}") from error
    payload = verified["payload"]
    try:
        snapshot = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CatalogStoreError(f"Signed catalog payload is invalid UTF-8 JSON: {error}") from error
    if not isinstance(snapshot, dict):
        raise CatalogStoreError("Signed catalog payload must be a JSON object")
    if canonical_snapshot_bytes(snapshot) != payload:
        raise CatalogStoreError("Signed catalog payload is not canonical")
    return {
        "snapshot": snapshot,
        "signature": {
            "verified": True,
            "payload_type": CATALOG_PAYLOAD_TYPE,
            "valid_signers": verified["valid_signers"],
            "threshold": verified["threshold"],
            "payload_digest": verified["payload_digest"],
        },
    }


def _text(value: Any, limit: int = 4096) -> str:
    return value[:limit] if isinstance(value, str) else ""


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _terms(values: Iterable[Any]) -> str:
    """Flatten searchable labels into one bounded text column."""
    seen: list[str] = []
    for value in values:
        text = _text(value, 256).strip()
        if text and text not in seen:
            seen.append(text)
        if len(seen) >= 64:
            break
    return " ".join(seen)


def _rows_from_snapshot(snapshot: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield storable rows for forks, plugins, and packages in one shape."""
    for entry in list(snapshot.get("entries") or []) + list(snapshot.get("supplemental_entries") or []):
        if not isinstance(entry, dict):
            continue
        identity = _text(entry.get("artifact_id"), 256)
        kind = _text(entry.get("artifact_type"), 32)
        if not identity or kind not in {"fork", "plugin", "repository"}:
            continue
        curation = entry.get("curation") if isinstance(entry.get("curation"), dict) else {}
        package = entry.get("package") if isinstance(entry.get("package"), dict) else {}
        license_value = entry.get("license") if isinstance(entry.get("license"), dict) else {}
        rank = _integer(entry.get("seed_rank")) or _integer(curation.get("rank"))
        yield {
            "artifact_id": identity,
            "type": kind,
            "slug": _text(entry.get("full_name"), 512),
            "name": _text(entry.get("name"), 256),
            "owner": _text(entry.get("owner"), 256),
            "description": _text(entry.get("description"), 2048),
            "language": _text(entry.get("language"), 128),
            "license": _text(license_value.get("spdx"), 128),
            "stars": _integer(entry.get("github_stars")),
            "pushed_at": _text(entry.get("pushed_at"), 64),
            "archived": 1 if entry.get("archived") else 0,
            "rank_value": rank if rank is not None else 9999,
            "featured": 1 if (kind == "plugin" and isinstance(rank, int) and rank <= 3) or (rank == 1) else 0,
            "risk": _text(curation.get("security_risk"), 32),
            "terms": _terms([
                entry.get("name"), entry.get("owner"), entry.get("full_name"),
                *(entry.get("topics") or []),
                *(curation.get("taxonomy") or []),
                package.get("name"), package.get("version"), package.get("registry"),
            ]),
            "record": entry,
        }

    for entry in list(snapshot.get("package_entries") or []):
        if not isinstance(entry, dict):
            continue
        identity = _text(entry.get("id"), 256)
        if not identity:
            continue
        publisher = entry.get("publisher") if isinstance(entry.get("publisher"), dict) else {}
        license_value = entry.get("license") if isinstance(entry.get("license"), dict) else {}
        risk = entry.get("risk") if isinstance(entry.get("risk"), dict) else {}
        components = entry.get("components") if isinstance(entry.get("components"), list) else []
        component_terms: list[Any] = []
        for component in components[:32]:
            if not isinstance(component, dict):
                continue
            package = component.get("package") if isinstance(component.get("package"), dict) else {}
            repository = component.get("repository") if isinstance(component.get("repository"), dict) else {}
            component_terms.extend([package.get("name"), package.get("version"), repository.get("full_name")])
        rank = _integer(entry.get("rank"))
        yield {
            "artifact_id": identity,
            "type": "package",
            "slug": _text(entry.get("slug"), 512),
            "name": _text(entry.get("slug"), 256),
            "owner": _text(publisher.get("name"), 256),
            "description": _text(entry.get("summary"), 2048),
            "language": "",
            "license": " + ".join(_text(item, 64) for item in (license_value.get("expressions") or [])[:8]),
            "stars": None,
            "pushed_at": _text(entry.get("updated_at"), 64),
            "archived": 0,
            "rank_value": rank if rank is not None else 9999,
            "featured": 1 if entry.get("featured") else 0,
            "risk": _text(risk.get("level"), 32),
            "terms": _terms([
                entry.get("slug"), publisher.get("name"),
                *(entry.get("taxonomy") or []),
                *component_terms,
            ]),
            "record": entry,
        }


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE artifacts (
            rowid       INTEGER PRIMARY KEY,
            artifact_id TEXT NOT NULL UNIQUE,
            type        TEXT NOT NULL,
            slug        TEXT NOT NULL,
            name        TEXT NOT NULL,
            name_key    TEXT NOT NULL,
            owner       TEXT NOT NULL,
            description TEXT NOT NULL,
            language    TEXT NOT NULL,
            license     TEXT NOT NULL,
            stars       INTEGER,
            pushed_at   TEXT NOT NULL,
            archived    INTEGER NOT NULL,
            rank_value  INTEGER NOT NULL,
            featured    INTEGER NOT NULL,
            risk        TEXT NOT NULL,
            terms       TEXT NOT NULL,
            record      TEXT NOT NULL
        );
        CREATE INDEX artifacts_rank ON artifacts (rank_value, stars DESC, artifact_id);
        CREATE INDEX artifacts_stars ON artifacts (stars DESC, rank_value, artifact_id);
        CREATE INDEX artifacts_recent ON artifacts (pushed_at DESC, artifact_id);
        CREATE INDEX artifacts_name ON artifacts (name_key, artifact_id);
        CREATE INDEX artifacts_type ON artifacts (type);
        CREATE VIRTUAL TABLE artifacts_fts USING fts5(
            name, owner, description, terms,
            content='artifacts', content_rowid='rowid',
            tokenize='unicode61 remove_diacritics 2'
        );
        """
    )


def build(
    destination: str | Path,
    snapshot: Mapping[str, Any],
    *,
    provenance: Mapping[str, Any] | None = None,
    signature: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a fresh store from a snapshot and atomically replace any existing one."""
    destination = Path(destination).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".catalog-", suffix=".sqlite3", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    # mkstemp created the file; SQLite needs to initialize it itself.
    temporary.unlink()

    generation = int(time.time() * 1000)
    counts: dict[str, int] = {kind: 0 for kind in ARTIFACT_TYPES}
    try:
        connection = _connect(temporary)
        try:
            with connection:
                _create_schema(connection)
                rows = 0
                for row in _rows_from_snapshot(snapshot):
                    kind = "plugin" if row["type"] == "repository" else row["type"]
                    counts[kind] = counts.get(kind, 0) + 1
                    rows += 1
                    connection.execute(
                        """
                        INSERT OR REPLACE INTO artifacts (
                            artifact_id, type, slug, name, name_key, owner, description, language,
                            license, stars, pushed_at, archived, rank_value, featured, risk, terms, record
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            row["artifact_id"], row["type"], row["slug"], row["name"], row["name"].casefold(),
                            row["owner"], row["description"], row["language"], row["license"], row["stars"],
                            row["pushed_at"], row["archived"], row["rank_value"], row["featured"], row["risk"],
                            row["terms"], json.dumps(row["record"], separators=(",", ":")),
                        ),
                    )
                connection.execute(
                    "INSERT INTO artifacts_fts(artifacts_fts) VALUES ('rebuild')"
                )
                recorded = {
                    "schema": CATALOG_STORE_SCHEMA,
                    "schema_version": str(STORE_SCHEMA_VERSION),
                    "generation": str(generation),
                    "artifact_count": str(rows),
                    "counts": json.dumps(counts, sort_keys=True),
                    "snapshot_id": _text(snapshot.get("snapshot_id"), 256),
                    "fetched_at": _text(snapshot.get("fetched_at"), 64),
                    # Carried through verbatim; importing never upgrades trust.
                    "provenance": json.dumps(provenance or snapshot.get("provenance") or {}, sort_keys=True),
                    # Only a verified envelope may record a signature here.
                    "signature": json.dumps(dict(signature) if signature else {"verified": False}, sort_keys=True),
                }
                connection.executemany(
                    "INSERT INTO meta (key, value) VALUES (?, ?)", sorted(recorded.items())
                )
        finally:
            connection.close()
        os.replace(temporary, destination)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return {"path": str(destination), "generation": generation, "artifact_count": sum(counts.values()), "counts": counts}


def _match_expression(query: str) -> str | None:
    """Turn free text into a bounded, quoted FTS5 expression.

    Every token is quoted, so punctuation a user types (`@scope/name`, `-`, `*`)
    is matched literally instead of being read as FTS5 query syntax.
    """
    # A token of pure punctuation ("@@@", "///") is an empty term to the
    # unicode61 tokenizer, so drop it here and let the query fall back to
    # browsing rather than matching nothing.
    tokens = [token for token in _TOKEN.findall(query or "") if any(c.isalnum() for c in token)]
    tokens = tokens[:MAX_QUERY_TERMS]
    if not tokens:
        return None
    quoted = ['"' + token.replace('"', '""') + '"' for token in tokens]
    # Trailing prefix match keeps type-ahead responsive without a second index.
    quoted[-1] = quoted[-1] + " *"
    return " AND ".join(quoted)


class CatalogStore:
    """Read-only accessor for a built catalog store."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        # The sidecar serves requests on a thread pool and SQLite connections are
        # thread-affine, so each thread reads through its own connection. They are
        # read-only, so concurrent readers need no serialization. Every connection
        # is also tracked, because close() must release all of them before an
        # import can atomically replace the file on Windows.
        self._local = threading.local()
        self._connections: list[sqlite3.Connection] = []
        self._connections_lock = threading.Lock()

    @property
    def available(self) -> bool:
        return self.path.is_file()

    def _open(self) -> sqlite3.Connection:
        existing = getattr(self._local, "connection", None)
        if existing is not None:
            return existing
        if not self.available:
            raise CatalogStoreError("No catalog store is imported yet")
        try:
            # check_same_thread=False lets shutdown close a connection that a
            # server thread opened. Each connection is still used by exactly one
            # thread, so no cross-thread serialization is needed for reads.
            connection = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True, check_same_thread=False)
        except sqlite3.Error as error:
            raise CatalogStoreError(f"Could not open the catalog store: {error}") from error
        connection.row_factory = sqlite3.Row
        try:
            version = connection.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        except sqlite3.Error as error:
            connection.close()
            raise CatalogStoreError(f"The catalog store is unreadable: {error}") from error
        if not version or version["value"] != str(STORE_SCHEMA_VERSION):
            connection.close()
            raise CatalogStoreError("The catalog store was built by a different schema version; re-import it")
        self._local.connection = connection
        with self._connections_lock:
            self._connections.append(connection)
        return connection

    def close(self) -> None:
        """Close every thread's connection so the file can be replaced."""
        with self._connections_lock:
            connections, self._connections = self._connections, []
        for connection in connections:
            try:
                connection.close()
            except sqlite3.Error:
                pass
        self._local = threading.local()

    def meta(self) -> dict[str, Any]:
        connection = self._open()
        rows = connection.execute("SELECT key, value FROM meta").fetchall()
        values = {row["key"]: row["value"] for row in rows}
        return {
            "schema": values.get("schema", CATALOG_STORE_SCHEMA),
            "schema_version": int(values.get("schema_version", STORE_SCHEMA_VERSION)),
            "generation": int(values.get("generation", 0)),
            "artifact_count": int(values.get("artifact_count", 0)),
            "counts": json.loads(values.get("counts", "{}")),
            "snapshot_id": values.get("snapshot_id", ""),
            "fetched_at": values.get("fetched_at", ""),
            "provenance": json.loads(values.get("provenance", "{}")),
            "signature": json.loads(values.get("signature", '{"verified": false}')),
        }

    def status(self) -> dict[str, Any]:
        if not self.available:
            return {
                "available": False,
                "path": str(self.path),
                "reason": "No catalog store is imported yet; the embedded snapshot is being used.",
            }
        try:
            meta = self.meta()
        except CatalogStoreError as error:
            return {"available": False, "path": str(self.path), "reason": str(error)}
        return {"available": True, "path": str(self.path), **meta}

    def search(
        self,
        *,
        query: str = "",
        types: Sequence[str] = (),
        licensed_only: bool = False,
        include_archived: bool = True,
        featured_only: bool = False,
        sort: str = "relevance",
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str = "",
    ) -> dict[str, Any]:
        connection = self._open()
        meta = self.meta()

        query = (query or "").strip()[:MAX_QUERY_LENGTH]
        if sort not in SORTS:
            raise CatalogStoreError(f"Unsupported sort: {sort}")
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            raise CatalogStoreError("limit must be an integer") from None
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise CatalogStoreError(f"limit must be between 1 and {MAX_PAGE_SIZE}")

        offset = self._decode_cursor(cursor, meta["generation"])
        selected = [kind for kind in types if kind in ARTIFACT_TYPES]

        where: list[str] = []
        parameters: list[Any] = []
        match = _match_expression(query)
        if match:
            source = "artifacts JOIN artifacts_fts ON artifacts_fts.rowid = artifacts.rowid"
            where.append("artifacts_fts MATCH ?")
            parameters.append(match)
        else:
            source = "artifacts"
        if selected:
            # 'repository' rows are shown under the plugin browser.
            expanded = list(selected) + (["repository"] if "plugin" in selected else [])
            placeholders = ",".join("?" for _ in expanded)
            where.append(f"artifacts.type IN ({placeholders})")
            parameters.extend(expanded)
        if licensed_only:
            where.append("artifacts.license != ''")
        if not include_archived:
            where.append("artifacts.archived = 0")
        if featured_only:
            where.append("artifacts.featured = 1")
        clause = (" WHERE " + " AND ".join(where)) if where else ""

        if sort == "relevance" and match:
            order = "bm25(artifacts_fts), artifacts.rank_value ASC, artifacts.artifact_id ASC"
        else:
            column = _SORT_COLUMNS["rank" if sort == "relevance" else sort]
            order = ", ".join("artifacts." + part for part in column.split(", "))

        try:
            total = connection.execute(f"SELECT COUNT(*) AS n FROM {source}{clause}", parameters).fetchone()["n"]
            rows = connection.execute(
                f"SELECT artifacts.record FROM {source}{clause} ORDER BY {order} LIMIT ? OFFSET ?",
                [*parameters, limit + 1, offset],
            ).fetchall()
        except sqlite3.Error as error:
            raise CatalogStoreError(f"Catalog search failed: {error}") from error

        has_more = len(rows) > limit
        page = [json.loads(row["record"]) for row in rows[:limit]]
        next_offset = offset + limit
        return {
            "artifacts": page,
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": has_more and next_offset < MAX_OFFSET,
            "next_cursor": self._encode_cursor(meta["generation"], next_offset)
            if has_more and next_offset < MAX_OFFSET else "",
            "generation": meta["generation"],
            "snapshot_id": meta["snapshot_id"],
            "provenance": meta["provenance"],
            "signature": meta["signature"],
        }

    def get(self, artifact_id: str) -> dict[str, Any] | None:
        connection = self._open()
        row = connection.execute(
            "SELECT record FROM artifacts WHERE artifact_id = ?", (str(artifact_id or "")[:256],)
        ).fetchone()
        return json.loads(row["record"]) if row else None

    @staticmethod
    def _encode_cursor(generation: int, offset: int) -> str:
        return f"{generation}.{offset}"

    @staticmethod
    def _decode_cursor(cursor: str, generation: int) -> int:
        if not cursor:
            return 0
        match = re.fullmatch(r"(\d{1,20})\.(\d{1,9})", str(cursor))
        if not match:
            raise CatalogStoreError("Invalid catalog cursor")
        if int(match.group(1)) != generation:
            raise CatalogStoreError("The catalog was re-imported; restart the query from the first page")
        offset = int(match.group(2))
        if offset > MAX_OFFSET:
            raise CatalogStoreError(f"Catalog paging stops at {MAX_OFFSET} results; narrow the query instead")
        return offset
