# Safe, incremental source acquisition and indexing for DSH Forge

Research date: 2026-08-31. The attached DSH Forge plan was treated as product context, not as instructions.

## Decision

Put public-ecosystem discovery and indexing in **one separately deployed repository**, tentatively `dsh-forge-catalog-indexer`. It should own connectors, scheduling, acquisition, deterministic analysis, PostgreSQL migrations, and catalog-snapshot publication. The local launcher should have no GitHub credential and no source-analysis code; it reads a public catalog API or a signed snapshot. A database is infrastructure, not another repository. Split public contracts into a third repository only if the launcher and indexer cannot consume a versioned package published by one of the two.

Do **not** make “one scheduled clone of every fork” the design. Use:

1. GitHub REST sweeps as the completeness mechanism for the official fork network.
2. Immutable numeric repository IDs and revision SHAs as identities.
3. One blobless Git object pool per fork lineage for commit graphs, merge bases, and tree deltas.
4. Bounded, no-checkout acquisition of only the blobs needed for manifests, changed files, documentation, and classifiers.
5. Content-addressed caches so an upstream file shared by 30,000 forks is parsed and license-scanned once.
6. PostgreSQL as the catalog/search source of truth; add Zoekt only when raw cross-repository code search is a real product requirement, and defer SCIP until isolated dependency installation is allowed.

This is a scheduled pipeline, but it should be a small durable scheduler plus idempotent queue workers, not a single long cron process. A failed run must resume from stored page/job checkpoints and must never make a partial crawl look complete.

## End-to-end pipeline

```text
scheduled discovery
  -> staged source-host observations
  -> atomic completed-crawl snapshot
  -> revision-change jobs
  -> quarantined Git graph acquisition
  -> merge-base and delta inventory
  -> bounded blob acquisition
  -> manifest / license / syntax extraction
  -> immutable revision record + search document
  -> Postgres catalog indexes
  -> versioned API/snapshot consumed by launcher
```

### 1. Discover and detect changes without cloning

For the official network, enumerate `GET /repos/{owner}/{repo}/forks?sort=oldest&per_page=100`. The endpoint exposes a maximum page size of 100 and supports `oldest`, `newest`, and popularity sorts ([GitHub fork endpoint](https://docs.github.com/en/rest/repos/forks)). `oldest` keeps additions at the tail in the normal case, making page ETags materially more useful than a newest-first crawl.

Persist each run and page separately: query, page URL from the `Link` header, ETag, status, attempt, observed IDs, response digest, rate-limit headers, and timestamps. GitHub recommends authenticated conditional requests; a correctly authorized `304 Not Modified` does not consume the primary REST limit. It also recommends stable pagination parameters and serial/queued requests to avoid secondary limits ([GitHub REST best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api), [pagination](https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api)).

Write results into a crawl staging set. Only after every page succeeds should a transaction mark that set complete and compare it with the prior complete set. Missing repositories become tombstone candidates, not immediate deletions. Confirm disappearance on a later complete sweep and retain the last known revision.

The fork-list payload’s metadata and `pushed_at` are change **hints**. Resolve and store the default-branch commit OID; a revision changed only when that OID changed. This catches force-pushes and avoids reanalysis when only stars or descriptions change. Use two digests:

- `metadata_digest = hash(canonical source-host metadata)` for catalog-only updates;
- `revision_key = (repository_id, object_format, commit_oid)` for source analysis.

The job dedupe key should include the analyzer version: `repo-id:commit-oid:analyzer-version`. Raw source-host JSON and response headers should be retained so new fields can be backfilled without recrawling.

Other DSH candidates—topics, repository/code searches, package registries, Discussions, and links found in already indexed artifacts—are *lead sources*. Partition broad searches by creation/push windows and record query coverage. Normalize every lead back to a host repository ID before acquisition. Never infer identity from `owner/name`; repositories can be renamed or transferred.

Webhooks are only an accelerator for authors who install the Forge GitHub App. GitHub states that App webhooks cover repositories to which the installation has access, so arbitrary public forks still require polling ([webhook types](https://docs.github.com/en/webhooks/types-of-webhooks)).

### 2. Acquire Git history once per lineage

Maintain a bare, blobless object pool for the official upstream and its fork network. Git’s `--filter=blob:none` transfers commits and trees while deferring file contents; unlike a shallow clone, it preserves history needed by `merge-base` ([Git clone](https://git-scm.com/docs/git-clone), [Git partial clone design](https://git-scm.com/docs/partial-clone)). GitHub explicitly warns that shallow clones make `merge-base` unavailable and recommends blobless over repeatedly fetching shallow histories ([GitHub partial-clone guidance](https://github.blog/open-source/git/get-up-to-speed-with-partial-clone-and-shallow-clone/)).

For each changed fork, fetch its observed default-branch tip into a namespaced ref such as `refs/forge/repos/<numeric-id>/<oid>`. Verify that the fetched OID equals the observation; if the branch moved during acquisition, record the race and enqueue the newer OID. Common commits and trees naturally deduplicate in the lineage pool. Serialize writes to a pool; analyzers should read a snapshot or disposable reference clone rather than race with repacking.

Do not add tens of thousands of persistent promisor remotes to one repository. For blob reads, create a disposable no-checkout partial clone whose promisor is the one fork and whose alternates/reference point at the lineage pool. Batch missing-blob retrieval for the specific revision/path set. Current Git provides `git backfill` to batch missing objects in blobless partial clones and can restrict work using sparse paths; this avoids the pathological one-request-per-blob behavior of some lazy operations ([Git backfill](https://git-scm.com/docs/git-backfill)). Extract bytes with plumbing commands such as `git cat-file`, then discard the disposable repository.

For an unrelated plugin repository or a Git failure, a commit-pinned GitHub tar archive is an acceptable current-tree fallback. GitHub guarantees the same extracted file contents for an archive requested by commit ID, while the outer compression bytes may change; branches and tags are not immutable ([GitHub source archives](https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives), [archive REST endpoint](https://docs.github.com/en/rest/repos/contents#download-a-repository-archive-tar)). Hash extracted entries, not the tarball alone.

The REST Trees API is useful for lightweight inventories but not the primary acquisition path: recursive responses are capped at 100,000 entries or 7 MB and can be marked truncated ([Git Trees API](https://docs.github.com/en/rest/git/trees)). Per-blob REST reads are a last-mile fallback, not bulk transport; the endpoint supports blobs only up to 100 MB and costs a request per blob ([Git Blobs API](https://docs.github.com/en/rest/git/blobs)).

### 3. Reconstruct the fork delta

For each fork revision:

1. Resolve numeric parent and ultimate-source identities from source-host metadata.
2. Fetch the relevant upstream head and fork head into the same lineage graph.
3. Run `git merge-base --all upstream fork`; Git notes that a pair can have multiple best common ancestors, so retain all candidates rather than silently selecting one ([git-merge-base](https://git-scm.com/docs/git-merge-base)).
4. Record ahead/behind counts from the symmetric revision range.
5. Produce a NUL-delimited machine inventory with `git diff-tree --raw --numstat -z --find-renames`, including modes, old/new blob IDs, adds/deletes, renames, and binary markers. Git documents these machine-readable forms and binary/rename behavior ([git-diff-tree](https://git-scm.com/docs/git-diff-tree)). Disable external diff and text-conversion helpers.
6. Enumerate fork-only commits, first-parent structure, merge commits, authorship timestamps, and patch equivalence to upstream. Keep both the commit history and the net tree delta; they answer different questions.
7. If there is no merge base, classify the repository as detached/rewritten and preserve that fact. Heuristic similarity must not be presented as proven lineage.

Do not use GitHub’s compare response as the canonical delta. It is useful for display or fallback, but local Git against the complete graph gives reproducible merge-base, rename, and binary handling. GitHub does support comparisons across forks in the same network ([compare commits endpoint](https://docs.github.com/en/rest/commits/commits#compare-two-commits)).

### 4. Fingerprint duplicates at several strengths

One hash cannot represent all meanings of “same fork.” Store:

- **Exact revision content:** root tree OID plus object format. Equal values mean identical tracked content.
- **Exact modification fingerprint:** SHA-256 over a versioned canonical encoding of `(path, status, modes, old-blob-id, new-blob-id)` sorted by raw path bytes, plus ultimate-source ID. This is deterministic and binary-safe.
- **Patch-equivalent commit IDs:** `git patch-id --stable` for each non-merge commit, plus a sorted aggregate. Git describes stable patch IDs as whitespace-insensitive, file-order-independent identifiers intended to find likely duplicate changes ([git-patch-id](https://git-scm.com/docs/git-patch-id)). They are evidence of equivalence, not a cryptographic identity.
- **Near-duplicate feature signature:** MinHash/SimHash or token shingles over added/modified syntax nodes, scoped by upstream and DSH extension surface. Use this only to form review candidates.

Keep distinct repositories as distinct social artifacts even when their exact delta fingerprint is shared. Reuse extraction and analysis results by content/fingerprint, but preserve owner, stars, license, and activity separately.

### 5. Extract deterministic metadata without running repository code

First read only a bounded path set: root manifests, workspace manifests, lockfiles, README/docs/changelog, license/notice files, DSH/Cordis configuration, workflow and container declarations, and files in the fork delta. Expand to the full current tree only after size/type gates pass.

Parse manifests and lockfiles as data; never invoke the package manager. `package-lock.json` describes the exact generated dependency tree and includes resolved sources, integrity values, install-script flags, licenses, engines, OS, and CPU information ([npm lockfile specification](https://docs.npmjs.com/cli/v11/configuring-npm/package-lock-json/)). Capture raw bytes, parsed canonical JSON, parser version, parse warnings, workspace relationships, dependency kinds/ranges, resolved artifacts/integrity, scripts, entry points, exports, engines/platforms, package manager, and DSH-specific declarations. Do the same for pnpm, Yarn, Cargo, Python, Go, Docker/Compose, devcontainers, CI workflows, submodule pointers, and Git LFS pointer files where present—without following or installing any of them.

Use Tree-sitter with pinned, prebuilt grammars for TypeScript/JavaScript and other observed languages. It creates syntax trees quickly and remains useful in the presence of syntax errors ([Tree-sitter](https://github.com/tree-sitter/tree-sitter)). Cache parse/extraction output by `(blob-content-digest, grammar-version, query-version)`, and on a new revision parse only new blob IDs. Extract imports/exports, declared symbols, DSH package references, Cordis services/events/patch rows, config keys, routes, tools, and tests with query patterns; retain byte ranges as evidence.

Do **not** run SCIP in the safe deterministic tier. SCIP is a good interchange format for definitions/references ([SCIP schema](https://github.com/scip-code/scip/blob/main/scip.proto)), but the official TypeScript indexer’s normal workflow installs project dependencies first and may require very large Node heaps ([scip-typescript](https://github.com/sourcegraph/scip-typescript)). That crosses the “do not execute or resolve untrusted repositories” boundary. Add SCIP later only inside the stronger build sandbox for selected artifacts, or accept a lower-fidelity syntax-only SCIP producer of your own.

License evidence should be layered:

1. GitHub’s detected repository license as a source-host observation, not a legal conclusion ([GitHub Licenses API](https://docs.github.com/en/rest/licenses)).
2. Declared SPDX expressions in manifests and `SPDX-License-Identifier` headers. SPDX expressions represent choices and combinations with `AND`, `OR`, and `WITH` ([SPDX expression specification](https://spdx.github.io/spdx-spec/v3.0.1/annexes/spdx-license-expressions/)).
3. REUSE metadata, `.license` companions, `REUSE.toml`, and `LICENSES/`; REUSE defines machine-readable file-level licensing and precedence ([REUSE 3.3](https://reuse.software/spec/)).
4. ScanCode Toolkit for license text, notices, copyright, and package evidence on each **new unique blob**, cached by digest. ScanCode is designed to detect licenses, copyrights, packages, dependencies, and origins ([ScanCode documentation](https://scancode-toolkit.readthedocs.io/en/latest/)).

Expose `declared`, `detected`, `conflicting`, and `unknown` separately. “No license detected” must not be converted to “open source.”

### 6. Catalog schema and indexes

Keep mutable identities separate from immutable evidence:

- `repositories`: host, numeric/node ID, current name/owner/status, parent/source IDs;
- `repository_aliases` and `repository_observations`: time-varying names and lossless host payloads;
- `revisions`: commit/tree IDs, observed refs, timestamps, acquisition state;
- `revision_paths`: path, mode, object type, blob ID, size, language/MIME, LFS/submodule markers;
- `deltas`, `delta_paths`, `commits`, `fingerprints`;
- `manifests`, `packages`, `dependencies`, `lock_resolutions`;
- `license_findings` with source, expression, confidence, path/range;
- `syntax_facts` and `dsh_evidence` with blob/range provenance;
- `analysis_runs`: tool/image versions, inputs, limits, warnings, failures, coverage;
- `search_documents`: one current document per artifact/revision plus historical versions if needed.

Index IDs, revision OIDs, source/fork identity, fingerprints, DSH compatibility ranges, license state, artifact type, and refresh times with ordinary B-tree/GIN indexes. Start user-facing search with PostgreSQL `tsvector` + GIN over name, description, topics, README, manifest names/dependencies, changed paths, extracted symbols/config keys, commit subjects, and normalized DSH evidence. PostgreSQL calls GIN the preferred full-text index type; `pg_trgm` adds indexed similarity, substring, `LIKE`, and regex search for names and symbols ([PostgreSQL text-search indexes](https://www.postgresql.org/docs/current/textsearch-indexes.html), [`pg_trgm`](https://www.postgresql.org/docs/current/pgtrgm.html)).

Add Zoekt only if users need arbitrary substring/regex search over all source code. It is purpose-built for cross-repository code search, mmap-able shards, and branch deduplication, but its own design estimates index shards at about 3.5 times corpus size ([Zoekt design](https://github.com/sourcegraph/zoekt/blob/main/doc/design.md), [Zoekt project](https://github.com/sourcegraph/zoekt)). Rebuild only the changed repository shard and treat Zoekt as a derived index, never the metadata source of truth.

### 7. Quarantine and resource limits

Repository bytes are untrusted even when no build occurs. Every acquisition/parser job should run as an unprivileged, short-lived container or pod with:

- no checkout, submodule initialization, Git LFS fetch, package install, hooks, credential helpers, or network-discovered remotes;
- an empty/sanitized Git config, `core.hooksPath=/dev/null`, HTTPS-only protocol policy, canonical allowlisted host URLs constructed by the service, prompts disabled, and `fetch.fsckObjects=true`; Git’s fsck setting rejects malformed/missing objects and checks known security issues including malicious `.gitmodules` cases ([Git config](https://git-scm.com/docs/git-config));
- no shell interpolation; pass fixed executable arguments;
- read-only root, dropped capabilities, `no-new-privileges`, seccomp, PID/CPU/memory/open-file limits, a size-limited scratch volume, wall-clock deadline, and network egress limited to the required source-host endpoints. Docker exposes read-only roots, PID and resource limits, and `no-new-privileges` controls ([Docker run](https://docs.docker.com/reference/cli/docker/container/run), [resource constraints](https://docs.docker.com/engine/containers/resource_constraints/));
- byte, object-count, tree-entry, path-depth/length, individual-blob, expanded-archive, compression-ratio, parse-node, and output-row budgets;
- streaming archive extraction that rejects absolute paths, `..` traversal, device nodes, hard links, unsafe symlinks, ownership changes, and writes outside scratch;
- parsers and Git pinned to patched images, with crash/time/resource-limit results quarantined rather than retried forever.

Quarantine is a catalog state, not invisibility. The launcher can still show safe host metadata while clearly labeling source analysis as partial/failed and preventing downloads or execution.

### 8. Immutable evidence storage and retention

Store raw API observations, acquisition manifests, analyzer outputs, and retained source blobs under content-addressed keys with a server-verified SHA-256 checksum. S3 supports upload/download checksum verification, including SHA-256 ([S3 integrity checks](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html)). A revision manifest should map every retained path to Git object ID, byte digest, size, media type, acquisition source, and analyzer versions.

Use bucket versioning and short governance retention for raw evidence, not indefinite compliance lock. S3 Object Lock is WORM storage and requires versioning, but a permanent lock conflicts with takedown/privacy obligations and cannot be undone simply by deleting a catalog row ([S3 Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html)). Keep mutable aliases and current status in PostgreSQL; immutable evidence objects are append-only and referenced by digest. Lifecycle commit archives and superseded raw responses to colder/cheaper storage, while retaining small normalized facts and hashes.

## Build versus buy

| Capability | Recommendation | Why / cost shape |
|---|---|---|
| Fork completeness and metadata | Build a thin connector on GitHub REST/GraphQL with Octokit | The official fork endpoint is the authority; scraping vendors add cost and another completeness claim to audit. Cost is roughly `forks / 100` REST pages per full sweep, mostly conditional. |
| Git graph and deltas | Build around pinned Git CLI | Git already owns merge-base, reachability, rename and binary semantics. A lineage object pool avoids N full clones. |
| Durable catalog and queue | Buy managed PostgreSQL; build schema/jobs | Tens of thousands of repos are modest relational scale. One database supports identity, leases, FTS, and launcher filters without Redis/OpenSearch initially. |
| Evidence bytes | Buy S3-compatible object storage | Cheap, checksummed, lifecycle-managed, and versionable. Storage grows with unique retained blobs/revisions, not repository count if CAS is used. |
| Syntax extraction | Build DSH-specific Tree-sitter queries | Low execution risk and high evidence value; parse cost is proportional to new unique blobs. |
| License analysis | Adopt ScanCode; build normalization/cache | Mature detection is expensive to recreate. Cache by blob digest so upstream code is scanned once. |
| Raw code search | Defer, then self-host Zoekt | Excellent when actually needed, but SSD footprint is approximately 3.5× indexed corpus and it adds another service. |
| Precise code navigation | Defer SCIP/Sourcegraph | Compiler-backed quality generally needs dependency installation/build context, which belongs after the strong sandbox boundary. |
| Vector/LLM classification | Asynchronous optional enrichment | Deterministic evidence must ship first. Model cost should scale with novel fingerprints/evidence packs, not every fork. |

The dominant steady-state cost should be changes, not total repositories:

```text
API: complete-page sweep + revision resolution for changed hints
network: new commit/tree objects + selected new blobs
CPU: new unique blobs x enabled analyzers
Postgres: observations + immutable revision facts + compact search docs
optional Zoekt SSD: ~3.5 x indexed source corpus
```

## Recommended delivery order

Current implementation note: Forge now implements a bounded preview of steps 2
and 3 for the top 100 metadata leads. It resolves immutable source/fork commits
and records GitHub compare counts and the provider's first 300 changed paths.
This is explicitly labelled `github_compare_metadata`; it is not the canonical
Git graph/delta tier described below and it executes no repository code.

1. **Coverage ledger:** fork sweeper, stable IDs, ETags, complete-run publication, tombstones, raw payload retention.
2. **Revision detector:** default-branch OIDs, deduped jobs, lineage mapping, no source content yet.
3. **Safe graph tier:** blobless lineage pool, merge bases, ahead/behind, changed-path inventory, exact fingerprints.
4. **Deterministic content tier:** bounded blob acquisition, manifests/lockfiles, README/license, Tree-sitter DSH evidence, blob-level caches.
5. **Catalog search:** PostgreSQL schema, GIN/trigram indexes, versioned public API/signed snapshot, launcher integration.
6. **Depth:** full unique-blob ScanCode backlog, feature clustering, optional Zoekt; SCIP/build/test only after the execution sandbox exists.

## Decisions to grill the product owner on

- Does “every fork” mean every fork returned by the official fork endpoint, or also every branch and tag inside every fork?
- Must Forge retain full public source after a repository is deleted, or only derived metadata and hashes? What is the takedown policy?
- Is raw arbitrary code search a launch requirement, or is search over metadata, docs, manifests, changed paths, and extracted DSH symbols enough?
- What maximum repository/blob/expanded-archive limits may produce a visible “metadata-only / analysis skipped” result?
- Which DSH compatibility signals are authoritative: declared manifest range, imported package/API surface, upstream merge base, or later sandbox verification?
- May public commit author emails be retained internally, and which identity fields may be displayed?
- What freshness SLO is required for new forks versus pushes to old forks? That determines API budget and worker concurrency.
- Is an author-installed GitHub App desirable for near-real-time updates and verified claims, while polling remains the completeness layer?
