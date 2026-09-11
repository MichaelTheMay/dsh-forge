# Registry indexing

The launcher consumes one neutral snapshot shape. Network collection stays in a
separate command, so searching and launching local DSH installations never
depends on GitHub or a marketplace being online.

```bash
export GITHUB_TOKEN=REDACTED
python3 scripts/index_registry.py --output registry-raw.json
python3 scripts/analyze_registry.py --snapshot registry-raw.json --output registry.json
python3 -m dsh_forge catalog import registry.json
```

`GITHUB_TOKEN` is optional for small tests and recommended for a full network.
The scheduled workflow uses its short-lived Actions token. Tokens are sent only
to `https://api.github.com`; redirects and pagination links to another host are
rejected.

## Sources and reuse

The default run merges:

- the integrity-checked DSH Plugin Marketplace v1 feed;
- the `deepseek-ai/deepseek-harness` GitHub fork network.

Additional agentic development tools can reuse the fork adapter without code
changes:

```bash
python3 scripts/index_registry.py \
  --fork-network owner/tool-one \
  --fork-network owner/tool-two \
  --output registry.json
```

Adapters own source validation and emit stable `artifact_id` values. The merge
deduplicates repositories by GitHub numeric ID. If a repository is both a fork
and a plugin, the richer plugin row is retained with both classifications.
Provenance stays attached to every source; merging never upgrades trust.

## Coverage contract

GitHub's root repository metadata is read before and after `Link` pagination.
Every returned fork with a nonzero child-fork count is recursively paginated;
zero-child forks require no extra request. Each network receives one coverage
record:

- `complete`: pagination ended, the root count did not change, the root pages
  reconcile with that direct-fork count, and every child page reconciles with
  its parent count;
- `incomplete`: a page or record bound was reached, the count changed, or the
  result did not reconcile. Reasons are included in the record.

This is a fail-honest contract. “Complete” means every public result visible to
the recursive API traversal was reconciled during that run; inaccessible forks
may still keep a run incomplete. A partial inventory remains searchable, but
the product must not call it “all forks.” The endpoint response is metadata
only: the indexer never clones, installs, imports, or executes repository code.

Fork rows initially remain `browse-only` and deliberately omit an immutable
head commit. The bounded analysis command selects at most 100 promising
metadata leads, pins source and fork heads, captures GitHub compare evidence,
and extracts path/manifest compatibility and risk signals without cloning or
executing code. Unselected records remain fully browseable. Installation requires source and
permission review, license verification, compatibility testing, signing, and
the existing networkless Apptainer certification path.

## Scheduled output

`.github/workflows/catalog-research.yml` rebuilds the raw registry, enriched
`registry.json`, and the bounded
`hidden-gems.json` research queue every day and on manual dispatch. Both are
retained for 30 days as workflow artifacts. The workflow has read-only contents
permission and no curator signing key, so it cannot certify or publish a
package.
