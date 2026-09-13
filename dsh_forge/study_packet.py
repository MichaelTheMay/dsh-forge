"""Build a self-contained, networkless reviewer packet from a blinded ballot."""

from __future__ import annotations

from collections import Counter
import hashlib
from itertools import combinations
import json
from typing import Any, Mapping

from .research import (
    DISCOVERY_QUEUE_SCHEMA,
    JUDGMENT_SCHEMA,
    MAX_STUDY_PER_ARM,
    POLICY_VERSION,
    ResearchError,
)


_FORBIDDEN_KEYS = {"arms", "github_stars", "pushed_at", "quality_rank", "rank", "score", "visibility"}
_MAX_PACKET_CANDIDATES = MAX_STUDY_PER_ARM * 4


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            str(key) in _FORBIDDEN_KEYS or _contains_forbidden_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def build_review_packet(ballot: Mapping[str, Any]) -> str:
    """Return one inert HTML file that exports a compatible judgment ledger."""

    candidates = ballot.get("candidates")
    if (
        ballot.get("schema") != DISCOVERY_QUEUE_SCHEMA
        or ballot.get("policy") != POLICY_VERSION
        or not isinstance(ballot.get("snapshot_id"), str)
        or not isinstance(candidates, list)
        or not 1 <= len(candidates) <= _MAX_PACKET_CANDIDATES
        or not isinstance(ballot.get("quality"), Mapping)
        or ballot["quality"].get("blinded") is not True
        or _contains_forbidden_key(candidates)
    ):
        raise ResearchError("Review packet requires a blinded current-policy study ballot")
    identities: list[str] = []
    for candidate in candidates:
        artifact = candidate.get("artifact") if isinstance(candidate, Mapping) else None
        research = candidate.get("research") if isinstance(candidate, Mapping) else None
        identity = artifact.get("artifact_id") if isinstance(artifact, Mapping) else None
        if (
            not isinstance(identity, str)
            or not identity
            or not isinstance(research, Mapping)
            or set(research) != {"subject"}
            or not isinstance(research.get("subject"), Mapping)
        ):
            raise ResearchError("Review packet ballot contains an invalid candidate")
        identities.append(identity)
    if len(set(identities)) != len(identities):
        raise ResearchError("Review packet ballot contains duplicate candidates")

    payload = json.dumps(ballot, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    for character, escape in (("&", "u0026"), ("<", "u003c"), (">", "u003e")):
        payload = payload.replace(character, chr(92) + escape)
    return (
        _PAGE
        .replace("__JUDGMENT_SCHEMA__", JUDGMENT_SCHEMA)
        .replace("__BALLOT_JSON__", payload)
    )


def assign_review_ballot(
    ballot: Mapping[str, Any],
    *,
    reviewer_index: int,
    reviewer_count: int,
    reviews_per_candidate: int,
) -> dict[str, Any]:
    """Return one deterministic balanced reviewer subset without changing identity."""

    candidates = ballot.get("candidates")
    if (
        not isinstance(candidates, list)
        or not isinstance(reviewer_count, int)
        or isinstance(reviewer_count, bool)
        or not 2 <= reviewer_count <= 20
        or not isinstance(reviewer_index, int)
        or isinstance(reviewer_index, bool)
        or not 1 <= reviewer_index <= reviewer_count
        or not isinstance(reviews_per_candidate, int)
        or isinstance(reviews_per_candidate, bool)
        or not 1 <= reviews_per_candidate <= min(5, reviewer_count)
    ):
        raise ResearchError("Reviewer assignment requires a valid index, reviewer count, and overlap")
    blocks = list(combinations(range(1, reviewer_count + 1), reviews_per_candidate))
    reviewer_load: Counter[int] = Counter()
    pair_load: Counter[tuple[int, int]] = Counter()
    assignments: list[tuple[int, ...]] = []
    for index, candidate in enumerate(candidates):
        artifact = candidate.get("artifact") if isinstance(candidate, Mapping) else None
        identity = str(artifact.get("artifact_id") or index) if isinstance(artifact, Mapping) else str(index)

        def choice(block: tuple[int, ...]) -> tuple[Any, ...]:
            loads = [reviewer_load[item] for item in block]
            pairs = list(combinations(block, 2))
            digest = hashlib.sha256(
                f"{ballot.get('snapshot_id')}\n{identity}\n{block}".encode("utf-8")
            ).hexdigest()
            return (
                max(loads),
                sum(loads),
                max((pair_load[pair] for pair in pairs), default=0),
                sum(pair_load[pair] for pair in pairs),
                digest,
            )

        block = min(blocks, key=choice)
        assignments.append(block)
        reviewer_load.update(block)
        pair_load.update(combinations(block, 2))
    selected = [
        candidate
        for candidate, block in zip(candidates, assignments)
        if reviewer_index in block
    ]
    return {
        **dict(ballot),
        "candidate_count": len(selected),
        "candidates": selected,
        "assignment": {
            "method": "balanced-combination-cycle/v1",
            "reviewer_index": reviewer_index,
            "reviewer_count": reviewer_count,
            "reviews_per_candidate": reviews_per_candidate,
            "source_candidate_count": len(candidates),
        },
    }


_PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'none'; img-src data:; object-src 'none'; base-uri 'none'; form-action 'none'">
<title>DSH Forge blinded discovery review</title>
<style>
:root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; color: #17212b; background: #f4f5f6; }
* { box-sizing: border-box; }
body { margin: 0; }
button, input, textarea { font: inherit; }
button { cursor: pointer; }
.shell { min-height: 100vh; display: grid; grid-template-columns: 280px minmax(0, 1fr); }
aside { padding: 30px 24px; background: #17212b; color: #f7f8f8; }
aside h1 { margin: 0 0 8px; font-size: 20px; letter-spacing: -.02em; }
aside p { color: #b9c2c8; font-size: 13px; line-height: 1.55; }
.label { display: block; margin-top: 26px; color: #d6dde1; font-size: 12px; font-weight: 650; }
input { width: 100%; margin-top: 7px; padding: 10px 11px; border: 1px solid #52616b; border-radius: 5px; color: #fff; background: #222f3a; }
.progress { margin: 24px 0 8px; height: 7px; overflow: hidden; border-radius: 10px; background: #34434e; }
.bar { width: 0; height: 100%; background: #4fb6c2; }
.progress-text { color: #b9c2c8; font: 12px ui-monospace, SFMono-Regular, monospace; }
.aside-action { width: 100%; margin-top: 18px; padding: 10px; border: 1px solid #6bc2cb; border-radius: 5px; color: #fff; background: #087e8b; font-weight: 650; }
.aside-action:disabled { cursor: not-allowed; opacity: .45; }
.privacy { margin-top: 24px; padding-top: 18px; border-top: 1px solid #34434e; }
main { padding: 42px clamp(24px, 5vw, 76px); }
.topline { display: flex; justify-content: space-between; gap: 20px; color: #64717a; font: 12px ui-monospace, SFMono-Regular, monospace; }
.card { max-width: 850px; margin: 18px auto 0; padding: 34px; border: 1px solid #d4d9dc; background: #fff; box-shadow: 0 8px 24px rgba(23, 33, 43, .06); }
.kind { color: #087e8b; font: 650 12px ui-monospace, SFMono-Regular, monospace; text-transform: uppercase; letter-spacing: .08em; }
h2 { margin: 10px 0 7px; font-size: 28px; letter-spacing: -.025em; }
.identity { color: #66747d; font: 12px ui-monospace, SFMono-Regular, monospace; overflow-wrap: anywhere; }
.description { margin: 24px 0; font-size: 16px; line-height: 1.7; }
.facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1px; border: 1px solid #dce1e3; background: #dce1e3; }
.fact { min-height: 70px; padding: 12px; background: #f8f9f9; }
.fact b { display: block; margin-bottom: 7px; color: #68757d; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; }
.fact span { font-size: 13px; line-height: 1.5; overflow-wrap: anywhere; }
.rubric { margin-top: 30px; }
.rubric h3, .notes-label { font-size: 13px; }
.ratings { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.rating { padding: 12px 7px; border: 1px solid #b9c2c7; border-radius: 5px; color: #35434d; background: #fff; }
.rating.abstain { grid-column: 1 / -1; }
.rating strong { display: block; }
.rating small { display: block; margin-top: 4px; color: #748089; }
.rating.selected { border-color: #087e8b; color: #075e68; background: #eaf6f7; box-shadow: inset 0 0 0 1px #087e8b; }
.notes-label { display: block; margin-top: 22px; font-weight: 650; }
textarea { width: 100%; min-height: 90px; margin-top: 7px; padding: 11px; resize: vertical; border: 1px solid #b9c2c7; border-radius: 5px; line-height: 1.5; }
.nav { display: flex; justify-content: space-between; max-width: 850px; margin: 16px auto; }
.nav button { min-width: 110px; padding: 9px 14px; border: 1px solid #aeb8bd; border-radius: 5px; color: #293843; background: #fff; }
.nav button:disabled { opacity: .4; cursor: not-allowed; }
.message { min-height: 20px; margin-top: 9px; color: #ffcf70; font-size: 12px; line-height: 1.45; }
@media (max-width: 760px) {
  .shell { display: block; }
  aside { padding: 22px; }
  main { padding: 22px 14px; }
  .card { padding: 22px; }
  .ratings, .facts { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="shell">
<aside>
  <h1>Blinded discovery review</h1>
  <p>Judge investigation value from the evidence shown. Do not treat relevance as proof of safety or compatibility.</p>
  <label class="label" for="reviewer">Reviewer name or study code</label>
  <input id="reviewer" maxlength="128" autocomplete="off" placeholder="Required for export">
  <div class="progress" aria-hidden="true"><div class="bar" id="bar"></div></div>
  <div class="progress-text" id="progress"></div>
  <button class="aside-action" id="export" type="button">Export rated JSON</button>
  <div class="message" id="message" role="status"></div>
  <p class="privacy">This file makes no network requests. Ratings stay in this browser until you export them. The study key is not included.</p>
</aside>
<main>
  <div class="topline"><span id="position"></span><span id="snapshot"></span></div>
  <article class="card">
    <div class="kind" id="kind"></div>
    <h2 id="name"></h2>
    <div class="identity" id="identity"></div>
    <p class="description" id="description"></p>
    <div class="facts">
      <div class="fact"><b>Topics</b><span id="topics"></span></div>
      <div class="fact"><b>Package</b><span id="package"></span></div>
      <div class="fact"><b>License</b><span id="license"></span></div>
      <div class="fact"><b>Compatibility</b><span id="compatibility"></span></div>
    </div>
    <section class="rubric">
      <h3>How valuable would it be to investigate this artifact for real agentic development work?</h3>
      <div class="ratings" id="ratings">
        <button class="rating" data-rating="irrelevant" type="button"><strong>0: Irrelevant</strong><small>No concrete use</small></button>
        <button class="rating" data-rating="weak" type="button"><strong>1: Weak</strong><small>Plausible, thin evidence</small></button>
        <button class="rating" data-rating="promising" type="button"><strong>2: Promising</strong><small>Merits hands-on review</small></button>
        <button class="rating" data-rating="exceptional" type="button"><strong>3: Exceptional</strong><small>Unusually useful</small></button>
        <button class="rating abstain" data-rating="abstain" type="button"><strong>Abstain</strong><small>Insufficient evidence or relevant expertise</small></button>
      </div>
      <label class="notes-label" for="notes">Short reason</label>
      <textarea id="notes" maxlength="4000" placeholder="What makes this relevant or irrelevant?"></textarea>
    </section>
  </article>
  <nav class="nav" aria-label="Candidate navigation">
    <button id="previous" type="button">Previous</button>
    <button id="next" type="button">Next</button>
  </nav>
</main>
</div>
<script id="ballot-data" type="application/json">__BALLOT_JSON__</script>
<script>
"use strict";
const ballot = JSON.parse(document.getElementById("ballot-data").textContent);
const relevance = { irrelevant: 0, weak: 1, promising: 2, exceptional: 3, abstain: null };
const assignmentIndex = ballot.assignment && Number.isInteger(ballot.assignment.reviewer_index)
  ? ":reviewer-" + ballot.assignment.reviewer_index
  : ":full-ballot";
const storageKey = "dsh-forge-review:" + ballot.snapshot_id + assignmentIndex;
let index = 0;
let saved = {};
try { saved = JSON.parse(localStorage.getItem(storageKey) || "{}"); } catch (_) { saved = {}; }

const byId = id => document.getElementById(id);
const clean = value => typeof value === "string" && value.trim() ? value.trim() : "Not reported";
const list = value => Array.isArray(value) && value.length ? value.join(", ") : "Not reported";

function current() { return ballot.candidates[index]; }
function persist() {
  try { localStorage.setItem(storageKey, JSON.stringify(saved)); } catch (_) {}
}
function render() {
  const candidate = current();
  const artifact = candidate.artifact;
  const answer = saved[artifact.artifact_id] || {};
  byId("position").textContent = "Candidate " + (index + 1) + " of " + ballot.candidates.length;
  byId("snapshot").textContent = ballot.snapshot_id;
  byId("kind").textContent = clean(artifact.artifact_type);
  byId("name").textContent = clean(artifact.name || artifact.full_name);
  byId("identity").textContent = clean(artifact.full_name || artifact.artifact_id);
  byId("description").textContent = clean(artifact.description);
  byId("topics").textContent = list(artifact.topics || artifact.classifications);
  const packageData = artifact.package || {};
  byId("package").textContent = packageData.name ? packageData.name + (packageData.version ? "@" + packageData.version : "") : "Not reported";
  byId("license").textContent = clean((artifact.license || {}).spdx || artifact.license);
  byId("compatibility").textContent = clean((artifact.compatibility || {}).summary || artifact.compatibility);
  byId("notes").value = answer.notes || "";
  document.querySelectorAll(".rating").forEach(button => {
    button.classList.toggle("selected", button.dataset.rating === answer.rating);
  });
  byId("previous").disabled = index === 0;
  byId("next").disabled = index === ballot.candidates.length - 1;
  const rated = Object.values(saved).filter(value => value.rating in relevance).length;
  byId("progress").textContent = rated + " of " + ballot.candidates.length + " rated";
  byId("bar").style.width = (100 * rated / ballot.candidates.length) + "%";
}
function update(rating) {
  const identity = current().artifact.artifact_id;
  saved[identity] = {
    rating: rating,
    notes: byId("notes").value.trim(),
    reviewed_at: new Date().toISOString()
  };
  persist();
  render();
}
document.querySelectorAll(".rating").forEach(button => {
  button.addEventListener("click", () => update(button.dataset.rating));
});
byId("notes").addEventListener("input", event => {
  const identity = current().artifact.artifact_id;
  if (!saved[identity]) saved[identity] = { notes: "", reviewed_at: new Date().toISOString() };
  saved[identity].notes = event.target.value;
  persist();
});
byId("previous").addEventListener("click", () => { if (index > 0) { index -= 1; render(); } });
byId("next").addEventListener("click", () => { if (index + 1 < ballot.candidates.length) { index += 1; render(); } });
byId("export").addEventListener("click", () => {
  const reviewer = byId("reviewer").value.trim();
  const message = byId("message");
  if (reviewer.length < 2) { message.textContent = "Enter a reviewer name or study code first."; return; }
  const judgments = ballot.candidates.flatMap(candidate => {
    const answer = saved[candidate.artifact.artifact_id];
    if (!answer || !(answer.rating in relevance)) return [];
    return [{
      artifact_id: candidate.artifact.artifact_id,
      subject: candidate.research.subject,
      rating: answer.rating,
      relevance: relevance[answer.rating],
      reviewer: reviewer,
      reviewed_at: answer.reviewed_at,
      notes: answer.notes || ""
    }];
  });
  if (!judgments.length) { message.textContent = "Rate at least one candidate before exporting."; return; }
  const ledger = {
    schema: "__JUDGMENT_SCHEMA__",
    policy: ballot.policy,
    snapshot_id: ballot.snapshot_id,
    judgments: judgments,
    claims: { signed: false, executed: false, security_verified: false, installation_authorized: false }
  };
  const blob = new Blob([JSON.stringify(ledger, null, 2) + "\n"], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  const safeReviewer = reviewer.replace(/[^a-z0-9_-]+/gi, "-").replace(/^-+|-+$/g, "").slice(0, 64) || "reviewer";
  link.download = ballot.snapshot_id + "-" + safeReviewer.toLowerCase() + ".json";
  link.click();
  URL.revokeObjectURL(link.href);
  message.textContent = "Exported " + judgments.length + " ratings. Send the JSON file to the study coordinator.";
});
render();
</script>
</body>
</html>
"""
