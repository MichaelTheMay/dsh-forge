# Local catalog store

The browser's embedded snapshot and the local catalog store are two different
corpora with two different jobs.

The **embedded snapshot** in `web/launcher.js` stays exactly as it is. It is
what `scripts/package_preview.py` turns into a single self-contained HTML file,
so it has to stay small and inline. It remains the corpus whenever no sidecar
is connected.

The **catalog store** is an FTS5-indexed SQLite database built from an imported
snapshot. It is what a connected sidecar reads, and it is the only path that
scales to the real fork network. The upstream fork endpoint captured in the seed
reports roughly 24,000 forks; ten of them are embedded today.

This mirrors the launcher's existing rule that live sidecar data replaces
preview inventory rather than merging with it.

## Importing

```bash
python3 -m dsh_forge catalog import data/public-repos.seed.json \
  --package-feed data/package-catalog.seed.json
python3 -m dsh_forge catalog status
```

Import is offline and inert. It parses metadata, writes rows, and builds a text
index. It never fetches, unpacks, or executes anything.

Import **never upgrades trust**. Whatever `provenance` the snapshot recorded is
stored verbatim and repeated in every search response, so an
`unsigned_development_seed` stays visibly unsigned all the way to the UI.
Verifying signed catalog updates is a separate boundary that does not exist yet.

The store is built into a temporary file and then atomically replaced, so a
failed import leaves the previous store intact and never leaves a partial one
behind. Each build stamps a `generation`; re-importing invalidates outstanding
page cursors rather than silently renumbering results.

## Searching

```bash
python3 -m dsh_forge catalog search "agent teams" --limit 10
python3 -m dsh_forge catalog search --type fork --sort stars --limit 25
python3 -m dsh_forge catalog search --type plugin --featured
```

A connected sidecar exposes the same query:

```
GET /api/v1/catalog/search?q=&type=&sort=&limit=&cursor=&featured=&licensed=&archived=
```

It requires the same loopback host and launcher session cookie as every other
API read.

- **Sorts**: `relevance` (BM25, falls back to `rank` when there is no query),
  `rank`, `stars`, `recent`, `name`. Every sort is total, so paging is stable.
- **Filters**: artifact type, administrator-curated only, reports a license,
  exclude archived. `repository` rows are shown under the plugin browser.
- **Free text** is matched literally. Every token is quoted before it reaches
  FTS5, so a scoped npm name like `@scope/plugin` matches the package that
  declares it, and FTS5 operator syntax a user types (`NEAR(`, `OR`, `*`) is
  treated as text rather than query structure. A query of pure punctuation
  browses instead of matching nothing.
- **Records are returned verbatim.** The store hands back the same record the
  snapshot contained, so the browser applies one mapping for both the embedded
  and the imported path.

## Bounds

Everything is bounded so a large corpus cannot turn into a large response:

| Bound | Value |
| ----- | ----- |
| Page size | 100 records |
| Query length | 200 characters |
| Query terms | 12 |
| Paging depth | 10,000 results |

Deep paging stops rather than letting a caller walk the whole corpus one page at
a time; narrow the query instead. At 24,000 records the store builds in well
under a second, occupies roughly 27 MB, and answers text queries in tens of
milliseconds.

## Concurrency

The sidecar serves requests on a thread pool, and SQLite connections are
thread-affine, so each thread reads through its own read-only connection.
Connections are tracked so shutdown can release all of them — on Windows an
unreleased handle would block the atomic replace that a re-import performs.
