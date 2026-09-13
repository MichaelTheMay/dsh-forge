# Cross-ecosystem adapter smoke test

Date: 13 September 2026

## Question

Can the existing source-neutral GitHub fork adapter collect metadata from other
agentic developer tool ecosystems without a code change?

## Method

The live GitHub REST API was queried without a token. Each network was limited
to one page and 100 records. This was a format and policy smoke test, not a
coverage benchmark.

```bash
python3 scripts/index_registry.py \
  --skip-marketplace \
  --fork-network openai/codex \
  --fork-network anthropics/claude-code \
  --fork-network google-gemini/gemini-cli \
  --max-fork-pages 1 \
  --output dist/cross-ecosystem-smoke.json \
  --force
```

## Result

| Upstream | Root count before and after | Records collected | Status |
| --- | ---: | ---: | --- |
| `openai/codex` | 19,087 | 100 | incomplete |
| `anthropics/claude-code` | 23,136 | 100 | incomplete |
| `google-gemini/gemini-cli` | 14,563 | 100 | incomplete |

All three networks produced normalized fork records and merged into snapshot
`registry-94059ba375d27dc7dc48`. The raw snapshot contained 300 records and had
SHA-256 digest
`62561f214815f774b73b1525857a7ce1880ab44b64979bac2ef32e952a9296ef`.

Every source correctly reported incomplete coverage because the one-page bound
stopped traversal before the root counts could reconcile. No repository was
cloned, imported, installed, or executed.

## Interpretation

This result supports one narrow claim: the existing fork collector and neutral
merge format are not hard-coded to the DeepSeek Harness upstream. It does not
show full ecosystem coverage, useful ranking, plugin-format compatibility, or
runtime portability. Strong generality evidence requires complete or sampled
collection protocols, source-specific plugin adapters, and runtime adapters for
at least two non-DSH tools.
