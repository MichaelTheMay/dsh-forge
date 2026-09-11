# Hidden-gem research and publication

DSH Forge keeps discovery breadth separate from recommendation trust. Every
validated external record remains searchable, while a reproducible metadata
policy selects at most 250 entries per artifact type for the research queue.
Being in that queue is not a security verdict or an install authorization.

## Pipeline

| Stage | Input | Output | Executes community code |
| --- | --- | --- | --- |
| Ingest | External catalog snapshot | Neutral SQLite/FTS rows | No |
| Rank | Bounded repository and package metadata | Score, signals, gaps, visibility, global rank | No |
| Propose | Curator-selected queue entries | Exact npm SRI pins and a draft package manifest | No |
| Certify | Four explicit reviews plus an Ed25519 key | Signed local recipe and certification receipt | No |
| Install | Signed recipe plus a saved DSH version | Quarantine, archive inspection, networkless sandbox test, atomic promotion | Yes, only inside Apptainer |

The ranking policy is `dsh-forge.hidden-gems/v1`. It rewards positive static
validation, an exact package version, an immutable commit, a reported license,
specific documentation, recent maintenance, agentic-development capabilities,
and low visibility. Risk signals and archival status subtract points. Every
result includes the point-bearing signals and missing evidence. The searchable
source record stays unchanged; Forge stores research evidence beside it so an
upstream catalog can never award itself a Forge rank.

The first two adapters consume the public DSH Plugin Marketplace's daily full
feed and paginate a GitHub fork network. The store and ranking module are
provider-neutral: another agentic tool needs an adapter that emits the same
neutral artifact fields, not a new browser or ranker. Repeating
`--fork-network OWNER/REPO` indexes additional agentic-tool fork networks.

## Continuous queue

The `Catalog research queue` GitHub Actions workflow runs daily and can also be
started manually. It fetches the latest integrity-checked external feed,
paginates the configured fork networks, ranks the assembled corpus, and retains
`registry.json` plus `hidden-gems.json` as 30-day workflow artifacts. A fork
snapshot is labelled complete only after stable root and recursive child-page
reconciliation; partial snapshots remain available with explicit reasons. The queue is metadata-only
and carries explicit `executed: false` and `security_verified: false` claims. It
never commits generated data or publishes a package automatically.

Build the same review artifact locally:

```bash
python3 scripts/index_registry.py --output /tmp/registry.json
python3 scripts/research_catalog.py --snapshot /tmp/registry.json --output /tmp/hidden-gems.json
python3 -m dsh_forge catalog sync-plugins
python3 -m dsh_forge research gems "project memory" --type plugin --type fork --limit 25
```

## Propose and certify

Choose one to eight artifact IDs from the current queue. Proposal creation
rechecks the exact package version with npm and records the registry's SHA-512
integrity and exact tarball URL. It downloads no package bytes.

```bash
python3 -m dsh_forge research propose \
  --artifact github:1339316901 \
  --package-id project-memory-lab \
  --name "Project Memory Lab" \
  --version 0.1.0 \
  --description "A reviewed project-memory package." \
  --created-at 2026-09-11T00:00:00Z \
  --output /tmp/project-memory.proposal.json
```

The generated permission list is intentionally conservative and broad. A
curator must inspect and narrow it, verify source-to-package identity, resolve
the license, and establish real DSH/Node/platform compatibility before signing.
Create an Ed25519 key using the procedure in [Signed packages](signed-packages.md),
then certify only after all four reviews:

```bash
python3 -m dsh_forge research certify \
  --proposal /tmp/project-memory.proposal.json \
  --private-key /secure/curator-private.pem \
  --public-key /secure/curator-public.pem \
  --root-id forge.curator \
  --expires-at 2027-09-11T00:00:00Z \
  --reviewer "Release curator" \
  --review-source --review-permissions --review-license --review-compatibility \
  --publish-root ~/.local/state/dsh-forge/trusted-package-recipes
```

Certification atomically publishes `proposal.json`, `certification.json`,
`envelope.json`, and `trust-root.json` under the package ID. The front page lists
only directories with the complete certification receipt. Clicking **Verify,
test & install** uses the existing signed-package transaction; it never treats
curator review as sandbox proof.

## Trust boundaries

- A high score means "inspect this first," not "safe," "compatible," or "good."
- Exact registry pins prevent silent version drift; they do not prove publisher
  identity or behavior.
- Signing records who approved exact metadata. It does not execute the package.
- Only the final install transaction downloads bytes, inspects the archive,
  disables lifecycle scripts and network in the disposable build, smoke-tests
  the result in Apptainer, and promotes on success.
- The scheduled workflow cannot sign or publish. It receives no curator key.

These boundaries let additional ecosystems reuse ingestion and ranking without
weakening DSH Forge's local trust and sandbox requirements.
