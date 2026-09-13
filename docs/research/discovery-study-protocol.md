# Discovery study protocol

Status: implementation-ready protocol, not a completed experiment

## Research question

Does DSH Forge surface more genuinely useful, low-visibility extensions than
straightforward metadata baselines?

The primary comparison is Forge against popularity. Quality-only and recency
are diagnostic baselines. Query-dependent GitHub search and any upstream
marketplace ordering should be added in a second, separately specified study
because they require a task or query distribution.

## Hypotheses

- H1: Forge has higher expert-rated precision at the frozen arm size than popularity.
- H2: Forge has higher expert-rated NDCG at the frozen arm size than popularity.
- H3: Forge returns more relevant artifacts with at most 10 stars.
- H4: Forge reduces owner concentration without reducing expert-rated
  relevance.

H1 is the primary hypothesis. The other tests are secondary and should use a
declared multiple-comparison correction.

## Frozen inputs

Before collecting labels, publish or escrow:

- the exact catalog snapshot and its digest;
- the ranking-policy version;
- the study seed digest;
- the requested arm size;
- artifact exclusion rules;
- this protocol and its source revision; and
- the analysis script or notebook.

An admissible artifact must be public, unarchived, not known invalid, and bound
to a repository URL and immutable commit. This rule is independent of the Forge
candidate threshold. All ranking arms draw from the same admissible pool.

## Candidate construction and blinding

Use `research study-power` before the confirmatory run. Under the documented
planning assumptions of 0.40 baseline precision, a minimum detectable lift of
0.20, a two-sided alpha of 0.05, and 80 percent power, the independent
two-proportion approximation returns 97 candidates per arm. Use 25 candidates
per arm only for a separate pilot. Update the confirmatory calculation once,
using the pilot variance and observed arm overlap, then freeze it before labels
from the confirmatory snapshot are collected.

Use `research study-create` with the frozen arm size. It constructs separate
Forge, quality-only, popularity, and recency selections, takes their union, and
shuffles that union deterministically. A candidate can belong to more than one
arm.

The ballot excludes stars, update dates, Forge scores, visibility classes, and
arm membership. The answer key binds the full ballot digest and must be withheld
from reviewers and the person monitoring annotation progress. Repository names
and descriptions can still reveal well-known projects, so this is feature
blinding, not guaranteed identity blinding.

## Reviewers and assignments

Recruit practitioners who have built or operated agentic developer tooling.
Report their experience criteria and conflicts of interest. Authors may pilot
the rubric but should not provide labels used in the primary analysis.

Collect at least three independent ratings per artifact. Use `research
study-packet` with a reviewer index and reviewer count to produce deterministic,
balanced assignments. The assignment algorithm minimizes reviewer load and
pair-load imbalance. Verify exact candidate coverage before distributing the
files. Do not show prior ratings or permit discussion until the ledger is frozen.
Record abstentions separately from low relevance.

The target sample size must come from a power analysis before the confirmatory
run. The current 97-item result is a planning estimate, not a final guarantee of
power under overlapping selections and clustered reviewer judgments.

## Rating rubric

Reviewers answer one question: based on the provided metadata and pinned source,
how valuable would it be to investigate this artifact for real agentic
development work?

| Rating | Operational definition |
| --- | --- |
| Irrelevant, 0 | No concrete agentic-development use is evident. |
| Weak, 1 | A use is plausible, but evidence or differentiation is thin. |
| Promising, 2 | The artifact addresses a concrete workflow and merits hands-on evaluation. |
| Exceptional, 3 | The artifact appears unusually capable, useful, and difficult to discover through ordinary attention signals. |
| Abstain | The supplied evidence is insufficient, or the reviewer lacks relevant expertise. |

Each rating or abstention should include a short reason. An abstention is
recorded but does not count toward the minimum number of scored reviews.
Reviewers should judge potential
utility, not installation safety. Security and compatibility are separate
experiments.

## Analysis

Treat the mean rating for an artifact as graded relevance. Treat a mean of at
least 2 as relevant for precision. Report:

- precision at 10, 25, 100, and the full arm size;
- NDCG at 10, 25, 100, and the full arm size;
- relevant low-visibility yield at the full arm size;
- unique owners and maximum items per owner;
- rating coverage and abstention rate;
- exact agreement plus an ordinal inter-rater statistic;
- Forge-minus-baseline precision differences with arm overlap reported; and
- 95 percent confidence intervals from a deterministic artifact-level bootstrap.

Use `research study-merge` to combine independent exports. The benchmark must
fail if any artifact has fewer than the frozen minimum number of reviews. Report
every arm, every overlap, and the complete rating distribution. Correct secondary
hypothesis tests and include effect sizes. Unjudged artifacts must not silently
become negative labels in the confirmatory analysis.

## Follow-up utility study

Metadata relevance is not task utility. After the ranking study, select a
stratified set of highly rated artifacts and evaluate them in disposable
profiles on predefined tasks. Record installation success, startup success,
task completion, time, interventions, rollback, and resource use. Keep
integrity, compatibility, containment, and task quality as separate outcomes.

## Reproduction record

Archive the snapshot, blinded ballot, sealed answer key, frozen judgment ledger,
benchmark output, environment information, and source revision. Publishing a
negative or inconclusive result is part of the protocol. Do not change the
ranking policy, eligibility rule, or exclusions after revealing the key.

The command sequence is documented in
[the hidden-gem pipeline](../hidden-gem-pipeline.md). Study coordination and
key-handling steps are documented in
[independent reviewer operations](reviewer-operations.md).
