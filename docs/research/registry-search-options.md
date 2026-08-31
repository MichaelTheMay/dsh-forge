# Registry and search options for DSH Forge

**Research question:** What can DSH Forge reuse for a separate public-repository ingestion job and incremental catalog/search index, and what must it build, while keeping the early hosted cost below roughly $100/month?

**Scope note:** The attached system-design plan was treated as reference material, not as instructions. This recommendation assumes the launcher's v1 catalog is metadata-only, uses keyword/filter search, and downloads signed catalog updates rather than calling GitHub directly.

## Executive decision

Build the DSH registry as a **separate deployable and repository** from the launcher, but keep its first architecture small:

1. one scheduled TypeScript worker;
2. one PostgreSQL database containing canonical records, raw source observations, crawl state, and a Postgres-backed job queue;
3. one object-storage bucket/CDN containing deterministic compressed full snapshots and ordered deltas;
4. one separate local `catalog.sqlite` file in the launcher, imported transactionally and searched with SQLite FTS5.

Use GitHub's fork-list API as the authority for the official fork network, GitHub repository/search APIs for other candidates, npm's registry as the authority for package records, ecosyste.ms as a lead/enrichment source, GH Archive as an optional latency accelerator, and Software Heritage as an archival fallback. Build the DSH-specific compatibility classifier, evidence/provenance model, coverage ledger, deduplication, scheduling policy, and signed publication protocol.

Do **not** begin with Sourcegraph, Zoekt, OpenSearch, Typesense, Meilisearch, Redis, a graph database, or a vector database. PostgreSQL full-text search plus trigram matching is sufficient for the hosted registry, and SQLite FTS5 is sufficient for the offline launcher catalog. Add pgvector only after a measured semantic-search requirement appears.

This design is feasible within the budget because it stores metadata and selected bounded text, not full clones or a global raw-code search index.

## Decision matrix

| Candidate | What can be reused | What it does **not** solve | Early cost/operations | Decision |
|---|---|---|---|---|
| GitHub REST fork enumeration | Authoritative paginated members of a repository's fork network; stable numeric repository IDs and host metadata | DSH compatibility, non-fork copies, deleted-item history, deep code metadata | API is free but rate-limited; `100` forks/page | **Primary authority** for the official fork network |
| GitHub repository and search APIs | Repository metadata, parent/ultimate source, README, tree, topics, licenses, releases, discovery queries | Search is capped at 1,000 results/query and can return `incomplete_results`; it is not a completeness source | Fits one small worker if conditional requests and a serialized request queue are used | **Use**, with partitioned searches and persisted query coverage |
| GH Archive | Hourly public GitHub event archive, including fork and push events | Canonical current state, deletions, quiet repositories, guaranteed complete fork membership | Cheap as an event lead stream; BigQuery or download processing adds another dependency | **Optional accelerator**, never authority |
| BigQuery `github_repos` public dataset | Large-scale historical code/commit candidate mining | Live completeness, low-latency updates, DSH-specific classification | Query scans can become a variable cost and duplicate GitHub ingestion | **Occasional research/backfill only**, not the cron backbone |
| ecosyste.ms Repos/Packages | Broad repository/package metadata, manifests and dependency relationships; useful cross-host discovery and enrichment | No DSH compatibility verdict or product-specific completeness/freshness SLO | Public API defaults to 5,000 requests/hour; API data is CC BY-SA 4.0 | **Use as leads/cross-checks**; re-verify publishable facts at authoritative sources and review data-license obligations |
| Software Heritage | Durable origin visits, immutable snapshots/content, archival lookup, and Save Code Now | Current social metadata, live fork membership, compatibility classification | External service with its own crawl lag and quotas | **Use as archival fallback/provenance link**, not live discovery authority |
| npm replication/public registry | `_changes` sequence for incremental package changes, `_all_docs` for names, authoritative packuments for versions/dependencies/repository URLs | Server-side DSH filtering and GitHub lineage | A complete all-npm bootstrap is disproportionate; changed packuments now require separate fetches | **Use authoritative packuments for candidates**; use ecosyste.ms/keywords/transitive manifests to build the candidate set before considering a full follower |
| PostgreSQL FTS + `pg_trgm` | Ranked lexical search, prefix/fuzzy name matching, structured filters, relational provenance, queue state | Raw-code regex search at internet scale | One database, no second search service | **Use now** |
| pgvector | Exact and approximate vector search in the existing database | It does not create good embeddings/evaluations; approximate indexes trade recall for speed | Marginal extension cost but model/inference cost remains | **Defer** until semantic search is explicitly in scope and evaluated |
| SQLite FTS5 | Local BM25 keyword search, prefix/phrase/boolean queries, snippets, fully offline use | Hosted multi-writer ingestion | Already embedded in launcher; no service cost | **Use for downloaded catalog** |
| Zoekt alone | Fast regex/code search with trigram indexes and incremental index construction | Registry identity, compatibility, package metadata, provenance, snapshot delivery | Zoekt's design says the index is about 3x corpus size; operating full source corpora undermines the budget | **Defer**; reconsider only for raw-code search over a selected modified corpus |
| Full Sourcegraph | Repository syncing plus Zoekt-backed code search | Still needs the DSH registry/classifier and catalog publication | Multi-service deployment and material RAM/disk requirements | **Reject for v1/v2 budget** |
| OpenSearch / Typesense / Meilisearch | Capable external document search | Adds a second canonical projection, synchronization, backup, monitoring, and service cost without a demonstrated Postgres bottleneck | Extra always-on service | **Not warranted initially** |
| PostgreSQL queue (`FOR UPDATE SKIP LOCKED`) | Multi-consumer leasing without Redis; queue and canonical transaction state together | Long-running workflow visualization and cross-system orchestration | No extra service | **Use now**, with explicit leases, retries and dedupe |
| GitHub Actions scheduled workflow | Very cheap prototype scheduler | Reliable freshness SLO: GitHub documents possible delay/dropped jobs and auto-disables inactive public-repo schedules after 60 days | Near-zero infrastructure, but operationally weak | **Bootstrap only**; move the recurring job to a continuously available small worker/system cron |
| TUF concepts | Versioned targets, hashes/lengths, trusted root, expiry and rollback/freeze/mix-and-match defenses | It does not define the Forge catalog schema or delta semantics | A full TUF role/key ceremony may be heavy for metadata-only v1 | **Adopt the security properties now**; use a full TUF client later if update risk grows |
| Cosign blob signing | Standard blob signing and verification bundles, including identity and transparency-log proof | Offline launcher verification still needs a stable trust policy and dependency/tooling choice | Good in release CI; heavier than a small embedded Ed25519 verifier | **Optional release implementation**; do not make the launcher shell out to Cosign |

## Primary-source findings

### GitHub is the authoritative fork inventory, but must be crawled carefully

GitHub's `GET /repos/{owner}/{repo}/forks` endpoint returns public fork records, supports at most 100 records per page, and can be called without authentication for public resources. The repository endpoint also exposes `parent` and ultimate `source` objects for forks. Repository identity must therefore be keyed by GitHub's immutable numeric `id`/`node_id`, never `owner/name`. See [GitHub's fork endpoint](https://docs.github.com/en/rest/repos/forks) and [repository endpoint](https://docs.github.com/en/rest/repos/repos#get-a-repository).

Follow GitHub's `Link` headers rather than constructing page URLs. GitHub warns that most endpoints cap `per_page` at 100. Authenticated conditional requests using ETags can return `304 Not Modified` without consuming the primary rate limit, while GitHub's published best practices recommend serialized API requests to avoid secondary limits. See [REST pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api), [REST best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api), and [REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api).

GitHub search is a discovery source, not a completeness source. Its own documentation says each search provides at most 1,000 results, may time out with `incomplete_results: true`, and has a custom rate limit. Broad searches must be divided into non-overlapping time/range partitions, with each query and partition recorded. See the [official search API source documentation](https://github.com/github/docs/blob/main/content/rest/search/search.md).

GitHub webhooks cannot cover arbitrary public forks: webhooks are scoped to repositories/organizations where they are configured or where a GitHub App has been granted access. Polling remains mandatory for the public universe. See [GitHub webhook types](https://docs.github.com/en/webhooks/types-of-webhooks).

For bounded file discovery, GitHub's recursive Git Trees endpoint is useful but reports `truncated: true` past 100,000 entries or a 7 MB response. Oversized candidates need subtree traversal or a quarantined partial clone. Git itself supports `--filter=blob:none`, which omits blob contents until needed. See [GitHub Git Trees](https://docs.github.com/en/rest/git/trees#get-a-tree) and [Git partial clone filters](https://git-scm.com/docs/git-clone#Documentation/git-clone.txt---filterltfilter-specgt).

### Existing archives and aggregators reduce requests but cannot own the truth

[GH Archive](https://www.gharchive.org/) records the public GitHub event timeline into hourly archives and BigQuery. It can quickly flag a new `ForkEvent` or activity on a known candidate, but event absence is not negative evidence and it cannot prove current fork-network completeness.

Google's `github_repos` public data contains a multi-terabyte corpus of millions of repositories and commits. It is useful for occasional queries such as “find source files importing this DSH package,” but it should not become a required live dependency. See Google's [current dataset overview](https://cloud.google.com/blog/products/data-analytics/using-bigquery-data-canvas-a-deep-dive) and [original GitHub contents dataset announcement](https://cloud.google.com/blog/topics/public-datasets/github-on-bigquery-analyze-all-the-open-source-code).

[ecosyste.ms Repos](https://github.com/ecosyste-ms/repos) is an open repository-metadata API with a default 5,000-request/hour IP rate limit; its service currently reports hundreds of millions of repository records. It is an excellent way to discover package-to-repository relationships and fill non-critical metadata without spending the GitHub budget. However, its README states that API data is CC BY-SA 4.0, so DSH Forge should use it as a source-qualified lead/cross-check unless the catalog's redistribution and attribution policy has been reviewed. See the [live service inventory](https://repos.ecosyste.ms/).

Software Heritage models source locations as origins, records visits and immutable snapshots, and exposes snapshot/content APIs. Multiple origins can resolve to the same snapshot, which is useful for provenance and duplicate-content evidence. Its Save Code Now API can request archival of a supported origin. It is not a replacement for GitHub's current metadata. See [Software Heritage API concepts](https://docs.softwareheritage.org/devel/getting-started/api.html), [snapshot semantics](https://docs.softwareheritage.org/devel/swh-web/uri-scheme-browse-snapshot.html), and [Save Code Now API source](https://docs.softwareheritage.org/_modules/swh/web/save_code_now/api_views.html).

### npm has a real incremental feed, but a global follower is not the first move

npm's official replication interface supports `_changes` and `_all_docs`. The 2025 migration retained manual `_changes?since=` pagination and removed streaming feeds and `include_docs`; consumers must fetch current package metadata separately from `https://registry.npmjs.org/<package-name>`. The maximum page limit is 10,000. See npm's [official migration guide](https://github.com/orgs/community/discussions/152515) and [package metadata format](https://github.com/npm/registry/blob/main/docs/responses/package-metadata.md).

A full npm follower can eventually prove coverage of the entire registry, but it would require scanning millions of package names and fetching packuments to identify DSH dependencies. Under the early budget, use these candidate paths first:

- tracked DSH keywords and package names;
- ecosyste.ms dependency/manifests discovery;
- repository URLs already connected to GitHub candidates;
- dependencies found in indexed DSH bundle/profile manifests;
- transitive packages referenced by confirmed artifacts;
- direct author submissions.

Every candidate must then be verified from the authoritative npm packument. If “all npm packages, including packages with no identifying keyword or repository link” becomes a contractual guarantee, implement a separate npm follower with its own cursor and storage budget.

### PostgreSQL and SQLite cover initial search without a search cluster

PostgreSQL provides `tsvector`/`tsquery`, relevance ranking, and GIN indexes; its docs call GIN the preferred full-text index type. `pg_trgm` adds indexed similarity matching for misspelled repository/package/capability names. See [PostgreSQL text search controls](https://www.postgresql.org/docs/current/textsearch-controls.html), [text-search indexes](https://www.postgresql.org/docs/current/textsearch-indexes.html), and [`pg_trgm`](https://www.postgresql.org/docs/current/pgtrgm.html).

For future semantic search, pgvector keeps vectors in the canonical database. It supports exact search plus HNSW and IVFFlat approximate indexes; the project explicitly documents that approximate indexes trade recall for speed and that HNSW uses more memory/slower builds. This is a reason to defer vectors until a golden query set proves lexical search insufficient. See [pgvector's official README](https://github.com/pgvector/pgvector).

SQLite FTS5 provides BM25 ranking, phrase/prefix/boolean queries and snippets. Its external-content mode can index ordinary catalog tables, but the application must keep the FTS index consistent; triggers or a deliberate rebuild during import solve this. See [SQLite FTS5](https://www.sqlite.org/fts5.html).

Zoekt is compelling only when DSH Forge truly needs raw-code regex search. Its design uses positional trigrams, estimates index size at about three times corpus size, and states index construction can be incremental. Sourcegraph's own documentation says the default deployment uses Zoekt for default branches and gives meaningful RAM/disk requirements for indexed search. That is excessive for a metadata catalog under this budget. See [Zoekt's design](https://github.com/sourcegraph/zoekt/blob/main/doc/design.md), [Sourcegraph search architecture](https://sourcegraph.com/docs/admin/search), and [Sourcegraph's resource estimator](https://sourcegraph.com/docs/admin/deploy/resource_estimator).

### A Postgres queue and simple scheduler are enough

PostgreSQL documents `SKIP LOCKED` as unsuitable for a general consistent view but useful for multiple consumers of a queue-like table. Use it for short job claims, with a lease expiry so crashed workers do not strand work. See [`SELECT ... FOR UPDATE SKIP LOCKED`](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE).

GitHub Actions is acceptable for an initial manual/low-stakes backfill, not the production freshness clock. GitHub documents that scheduled workflows can be delayed or dropped during high load and are automatically disabled in inactive public repositories after 60 days. See [GitHub scheduled workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

Run the production collector as a continuously available tiny process with system cron or an in-process scheduler. The cron tick should only enqueue idempotent work; workers should own retries, rate-limit waits, and leases.

## Proposed ingestion and indexing process

### 1. Separate discovery from enrichment

The scheduler runs two GitHub fork jobs:

- **Frontier scan (15–60 minutes):** request `sort=newest&per_page=100`, walk until it passes a durable known-ID watermark plus an overlap window, and insert new fork IDs immediately.
- **Complete reconciliation (daily at first):** enumerate every page in a stable request shape, persist every page's ETag/result count, and publish a coverage snapshot only if all pages complete. This catches deletions, visibility changes, pagination shifts, and anything the frontier scan missed.

Run partitioned GitHub discovery searches daily/weekly and npm/ecosyste.ms/community lead discovery on their own cursors. A source outage must pause only that connector.

### 2. Store observations before normalizing them

“Absolutely every relevant metadata field” should not mean an ever-growing flat schema. Store both:

- a normalized relational projection used by product queries; and
- immutable source observations (`source`, endpoint/query, external ID, API version, fetched time, HTTP status, ETag/last-modified, payload SHA-256, compressed raw JSON, parser version).

This preserves fields not yet modeled, makes parsers replayable, and shows exactly where each displayed fact came from. Keep raw-payload retention bounded by content hash: identical payloads need only one blob plus observation references.

Minimum canonical tables for the first registry:

```text
repositories                 repository_aliases
repository_relationships     repository_observations
revisions                    artifacts
artifact_versions            manifests
dependencies                 licenses
compatibility_evidence       search_documents
crawl_sources                crawl_runs
crawl_cursors                crawl_errors
jobs                         coverage_snapshots
catalog_releases             catalog_release_items
```

Use ordinary relationship tables rather than a graph database. Keep repository identity separate from artifact identity: one repository can contain several plugins/profiles/bundles, and an npm artifact can point to a repository.

### 3. Decide whether a record changed before expensive work

Upsert GitHub repositories by numeric repository ID and npm packages by normalized registry/name. Compare a small observation fingerprint such as:

```text
GitHub: repository_id + updated_at + pushed_at + default_branch + archived/disabled/visibility
npm: registry + package_name + modified + dist-tags + latest-version integrity
```

If the fingerprint is unchanged, record freshness and stop. If it changed, resolve the current default revision/version and enqueue deterministic extraction using an idempotency key:

```text
(job_type, source, external_id, immutable_revision, analyzer_version)
```

The queue record needs priority, attempts, `available_at`, lease owner/expiry, last error, and a dead-letter/quarantine state. Retry only retryable failures; obey `Retry-After` and rate-limit reset headers.

### 4. Extract in bounded tiers and never execute repository code

For every discovered repository:

1. normalize host identity, aliases, owner, URLs, lifecycle flags, timestamps and social counters;
2. resolve `parent` and ultimate `source` for fork lineage;
3. record the immutable default-branch commit SHA;
4. fetch README, license, root package/workspace manifests, DSH/Cordis-specific manifests and a bounded path tree;
5. parse files as data only—no dependency installation, package scripts, builds or repository-supplied binaries;
6. apply file, response, repository-size, path-count, archive-expansion and time limits;
7. mark truncated/failed extraction explicitly instead of silently treating it as “not compatible.”

Use GitHub tree/blob APIs for the cheap path. Use a quarantined `--filter=blob:none --no-checkout` partial clone only when API limits are hit or when diff reconstruction is justified. Full source and all history are not needed merely to list a fork.

### 5. Classify compatibility with evidence, not a boolean guess

Use four states: `confirmed`, `candidate`, `not_compatible`, and `unknown`. Keep evidence rows with method, source locator, observed revision, parser version and confidence.

Suggested deterministic evidence strengths:

1. **Strong:** GitHub ultimate source is the official DSH repository; package manifest depends on a known DSH package; valid DSH bundle/profile/patch manifest is present; known DSH imports or extension points appear in changed source.
2. **Medium:** repository/package metadata and README describe DSH and link to the official upstream; a confirmed DSH artifact depends on it.
3. **Weak lead only:** topic, keyword, name similarity, community-list mention.

A weak lead can cause extraction but must not produce a “compatible” badge by itself. Unknown or failed extractions stay in the registry so later parser improvements can replay them.

### 6. Generate one explicit search document per artifact version

Build the hosted `search_documents` projection deterministically from:

- repository/package/artifact names and aliases;
- owners and organizations;
- descriptions and README headings/text within a byte cap;
- manifest package names, dependencies and configuration keys;
- changed path names and identifiers when diff analysis exists;
- artifact type, lineage, license, platform and compatibility evidence;
- lifecycle, analysis completeness and last-observed timestamps.

Use weighted PostgreSQL `tsvector` fields plus `pg_trgm` for names/aliases. Keep ranking as query relevance; expose compatibility/evidence/activity as independent filters or signals. Do not label a result “best” from a single blended score.

### 7. Publish deterministic full snapshots and deltas

Take a repeatable database view at one transaction boundary and sort every record by stable ID. Publish:

- a periodic full snapshot (initially daily or weekly, depending on size);
- one delta per successful publication sequence;
- explicit upserts and tombstones, never implicit deletion by absence;
- a coverage ledger showing each source run, pages/partitions attempted and completed, errors, and observed counts.

Use content-addressed object names and a small signed manifest:

```json
{
  "schema_version": 1,
  "sequence": 42,
  "base_sequence": 41,
  "kind": "delta",
  "generated_at": "...",
  "expires_at": "...",
  "object": {
    "url": "catalog/sha256-....jsonl.gz",
    "sha256": "...",
    "bytes": 123456
  },
  "coverage_snapshot_id": "...",
  "key_id": "catalog-2026-01",
  "signature": "..."
}
```

The launcher pins the initial public key. It checks schema compatibility, signature, expiry, monotonic sequence, expected base sequence, declared byte limit and SHA-256 before parsing. Imports occur in one SQLite transaction; FTS rows are updated by triggers or rebuilt before commit. On any failure, retain the last good catalog.

This borrows the important TUF properties: trusted root, signed target hashes/lengths, versions, expiry, and rollback/freeze protection. TUF's specification explains that snapshot metadata prevents mix-and-match attacks and timestamp/version rules prevent freeze and rollback attacks. See the [TUF specification](https://theupdateframework.github.io/specification/latest/). If CI identity/transparency is desired, Cosign can sign arbitrary blobs and emit verification bundles; see [Sigstore blob signing](https://docs.sigstore.dev/cosign/signing/signing_with_blobs/). An embedded Ed25519 verifier is simpler for the launcher's v1 runtime.

## Reuse versus build summary

### Reuse

- GitHub fork/repository/search/tree APIs and conditional request semantics;
- npm packuments and the replication cursor when/if a full npm follower is justified;
- ecosyste.ms for candidate discovery and source-qualified enrichment;
- GH Archive for new-activity hints;
- Software Heritage for archival presence, immutable snapshot identity and recovery links;
- PostgreSQL relational storage, FTS, trigram matching and queue locking;
- SQLite FTS5 in the launcher;
- object storage/CDN and standard hashing/signature primitives.

### Build

- the operational definition of the DSH-compatible universe;
- source plans, partition/cursor state and the honest coverage ledger;
- stable cross-source identity, aliases, repository/artifact/version separation and fork lineage;
- deterministic manifest parsers and DSH compatibility evidence rules;
- bounded extraction/quarantine policy;
- replayable raw-observation/provenance model;
- search-document projection and DSH-specific filters;
- snapshot/delta schema, tombstone semantics, signing/key rotation and the launcher importer.

No existing project owns those DSH-specific product semantics.

## Cost-shaped deployment recommendation

Keep the registry repository independently deployable from the launcher repository. A realistic first hosted footprint is:

| Component | Target |
|---|---:|
| Small always-on worker/API process | $5–25/month |
| Small PostgreSQL instance | $0–25/month |
| Object storage/CDN for compressed catalog releases | $1–10/month |
| Logs/uptime monitoring | $0–10/month |
| Reserve for bursts/backfills | remainder to $100 |

These are planning envelopes, not provider quotes. The hard cost controls are architectural:

- do not retain full clones by default;
- deduplicate raw payloads and analysis by content/revision hash;
- skip analysis when source fingerprints are unchanged;
- enforce per-connector rate and byte budgets;
- serialize GitHub requests and use ETags;
- separate cheap deterministic extraction from later model analysis;
- publish static catalog objects so launcher traffic does not hit PostgreSQL;
- require explicit administrative approval for any paid model run or large backfill.

## Concise recommendation

Create a separate `dsh-forge-registry` repository containing the connectors, schema/migrations, Postgres queue, deterministic extractors/classifier, coverage ledger and catalog publisher. Keep a small versioned catalog contract in a language-neutral JSON Schema package that both registry and launcher consume.

Start with GitHub official-fork reconciliation plus targeted discovery, candidate-driven npm verification, Postgres FTS/trigrams, and signed full snapshot/delta delivery to a separate launcher `catalog.sqlite`. Treat ecosyste.ms, GH Archive and Software Heritage as valuable accelerators/evidence sources—not authorities. Defer raw-code search, vectors and a dedicated search cluster until a measured requirement and corpus-size benchmark justify them.
