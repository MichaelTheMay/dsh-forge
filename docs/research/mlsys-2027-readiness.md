# MLSys 2027 submission readiness

Status: active work plan, not an acceptance forecast

## Venue fit and deadline

MLSys 2027 explicitly lists autonomous and agentic AI systems, testing,
debugging, monitoring, and ML tooling as topics. Research papers are judged on
novelty, quality, interest, and impact. The paper deadline is 30 October 2026 at
20:00 UTC. The research track is double blind and requires the official
two-column format, with at most 10 main-text pages excluding references.

Official source: <https://mlsys.org/Conferences/2027/CallForResearchPapers>

The public system report is not the conference submission. A research-track
submission must remove author names and affiliations, anonymize self-references
in good faith, and use the official MLSys style. A public technical report or
arXiv version is allowed by the venue policy.

## The acceptance-critical claim

The current implementation shows breadth, provenance, exposure diversity, and a
staged path from metadata to isolated execution. Those are meaningful systems
properties. They do not prove the central product thesis.

The primary conference claim should be:

> For a frozen agent-extension corpus, DSH Forge increases independently judged
> discovery precision over popularity ranking while retaining long-tail and
> owner diversity.

This claim is credible only after the confirmatory study succeeds under the
frozen protocol. If it does not, report the result and reposition the paper
around measurement, architecture, and failure analysis.

## Hard gates before submission

### 1. Independent ranking study

- Run a 25-item-per-arm pilot with reviewers who are not paper authors.
- Use the pilot only to refine instructions and the power calculation.
- Freeze the confirmatory snapshot, seed, exclusions, primary outcome, arm size,
  reviewer assignment, and analysis revision before collecting labels.
- Collect at least three independent ratings per candidate.
- Report uncertainty, arm overlap, rating distributions, and inter-rater
  agreement, including an inconclusive or negative result.

### 2. Real task utility

- Select a preregistered stratified sample from the rated candidates.
- Compare no extension, a popularity-selected extension, and a Forge-selected
  extension on fixed agentic development tasks.
- Record task completion, time, interventions, install success, startup success,
  rollback success, and resource use.
- Keep usefulness, compatibility, integrity, and containment as separate
  outcomes.

### 3. Generality beyond DSH

- Add complete metadata adapters for at least two other agentic development
  tools.
- Add at least one plugin-format or runtime adapter outside DSH.
- Measure code reused, adapter-specific code, ingest coverage, and unsupported
  assumptions. The existing 100-record smoke tests demonstrate parsing only.

### 4. Systems measurements

- Measure ingest throughput and API cost on frozen and changing networks.
- Measure catalog build time, size, query latency, and memory at multiple corpus
  scales.
- Measure time from source change to published feed.
- Exercise installation, startup, rollback, and concurrent local launches on a
  declared OS and Apptainer matrix.

### 5. Release and reproducibility

- Archive immutable snapshots, ballots, sealed keys, ledgers, results, and
  environment details.
- Provide a small offline dataset and one-command smoke reproduction.
- Pin the paper to the evaluated source revision and CI run.
- Choose and add a repository license before asking others to reuse the code.
- Add author identifiers and contact details only to the public report and final
  camera-ready version, not to the blinded submission.

## Implemented support

The repository now provides:

- checksum-verified study creation from a local snapshot or the public feed;
- a planning sample-size command with explicit assumptions;
- a blinded ballot and separately sealed answer key;
- deterministic reviewer subsets with exact overlap targets;
- a networkless single-file review interface;
- conflict-detecting merge of independent reviewer ledgers; and
- a benchmark that refuses incomplete review coverage and reports bootstrap
  intervals, ranking quality, long-tail yield, diversity, and ordinal agreement.

This closes the mechanics gap. It does not recruit reviewers, preregister the
study, generate genuine labels, or run real user tasks. Those human and empirical
steps now dominate the probability of acceptance.

## Honest readiness estimate

No implementation change can make conference acceptance 90 percent certain.
Reviewers compare the paper with an unknown submission pool, and the strongest
claims depend on results that do not exist yet. The current work is suitable as a
public system report and an evaluation platform. It becomes a competitive MLSys
research submission only after the independent ranking study, task-utility
study, cross-tool validation, and systems measurements are complete.
