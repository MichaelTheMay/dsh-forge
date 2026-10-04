"""Hidden-gem discovery v3: measured attention gap, gates, reasons, packs, and fallbacks."""

import datetime as dt
import math
import random
import unittest

from dsh_forge import discovery
from dsh_forge.analysis import select_fork_leads
from dsh_forge.enrichment import EVIDENCE_SCHEMA


NOW = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)


def iso(days_ago):
    return (NOW - dt.timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def plugin(index, *, quality, stars, name=None, description=None, owner=None, topics=(), **evidence_changes):
    """A plugin whose evidence scales with `quality` (0-1)."""
    evidence = {
        "schema": EVIDENCE_SCHEMA,
        "observed_at": iso(0),
        "created_at": iso(400),
        "pushed_at": iso(10),
        "has_tests": quality > 0.4,
        "ci_workflows": 1 if quality > 0.5 else 0,
        "readme_bytes": int(500 + 9000 * quality),
        "has_docs": quality > 0.6,
        "has_changelog": quality > 0.7,
        "releases": int(10 * quality),
        "commits_total": int(20 + 400 * quality),
        "commits_recent": int(40 * quality),
        "license": "MIT",
        "stars": stars,
    }
    evidence.update(evidence_changes)
    return {
        "artifact_id": f"github:{index}",
        "artifact_type": "plugin",
        "full_name": f"{owner or f'owner{index}'}/{name or f'plugin-{index}'}",
        "name": name or f"plugin-{index}",
        "owner": owner or f"owner{index}",
        "description": description or f"A DeepSeek Harness plugin number {index} that does useful things",
        "github_stars": stars,
        "pushed_at": iso(10),
        "license": {"spdx": "MIT"},
        "topics": list(topics),
        "evidence": evidence,
    }


def population(size=120, seed=7):
    """Stars follow build quality (so the model can learn it), with noise."""
    rng = random.Random(seed)
    records = []
    for index in range(size):
        quality = rng.random()
        stars = max(0, int(math.expm1(4.5 * quality + rng.gauss(0, 0.35))))
        records.append(plugin(1000 + index, quality=quality, stars=stars))
    return records


def snapshot(records):
    return {"snapshot_id": "registry-test", "fetched_at": iso(0), "entries": [], "supplemental_entries": records}


class RidgeTests(unittest.TestCase):
    def test_recovers_a_linear_relationship(self):
        rng = random.Random(1)
        rows = [[rng.random(), rng.random()] for _ in range(200)]
        targets = [3 * a - 2 * b + 1 for a, b in rows]
        model = discovery.Ridge(penalty=0.01).fit(rows, targets)
        self.assertAlmostEqual(model.predict([0.5, 0.5]), 1.5, places=1)
        self.assertGreater(model.weights[0], 0)
        self.assertLess(model.weights[1], 0)

    def test_constant_feature_does_not_break_the_fit(self):
        rows = [[1.0, float(index)] for index in range(50)]
        model = discovery.Ridge().fit(rows, [float(index) for index in range(50)])
        self.assertTrue(math.isfinite(model.predict([1.0, 10.0])))

    def test_percentiles_and_spearman(self):
        self.assertEqual(discovery.percentiles([3, 1, 2]), [1.0, 0.0, 0.5])
        self.assertEqual(discovery.percentiles([5, 5]), [0.5, 0.5])
        self.assertAlmostEqual(discovery.spearman([1, 2, 3, 4], [10, 20, 30, 40]), 1.0)
        self.assertAlmostEqual(discovery.spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)


class AttentionModelTests(unittest.TestCase):
    def test_model_is_cross_validated_and_finds_the_underrated_plugin(self):
        records = population()
        gem = plugin(1, quality=0.97, stars=1, name="dsh-memory-vault", topics=["memory"])
        famous = plugin(2, quality=0.97, stars=400, name="dsh-famous")
        records += [gem, famous]
        reports, validation = discovery.score_records(records, NOW)
        self.assertEqual(validation["status"], "fitted")
        self.assertEqual(validation["ranking"], "attention-model")
        self.assertGreater(validation["cross_validation"]["spearman"], 0.5)
        self.assertEqual(validation["cross_validation"]["folds"], discovery.CV_FOLDS)
        gem_report = reports["github:1"]
        self.assertFalse(gem_report["blocked_by"])
        self.assertGreaterEqual(gem_report["built_percentile"], 90)
        self.assertGreater(gem_report["predicted_stars"], 10)
        self.assertTrue(gem_report["reasons"][0].startswith("Built like projects that usually have ~"))
        # The famous plugin is just as well built but is not hidden.
        self.assertIn("already well known", reports["github:2"]["blocked_by"])
        self.assertGreater(gem_report["score"], reports["github:2"]["score"] - 1)

    def test_weak_model_falls_back_to_an_equal_weight_craft_index(self):
        rng = random.Random(3)
        # Stars unrelated to build quality: no honest "projects like this get N stars" claim.
        records = [plugin(2000 + index, quality=rng.random(), stars=rng.randint(0, 40)) for index in range(120)]
        records.append(plugin(3, quality=0.99, stars=0))
        reports, validation = discovery.score_records(records, NOW)
        self.assertEqual(validation["ranking"], "craft-index")
        report = reports["github:3"]
        self.assertIsNone(report["predicted_stars"])
        self.assertFalse(any(reason.startswith("Built like projects") for reason in report["reasons"]))
        self.assertGreaterEqual(report["built_percentile"], 90)

    def test_too_few_plugins_skip_the_model(self):
        model, validation = discovery.fit_attention(population(size=10), NOW)
        self.assertIsNone(model)
        self.assertEqual(validation["status"], "insufficient_evidence")

    def test_hidden_ceiling_follows_the_data_within_bounds(self):
        low = [plugin(index, quality=0.5, stars=1) for index in range(100)]
        self.assertEqual(discovery.hidden_ceiling(low), discovery.MIN_HIDDEN_CEILING)
        high = [plugin(index, quality=0.5, stars=10_000) for index in range(100)]
        self.assertEqual(discovery.hidden_ceiling(high), discovery.HIDDEN_STAR_CEILING)


class GateTests(unittest.TestCase):
    def test_gates_name_each_disqualifier(self):
        base = plugin(5, quality=0.9, stars=1)
        self.assertEqual(discovery._gate(base, base["evidence"], NOW), [])
        archived = {**base, "archived": True}
        self.assertIn("archived", discovery._gate(archived, archived["evidence"], NOW))
        unlicensed = plugin(6, quality=0.9, stars=1, license=None)
        unlicensed["license"] = {}
        self.assertIn("no license", discovery._gate(unlicensed, unlicensed["evidence"], NOW))
        stale = plugin(7, quality=0.9, stars=1, pushed_at=iso(500))
        stale["pushed_at"] = iso(500)
        self.assertIn("not updated in the last year", discovery._gate(stale, stale["evidence"], NOW))
        vague = plugin(8, quality=0.9, stars=1, description="tool")
        self.assertIn("no description", discovery._gate(vague, vague["evidence"], NOW))

    def test_short_readme_and_weak_build_are_not_gems(self):
        records = population()
        records.append(plugin(9, quality=0.97, stars=0, readme_bytes=200))
        records.append(plugin(10, quality=0.05, stars=0))
        reports, _ = discovery.score_records(records, NOW)
        self.assertIn("README too short", reports["github:9"]["blocked_by"])
        self.assertIn("below the quality bar", reports["github:10"]["blocked_by"])


def fork(index, *, ahead, parent="deepseek-ai/deepseek-harness", description=None, pushed=5, surfaces=("plugin runtime",)):
    return {
        "artifact_id": f"github:{index}",
        "artifact_type": "fork",
        "full_name": f"forker{index}/deepseek-harness",
        "name": "deepseek-harness",
        "owner": f"forker{index}",
        "description": description or "DeepSeek Harness: Everything is a Plugin.",
        "github_stars": 0,
        "pushed_at": iso(pushed),
        "created_at": iso(200),
        "license": {"spdx": "MIT"},
        "source_repository": "deepseek-ai/deepseek-harness",
        "parent_repository": parent,
        "divergence": {"ahead_by": ahead, "behind_by": 3, "listed_file_count": 12, "status": "diverged"},
        "compatibility": {"changed_surfaces": list(surfaces)},
    }


class ForkTests(unittest.TestCase):
    def test_forks_are_judged_on_their_own_changes(self):
        records = [
            fork(20, ahead=40, description="Adds a native Windows shell and a plugin marketplace browser"),
            fork(21, ahead=1),
            fork(22, ahead=60, parent="someone/deepseek-harness"),
        ]
        reports, _ = discovery.score_records(records, NOW)
        self.assertGreater(reports["github:20"]["score"], reports["github:21"]["score"])
        self.assertTrue(reports["github:20"]["reasons"][0].startswith("Adds 40 commits on top of DeepSeek Harness"))
        # A fork of a fork can't borrow its parent's commits.
        self.assertIn("copy of another fork", reports["github:22"]["blocked_by"])
        self.assertTrue(any(reason.startswith("Updated in ") for reason in reports["github:20"]["reasons"]))

    def test_fork_leads_skip_untouched_copies(self):
        untouched = fork(30, ahead=0)
        untouched.pop("divergence")
        untouched["pushed_at"] = untouched["created_at"]
        worked = fork(31, ahead=0, description="My own take on the harness with offline mode")
        worked.pop("divergence")
        starred = fork(32, ahead=0)
        starred.pop("divergence")
        starred["github_stars"] = 4
        copy_of_copy = fork(33, ahead=0, parent="someone/deepseek-harness")
        copy_of_copy.pop("divergence")
        snap = {"entries": [untouched, worked, starred, copy_of_copy], "supplemental_entries": []}
        leads = select_fork_leads(snap, limit=10)
        self.assertNotIn("github:30", leads)
        self.assertIn("github:31", leads)
        self.assertIn("github:32", leads)
        # The penalised fork of a fork ranks after the others when included at all.
        if "github:33" in leads:
            self.assertGreater(leads.index("github:33"), leads.index("github:31"))


class PackTests(unittest.TestCase):
    def test_packs_fill_roles_with_one_plugin_per_owner_and_distinct_notes(self):
        records = population()
        records += [
            plugin(40, quality=0.95, stars=3, name="dsh-memory-store", topics=["memory"]),
            plugin(41, quality=0.93, stars=2, name="dsh-repo-map", description="Builds a repository map and code index for your codebase so agents find symbols", topics=["codebase"]),
            plugin(42, quality=0.92, stars=4, name="dsh-web-search", topics=["search"]),
            plugin(43, quality=0.94, stars=1, name="dsh-code-review", topics=["review"]),
            plugin(44, quality=0.91, stars=2, name="dsh-security-audit", topics=["security"]),
            plugin(45, quality=0.9, stars=5, name="dsh-test-runner", topics=["testing"]),
            plugin(46, quality=0.9, stars=1, name="dsh-agent-orchestration", topics=["orchestration"]),
            plugin(47, quality=0.9, stars=3, name="dsh-trace-dashboard", topics=["observability"]),
        ]
        queue = discovery.discovery_queue(snapshot(records))
        packs = {pack["id"]: pack for pack in queue["packs"]}
        self.assertIn("memory-and-context", packs)
        self.assertIn("review-and-safety", packs)
        for pack in packs.values():
            owners = [member["owner"] for member in pack["members"]]
            self.assertEqual(len(owners), len(set(owners)))
            self.assertGreaterEqual(len(pack["members"]), 3)
            kinds = [discovery._reason_kind(member["why"]) for member in pack["members"]]
            self.assertEqual(len(kinds), len(set(kinds)), pack["members"])
        memory = packs["memory-and-context"]["members"]
        self.assertEqual(memory[0]["role"], "Memory")
        self.assertEqual(memory[0]["name"], "dsh-memory-store")

    def test_loose_mentions_do_not_make_a_primary_capability(self):
        once = plugin(50, quality=0.9, stars=1, name="dsh-formatter", description="Formats code. Keeps context small.")
        self.assertNotIn("memory", discovery.primary_capabilities(once))
        named = plugin(51, quality=0.9, stars=1, name="dsh-memory", description="Search your notes")
        self.assertEqual(discovery.primary_capabilities(named)[0], "memory")


class QueueTests(unittest.TestCase):
    def test_queue_publishes_v3_candidates_with_reasons_and_annotates_the_registry(self):
        records = population()
        records.append(plugin(60, quality=0.98, stars=0, name="dsh-quiet-gem"))
        snap = snapshot(records)
        queue = discovery.discovery_queue(snap)
        self.assertEqual(queue["policy"], discovery.POLICY)
        self.assertGreater(queue["candidate_count"], 0)
        model = queue["quality"]["discovery"]["attention_model"]
        self.assertIn("hidden_star_ceiling", model)
        for item in queue["candidates"]:
            research = item["research"]
            self.assertTrue(research["candidate"])
            self.assertTrue(research["reasons"])
            self.assertFalse(research["security_verified"])
            # Signed snapshots reject floats.
            self.assertFalse(isinstance(research["predicted_stars"], float))
        annotated = discovery.annotate(snap, queue)
        self.assertEqual(annotated, queue["candidate_count"])
        self.assertEqual(snap["discovery_policy"], discovery.POLICY)
        marked = [record for record in records if "discovery" in record]
        self.assertEqual(len(marked), annotated)

    def test_without_evidence_the_queue_falls_back_to_the_metadata_policy(self):
        records = population(size=60)
        for record in records:
            record.pop("evidence")
        queue = discovery.discovery_queue(snapshot(records))
        self.assertNotEqual(queue["policy"], discovery.POLICY)
        self.assertEqual(queue["quality"]["discovery"]["fallback"], "too little evidence")
        self.assertEqual(queue["packs"], [])


if __name__ == "__main__":
    unittest.main()
