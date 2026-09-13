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

- H1: Forge has higher expert-rated precision at 25 than popularity.
- H2: Forge has higher expert-rated NDCG at 25 than popularity.
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

Use `research study-create` with 25 candidates per arm. It constructs separate
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

Collect at least three independent ratings per artifact. Randomize assignments
with balanced overlap so every pair of reviewers shares some artifacts. Do not
show prior ratings or permit discussion until the ledger is frozen. Record
abstentions separately from low relevance.

The target sample size must come from a power analysis before the confirmatory
run. A 25-item arm is suitable for a pilot, not automatically sufficient for a
conference claim.

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

Each rating should include a short reason. Reviewers should judge potential
utility, not installation safety. Security and compatibility are separate
experiments.

## Analysis

Treat the mean rating for an artifact as graded relevance. Treat a mean of at
least 2 as relevant for precision. Report:

- precision at 10 and 25;
- NDCG at 10 and 25;
- relevant low-visibility yield at 25;
- unique owners and maximum items per owner;
- rating coverage and abstention rate;
- exact agreement plus an ordinal inter-rater statistic;
- paired differences for artifacts shared by two arms; and
- 95 percent confidence intervals from an artifact-level bootstrap.

Report every arm, every overlap, and the complete rating distribution. Correct
secondary hypothesis tests and include effect sizes. Unjudged artifacts should
not silently become negative labels in the confirmatory analysis.

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
[the hidden-gem pipeline](../hidden-gem-pipeline.md).
