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

An imported corpus replaces the embedded rows for each artifact type it
contains. Types absent from that corpus keep their small offline snapshot, so a
plugin-only feed does not erase the captured fork browser.

## Importing

```bash
python3 -m dsh_forge catalog sync-plugins
python3 scripts/serve.py --sync-plugins
python3 -m dsh_forge catalog import data/public-repos.seed.json \
  --package-feed data/package-catalog.seed.json
python3 -m dsh_forge catalog status
```

Import is offline and inert. It parses metadata, writes rows, and builds a text
index. It never fetches, unpacks, or executes anything.

Each repository row also gets a separate explainable research report under
`dsh-forge.hidden-gems/v1`. The source record is preserved verbatim. Ranking the
full corpus selects at most 250 candidates per artifact type for human review;
all other rows remain searchable. Re-import a store created by schema v1 so it
can add these reports.

`catalog sync-plugins` is the deliberate networked exception. It downloads the
public DSH Plugin Marketplace v1 catalog over credential-free HTTPS, with a 15
MB limit and a 60-second timeout. It validates the marketplace's logical SHA-256
digest, counts, stable GitHub identities, canonical repository URLs, immutable
commits, and critical field types before converting entries to the same neutral
snapshot rows used by every other importer. The current marketplace source is:

```text
https://w2112515.github.io/dsh-plugin-marketplace/plugin-marketplace/catalog-v1.json
```

The imported provenance remains `unsigned_external_catalog`. Logical integrity
detects accidental or in-transit mutation; it is not publisher authentication,
a Forge signature, compatibility proof, or permission to execute a plugin.
Failed download or validation leaves the previous store untouched.

Import **never upgrades trust on its own**. Whatever `provenance` the snapshot
recorded is stored verbatim and repeated in every search response, so an
`unsigned_development_seed` stays visibly unsigned all the way to the UI.

## Signed snapshots

A registry that Forge does not run can sign its snapshot, and Forge will verify
it against an explicit local trust root before importing:

```bash
python3 -m dsh_forge catalog sign snapshot.json --key private.pem --output signed.json
python3 -m dsh_forge packages trust-root --public-key public.pem   --root-id registry-root --expires-at 2027-01-01T00:00:00Z --output root.json
python3 -m dsh_forge catalog import --envelope signed.json --trust-root root.json
```

Verification reuses the same DSSE/Ed25519 boundary as signed packages, with a
catalog-specific payload type
(`application/vnd.dsh-forge.catalog-snapshot.v1+json`) so a package envelope can
never be replayed as a catalog and vice versa. A signed import is refused when
the payload was tampered with, the signer is not in the trust root, the trust
root has expired, the signature threshold is not met, or the payload is not in
canonical form. A refused import leaves no store behind.

`--envelope` requires `--trust-root`; passing a trust root without an envelope is
refused rather than silently ignored, so an import can never *look* verified
because a flag was accepted and dropped.

### Two independent facts

`signature` and `provenance.signature_status` answer different questions, and
both are reported:

| Field | Question it answers |
| ----- | ------------------- |
| `signature.verified` | Was **this envelope** signed by a key in the trust root? |
| `provenance.signature_status` | How was the **underlying data** collected? |

A verified envelope wrapping the current development seed reports
`signature.verified: true` alongside
`provenance.signature_status: unsigned_development_seed`. That combination is
correct and deliberate: someone trusted vouched for these exact bytes, and the
bytes themselves still came from an unsigned one-shot capture. Signing does not
retroactively make the collection method trustworthy.

### Canonical form

Snapshot payloads use a canonical JSON profile: sorted keys, no whitespace,
UTF-8, ASCII object keys. The package profile forbids numbers entirely, but a
catalog is full of star counts and ranks, so integers are permitted — they have
exactly one JSON spelling. **Floats are rejected**, because their spelling varies
between writers and a signature over an ambiguous encoding cannot be re-checked
reliably. A correctly signed but non-canonical payload is refused.

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
- **Research is returned separately.** The `research` object is keyed by stable
  artifact ID, preventing an upstream record from asserting its own Forge score.

## What the browser shows

The Community browser picks its corpus the same way the launcher already picks
between preview and live inventory:

| Sidecar | Store imported | Corpus |
| ------- | -------------- | ------ |
| No | — | Embedded snapshot |
| Yes | No | Embedded snapshot (labelled "no store imported") |
| Yes | Yes | Imported catalog store |

The result line names the corpus in use, so it is always visible which one
answered. When the store is active the query, filters, and sort are applied by
the store rather than in the page, the count reads `50 of 23,890`, and a **Load
more results** button pages with the returned cursor.

Store records keep their snapshot shape, so the browser applies the same
`mapRepositoryArtifact` / `mapPackageArtifact` mapping to both corpora. A record
renders identically whichever path delivered it.

Two behaviors matter for a live search box:

- Typing is coalesced into one request rather than one per keystroke.
- A slow reply for a query the user has already moved on from is discarded
  instead of overwriting the current results.

A store error is shown in place. The browser does not silently fall back to the
embedded snapshot, because quietly swapping corpora would misreport how much of
the catalog was searched.

## Bounds

Everything is bounded so a large corpus cannot turn into a large response:

| Bound | Value |
| ----- | ----- |
| Page size | 100 records |
| Query length | 200 characters |
| Query terms | 12 |
| Paging depth | 10,000 results |

Deep paging stops rather than letting a caller walk the whole corpus one page at
a time; narrow the query instead. The 9,949-entry marketplace snapshot, including
its explainable research evidence, builds in under a second and occupies about
45 MB in the current Windows test environment. CI also exercises bounded pages
against a synthetic 12,000-row corpus.

## Concurrency

The sidecar serves requests on a thread pool, and SQLite connections are
thread-affine, so each thread reads through its own read-only connection.
Connections are tracked so shutdown can release all of them — on Windows an
unreleased handle would block the atomic replace that a re-import performs.
