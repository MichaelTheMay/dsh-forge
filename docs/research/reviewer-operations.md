# Independent reviewer operations

This runbook turns the discovery protocol into a controlled annotation process.
It does not replace institutional research-ethics review. Before recruiting
people or collecting identifiable information, obtain the required determination
from the responsible institution.

## Roles

- The study coordinator freezes inputs, distributes packets, and monitors only
  completion counts.
- The key custodian stores the answer key separately and does not reveal arm
  membership until the ledger is frozen.
- Reviewers are practitioners who are not paper authors and do not discuss
  candidates during scoring.
- The analyst receives the frozen ballot, key, merged ledger, and analysis
  revision only after annotation closes.

One person may hold the coordinator and analyst roles. The key custodian should
be separate when practical.

## Before recruitment

1. Obtain the relevant ethics or IRB determination.
2. Define practitioner experience criteria and a conflict-of-interest policy.
3. Decide what reviewer information is necessary. Prefer study codes over names
   in exported ledgers.
4. Set compensation and time expectations consistently.
5. Freeze the pilot protocol without using pilot labels as confirmatory labels.

## Pilot

Use 25 candidates per arm. The pilot tests the instructions, packet usability,
review time, abstention rate, agreement, arm overlap, and plausible baseline
precision. It is not evidence for the primary conference claim.

After the pilot, make one documented update to the rubric and power calculation.
Do not tune the ranking policy against pilot labels unless the later confirmatory
study uses a new snapshot and declares that tuning.

## Confirmatory freeze

Archive these items before distributing a packet:

- protocol revision and source commit;
- source snapshot ID and checksums;
- study seed and requested arm size;
- blinded ballot digest;
- sealed answer key digest and custodian;
- reviewer count, assignment overlap, and exclusion rules;
- primary outcome, relevance threshold, confidence interval method, and
  secondary-test correction; and
- planned start and close times.

The packet command reports each file's SHA-256 digest. Record that digest and
which packet number was sent to each study code. Do not send the answer key, arm
labels, stars, dates, or Forge scores with a packet.

## Review instructions

Reviewers should use only the evidence displayed in the packet for the primary
metadata study. They should judge investigation value, not safety. A short reason
is required for each decision.

Use `abstain` when the evidence is insufficient or the artifact falls outside the
reviewer's expertise. Abstention is not a negative relevance label and does not
satisfy the required number of scored reviews. The coordinator must assign a
replacement review without showing earlier decisions.

## Close and analysis

1. Collect the exported JSON files and verify the expected snapshot ID.
2. Merge with `research study-merge`. Resolve a duplicate only from the reviewer's
   timestamped correction; never choose the more favorable rating.
3. Check that every candidate has the frozen number of scored reviews. The
   benchmark command fails if this condition is not met.
4. Freeze and checksum the merged ledger.
5. Release the answer key to the analyst.
6. Run the benchmark once with the preregistered options.
7. Publish the complete rating distribution, abstention count, agreement, arm
   overlap, effect sizes, intervals, exclusions, and deviations.

Negative and inconclusive results remain results. Do not change the seed,
eligibility rules, ranking policy, or relevance threshold after the key is opened.
