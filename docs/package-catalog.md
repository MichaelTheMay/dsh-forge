# Package catalog metadata and bounded ingester

The Packages browser is the primary community discovery surface. A **package**
is a curated, ordered candidate made from one or more exact plugin releases; a
**plugin** page describes one upstream project/release. Package inclusion does
not authorize acquisition, installation, or execution.

## Machine contracts

Three closed JSON Schemas live in `schemas/`:

- `dsh-forge.catalog-sources/v1` records bounded directories and curated
  package recipes;
- `dsh-forge.catalog-package/v1` defines the complete metadata shown on every
  package page; and
- `dsh-forge.catalog-feed/v1` contains deterministic package records plus a
  canonical SHA-256 catalog digest.

Every component requires an exact semantic version, npm SHA-512 SRI or MCPB
SHA-256, canonical repository URL, and full repository commit. Each package
also declares publisher, component roles, taxonomy, compatibility status,
surfaces, license metadata, permissions/risk, provenance, verification state,
and a stable `#packages/<slug>` route. Unknown fields and duplicate identities,
ranks, routes, components, or directory IDs are rejected.

Run the local, networkless ingester and embed the result:

```bash
python3 scripts/ingest_package_catalog.py --check
python3 scripts/embed_catalog.py
```

The ingester reads only `data/package-catalog.sources.json` and the already
pinned plugin metadata in `data/public-repos.seed.json`. It does not fetch a
directory, execute a package manager, install dependencies, inspect a Harness
home, or run community code. Its output is
`data/package-catalog.seed.json`.

## Existing directories are discovery leads

The first source ledger records immutable snapshots of
[DSH Get](https://github.com/bobby-sheng/dshget-data) and
[Awesome DeepSeek Harness](https://github.com/0xsline/awesome-deepseek-harness),
plus the official Show Your Plugins category, npm, and GitHub. The generic
`directory_leads()` adapter accepts a bounded DSH Get-style `plugins` array and
emits only repository/package-name leads. It deliberately drops directory
install commands and verification labels.

Directory presence, an author announcement, stars, and topics cannot establish
compatibility or safety. Exact package metadata is re-enriched from npm/MCPB;
repository identity and revisions come from GitHub. A repository commit is an
observed immutable source reference and is not called a release commit when npm
does not publish a corresponding `gitHead`.

## Initial package pages

The seed contains three explicit review candidates:

- **AgentTeams Builder** — `@nanmicoder/dsh-agent-teams@0.1.16-rc.1`;
- **Code Review Lab** — `dsh-vet@0.3.0` plus
  `dsh-code-index@0.3.1`; and
- **Auditable Memory Lab** — `rawmem@0.7.1` plus `memdsl@0.9.2`.

All three say metadata reviewed, artifacts not acquired, not installed, not
executed, and not sandbox verified. The visible **Acquire verified bytes**
control remains disabled because none has a trusted DSSE package envelope.
This is a stronger promise than an “Install” button backed only by a directory
record.

## Hosted database and client streaming contract

The hosted registry belongs in the separate `dsh-forge-registry` service. Its
canonical database should keep repositories, artifacts, versions, package
recipes, source observations, moderation decisions, compatibility evidence,
catalog releases, and release items separately. Raw directory observations are
append-only provenance; normalized product rows never overwrite their source.

Clients should not connect directly to that database or stream executable
archives. A publication job emits signed, content-addressed full snapshots and
deltas. The launcher verifies the root key, schema version, sequence, expiry,
declared length, and digest before importing the metadata transactionally into
its local search index. On failure it retains the last known-good catalog.

The initial public API shape is therefore read-only:

```text
GET /v1/catalog/releases/latest
GET /v1/catalog/objects/sha256/<digest>
GET /v1/packages/<slug>
```

Uploads later require authenticated publisher identity, moderation state,
artifact ownership proof, signing-key policy, and immutable blob storage. That
is independent from this unsigned development feed.

## Deferred execution boundary

A catalog page may enable **Acquire verified bytes** only after it points to a
trusted DSSE envelope accepted by the existing trust-root verifier. Even then,
acquisition ends in the non-executable content-addressed quarantine. “Install”
and “Run” require archive inspection, disposable profile construction, exact
dependency resolution, and a reproducible Apptainer compatibility test. No
package is installed into an existing user profile by this change.
