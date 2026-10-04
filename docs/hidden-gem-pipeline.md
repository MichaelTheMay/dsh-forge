# Hidden-gem research and publication

DSH Forge keeps discovery breadth separate from recommendation trust. Every
validated external record remains searchable, while a reproducible, measured
policy selects at most 250 entries for the research queue and the website's
**Discover** page. Being in that queue is not a security verdict or an install
authorization.

No language model ranks or explains a pick. Every number below is computed from
public GitHub facts, and every sentence a reader sees is generated from those
numbers.

## Pipeline

| Stage | Input | Output | Executes community code |
| --- | --- | --- | --- |
| Ingest | External catalog snapshot | Neutral SQLite/FTS rows | No |
| Gather evidence | Promising repositories, one GraphQL query per 25 | Tests, CI, README size, docs, releases, commit activity, merged PRs, contributors, recent stargazers | No |
| Analyze fork leads | Top metadata leads | Exact head/base commits, bounded changed paths, static compatibility and risk signals | No |
| Rank | Evidence, repository, and source-diff metadata | Score, plain-language reasons, gaps, global rank, curated packs | No |
| Propose | Curator-selected queue entries | Exact npm SRI pins and a draft package manifest | No |
| Certify | Four explicit reviews plus an Ed25519 key | Signed local recipe and certification receipt | No |
| Install | Signed recipe plus a saved DSH version | Quarantine, archive inspection, networkless sandbox test, atomic promotion | Yes, only inside Apptainer |

## Discovery v3: the attention gap

The ranking policy is `dsh-forge.hidden-gems/v3`. A hidden gem is a project
that is **built like projects that get noticed, but hasn't been noticed yet**.

1. **Evidence.** `scripts/enrich_registry.py` reads a fixed set of public facts
   for up to 3,000 promising repositories a day within a 900-point GraphQL
   budget: root files (tests, CI workflows, docs, examples, changelog, README
   size), releases, total and 90-day commits, closed issues, merged pull
   requests, mentionable users, license, and the ten most recent stargazers.
   Evidence is reused for 14 days while a repository hasn't been pushed, so
   coverage grows across runs. Nothing is cloned or executed. Stargazer
   identities are reduced to two numbers before publication: endorsements
   (stars from upstream Harness contributors or authors of plugins with 50+
   stars) and stars in the last 30 days. If evidence would push the published
   registry past 60 MB, the least promising records lose theirs first.
2. **How well it's built.** An equal-weight craft index over the same
   creator-controlled practices (tests, CI, README depth, docs, changelog,
   releases, license, commit volume, recent commits, freshness), so a good
   practice can only raise it. Age is excluded: it buys exposure, not quality.
3. **What attention a build usually earns.** A ridge regression
   (`dsh-forge.attention-ridge/v1`) is fitted across every plugin with
   evidence, predicting `log(1 + stars)` from creator-controlled features only:
   tests, CI, README depth, docs, changelog, releases, license, commit volume,
   recent commits, freshness, and age (here age is a control: young projects
   haven't had time to be noticed). Five-fold cross-validated Spearman
   correlation and R² are published with every queue. The model only sets
   expectations; its coefficients are never read as a quality score, because
   they absorb exposure effects (on the first real run, commit volume and age
   carried most of the weight).
4. **The gap.** A plugin scores `45 × craft percentile + 40 × gap percentile +
   0.75 × outside validation`, where the gap is predicted minus actual
   attention. Outside validation (0-20 points) counts endorsements, merged pull
   requests and closed issues, other contributors, and recent stars, which
   mean something even at three stars.
5. **An honest fallback.** If the model's held-out Spearman correlation is
   below 0.15 on the day's data, it isn't trusted to say what a project
   "should" have. The gap becomes craft rank minus star rank
   (`ranking: craft-index` in the queue) and no reason claims a predicted star
   count.
6. **Gates.** A plugin cannot be a gem if it is archived, unlicensed, above the
   ecosystem's 95th-percentile star count (clamped to 10-50), not pushed in a
   year, missing a description, has a README under 800 bytes, is built worse
   than 60% of plugins, or already gets the attention its build predicts.
7. **Forks** are judged only on what they added: commits ahead of upstream,
   changed surfaces, recency, a description of their own, and a quarter of the
   outside validation. A fork of a fork is excluded, because its divergence is
   measured against upstream and is mostly its parent's work. Fork leads skip
   copies with no commits or stars of their own.
8. **Reasons.** Each pick carries up to four sentences generated from the
   numbers above, for example "Built like projects that usually have ~40
   stars; it has 3.", "Starred by Harness contributors or plugin authors
   (@a, @b).", or "Adds 18 commits on top of DeepSeek Harness, touching CLI and
   commands." Dates are written as a month and year so they stay true while the
   feed is current.

When fewer than 5% of plugins have evidence (for example, a run without a
token), the queue falls back to the metadata-only `dsh-forge.hidden-gems/v2`
policy and says so in `quality.discovery.fallback`. That policy rewards
positive static validation, an exact package version, an immutable commit, a
reported license, specific documentation, recent maintenance, agentic
capabilities, fork-only commits, and low visibility.

The searchable source record stays unchanged; Forge stores research evidence
beside it so an upstream catalog can never award itself a Forge rank. The
registry also carries each candidate's report under `discovery`, so the
desktop store shows the same picks without the separate queue file.

## Curated packs

`dsh-forge.curated-packs/v1` builds themed bundles of complementary plugins
from the same evidence: **Memory & context** (memory, code navigation, search),
**Review & safety net** (code review, security, testing), **Agent teams**
(orchestration, observability, memory), and **Ship faster** (code navigation,
testing, orchestration). Each role is filled by a plugin whose *main* purpose
it is, with a match strength of at least 4: named for it, or tagged with it
twice, or tagged and described that way (one stray topic such as `web-search`
is not enough). Members are built better than half the ecosystem and not gated
for safety reasons. Packs prefer quality over obscurity, use one plugin per
owner, never reuse a plugin across packs,
and give every member a note that says something the others don't. A pack needs
at least three members to be published. Each plugin still installs on its own;
a pack is a reading list, not an installer.

Candidate selection applies `dsh-forge.discovery-diversity/v1` after scoring.
Within a five-point quality window it prefers owners and capability lanes with
less prior exposure. It never promotes a lower-scoring item outside that window.
Quality rank, discovery rank, selection reason, owner concentration, capability
coverage, visibility mix, and score range are included in the queue so ranking
changes can be evaluated rather than judged by anecdotes.

The first two adapters consume the public DSH Plugin Marketplace's daily full
feed and paginate a GitHub fork network. The store and ranking module are
provider-neutral: another agentic tool needs an adapter that emits the same
neutral artifact fields, not a new browser or ranker. Repeating
`--fork-network OWNER/REPO` indexes additional agentic-tool fork networks.

## Continuous queue

The `Catalog research queue` GitHub Actions workflow runs daily and can also be
started manually. It fetches the latest integrity-checked external feed,
paginates the configured fork networks, gathers evidence for promising
repositories (reusing the previous release's evidence where still valid),
selects at most 100 promising fork leads, compares exact source and fork
commits, ranks the assembled corpus and composes packs, and retains
`registry.json` plus `hidden-gems.json` as 30-day workflow artifacts. A fork
snapshot is labelled complete only after stable root and recursive child-page
reconciliation; partial snapshots remain available with explicit reasons. The queue is metadata-only
and carries explicit `executed: false` and `security_verified: false` claims. It
never commits generated data or publishes a package automatically.

On `main`, the workflow also writes deterministic gzip versions plus
`registry-feed.json` to the stable `catalog-latest` GitHub Release. The feed
index is uploaded last, so readers either verify the complete new registry or
fail closed during the short replacement window. Both compressed and expanded
SHA-256 values are checked before JSON import. This is a durable public metadata
feed, not a Forge signature or installation approval.

Build the same review artifact locally:

```bash
python3 scripts/index_registry.py --output /tmp/registry.json
python3 scripts/analyze_registry.py --snapshot /tmp/registry.json --output /tmp/registry-analyzed.json
python3 scripts/research_catalog.py --snapshot /tmp/registry-analyzed.json --output /tmp/hidden-gems.json
python3 -m dsh_forge catalog sync-plugins
python3 -m dsh_forge catalog sync
python3 -m dsh_forge research gems "project memory" --type plugin --type fork --limit 25
```

## Curator feedback and ranking benchmarks

Ratings are bound to one queue snapshot and exact artifact subject. They do not
carry forward silently when a package version, repository commit, or ranking
snapshot changes:

```bash
python3 -m dsh_forge research judge \
  --queue /tmp/hidden-gems.json \
  --artifact github:1339316901 \
  --rating exceptional \
  --reviewer "Release curator" \
  --reviewed-at 2026-09-11T18:00:00Z \
  --notes "Unusually capable project-memory workflow." \
  --output /tmp/discovery-judgments.json

python3 -m dsh_forge research benchmark \
  --queue /tmp/hidden-gems.json \
  --judgments /tmp/discovery-judgments.json \
  --output /tmp/discovery-benchmark.json
```

Multiple curators can independently rate the same artifact. A later rating from
the same curator updates that curator's earlier rating without removing other
reviewers. The benchmark reports reviewer count, double-rated coverage,
pairwise exact agreement, rating counts, judgment coverage, precision,
precision among judged results, and NDCG at 10, 25, and 100. It also compares
the Forge, quality-only, popularity, and recency orderings over the same
candidate set. This comparison measures ordering only; it does not compare how
each method selects candidates for the pool.

Unjudged results count as non-relevant in overall precision and as zero gain in
NDCG. Coverage and precision among judged results make sparse review explicit.
Feedback is unsigned, executes nothing, and never authorizes installation.

For a selection study, first record a transparent planning estimate for the
primary precision comparison:

```bash
python3 -m dsh_forge research study-power \
  --baseline-precision 0.4 \
  --minimum-lift 0.2 \
  --alpha 0.05 \
  --power 0.8
```

The default calculation returns 97 candidates per arm. It is a two-proportion
normal approximation, not a guarantee. Freeze the final sample size after a
separate pilot accounts for arm overlap, observed variance, reviewer clustering,
and the chosen primary analysis.

Then generate one blinded union of the Forge, quality-only,
popularity, and recency arms. All four arms start from the same admissible source
pool: public, unarchived, not known invalid, and bound to a repository URL and
immutable commit. The ballot omits stars, update dates, Forge scores, visibility labels, and
arm membership. Keep the answer key away from curators until all ratings are
complete:

```bash
python3 -m dsh_forge research study-create \
  --snapshot /tmp/registry-analyzed.json \
  --per-arm 97 \
  --seed "study-round-2026-09" \
  --ballot /tmp/discovery-study-ballot.json \
  --key /secure/discovery-study-key.json

python3 -m dsh_forge research judge \
  --queue /tmp/discovery-study-ballot.json \
  --artifact github:1339316901 \
  --rating exceptional \
  --reviewer "Curator 1" \
  --reviewed-at 2026-09-13T18:00:00Z \
  --output /tmp/discovery-study-judgments.json

```

To use the current public catalog instead of a local snapshot, replace the
`--snapshot` argument with:

```bash
--url https://github.com/MichaelTheMay/dsh-forge/releases/download/catalog-latest/registry-feed.json
```

The same catalog-feed client verifies the compressed and expanded checksums
before study construction.

Build a separate, deterministically balanced review page for each reviewer.
This example assigns every candidate to exactly three of nine reviewers:

```bash
python3 -m dsh_forge research study-packet \
  --ballot /tmp/discovery-study-ballot.json \
  --reviewer-index 1 \
  --reviewer-count 9 \
  --reviews-per-candidate 3 \
  --output /tmp/discovery-study-reviewer-01.html
```

Repeat the packet command with reviewer indices 2 through 9, then send each
reviewer only their assigned file. Each file makes no network requests, stores
progress in that browser, and exports a snapshot-bound judgment ledger. It never
contains the answer key.
Opening a repository link manually is outside the packet and may reveal the
reviewer to the repository host.

After review, merge all exports and run the frozen benchmark:

```bash
python3 -m dsh_forge research study-merge \
  --ballot /tmp/discovery-study-ballot.json \
  --judgments /tmp/reviewer-01.json \
  --judgments /tmp/reviewer-02.json \
  --judgments /tmp/reviewer-03.json \
  --output /tmp/discovery-study-judgments.json

python3 -m dsh_forge research study-benchmark \
  --ballot /tmp/discovery-study-ballot.json \
  --key /secure/discovery-study-key.json \
  --judgments /tmp/discovery-study-judgments.json \
  --min-reviews 3 \
  --bootstrap-samples 5000 \
  --output /tmp/discovery-study-results.json
```

The separate key binds each method to its ranked arm and binds the arm set to
the ballot. The benchmark fails until every candidate has the required review
count. It reports per-arm precision with bootstrap intervals, NDCG, low-visibility
yield, owner diversity, pairwise Forge-versus-baseline differences with intervals,
exact agreement, and quadratic weighted kappa. These commands make the experiment
reproducible, but they do not replace preregistration or independent curators.

The current analyzer is a deliberately bounded REST tier. It resolves both
repositories to immutable commits, asks GitHub to compare those commits, records
ahead/behind counts and up to 300 changed paths, and parses `package.json` only
when that file changed. It never clones or executes a repository. `files_truncated`
is explicit when GitHub reaches its response limit. The blobless local Git tier
described in [source analysis](research/source-analysis.md) remains the later
canonical path for complete tree deltas and rename/binary fidelity.

## Evaluate a fork lead

After importing an analyzed snapshot, a curator can record an inert decision
bound to the artifact ID, exact commit, and source-evidence digest:

```bash
python3 -m dsh_forge research evaluate \
  --artifact github:123456 \
  --decision advance \
  --reviewer "Release curator" \
  --reviewed-at 2026-09-11T18:00:00Z \
  --review-source --review-risk --review-license --review-compatibility \
  --notes "Advance to isolated source review." \
  --output /tmp/github-123456.assessment.json
```

This assessment is unsigned and always records `installation_authorized: false`.
It is a review-queue decision, not a certification. Any later distributable
package still follows the signed proposal, quarantine, networkless sandbox, and
atomic promotion path below.

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
- GitHub compare metadata is useful screening evidence, not a complete local Git analysis.
- Exact registry pins prevent silent version drift; they do not prove publisher
  identity or behavior.
- Signing records who approved exact metadata. It does not execute the package.
- Only the final install transaction downloads bytes, inspects the archive,
  disables lifecycle scripts and network in the disposable build, smoke-tests
  the result in Apptainer, and promotes on success.
- The scheduled workflow can publish unsigned metadata feed assets, but cannot
  sign or publish installable packages. It receives no curator key.

These boundaries let additional ecosystems reuse ingestion and ranking without
weakening DSH Forge's local trust and sandbox requirements.
