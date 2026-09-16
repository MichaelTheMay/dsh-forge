"""Tests for deterministic catalog enrichment."""

from __future__ import annotations

import unittest

from dsh_forge.enrichment import (
    BOILERPLATE_SHARE,
    build_facets,
    derive_tags,
    differentiation,
    enrich_record,
    enrich_snapshot,
    flatten_tags,
    primary_capability,
)


def plugin(**overrides):
    record = {
        "artifact_id": "github:1",
        "artifact_type": "plugin",
        "name": "dsh-memory",
        "description": "Persistent memory and semantic search over your codebase via MCP.",
        "topics": ["deepseek-harness", "memory", "mcp"],
        "language": "TypeScript",
        "license": {"spdx": "MIT"},
        "github_stars": 12,
        "pushed_at": "2026-09-01T00:00:00Z",
        "package": {"name": "dsh-memory", "version": "1.2.0"},
    }
    record.update(overrides)
    return record


class DeriveTagsTests(unittest.TestCase):
    def test_tags_come_from_the_records_own_words(self):
        families = derive_tags(plugin(), observed_at="2026-09-15T00:00:00Z")
        self.assertIn("memory", families["capability"])
        self.assertIn("search", families["capability"])
        self.assertIn("mcp", families["integration"])

    def test_tagging_is_deterministic(self):
        record = plugin()
        first = derive_tags(record, observed_at="2026-09-15T00:00:00Z")
        second = derive_tags(dict(record), observed_at="2026-09-15T00:00:00Z")
        self.assertEqual(first, second)

    def test_unrelated_words_do_not_produce_tags(self):
        families = derive_tags(
            plugin(name="wallpapers", description="A wallpaper collection.", topics=[], package=None),
            observed_at="2026-09-15T00:00:00Z",
        )
        self.assertNotIn("capability", families)
        self.assertNotIn("integration", families)

    def test_the_repository_name_is_evidence_too(self):
        families = derive_tags(
            plugin(name="dsh-memory", description="A wallpaper collection.", topics=[], package=None),
            observed_at="2026-09-15T00:00:00Z",
        )
        self.assertIn("memory", families["capability"])

    def test_substrings_do_not_match_across_word_boundaries(self):
        # "testing" must not be triggered by "latest", nor "git" by "digit".
        families = derive_tags(
            plugin(description="The latest digit formatter.", topics=[], package=None, language="Go"),
            observed_at="2026-09-15T00:00:00Z",
        )
        self.assertNotIn("testing", families.get("capability", []))
        self.assertNotIn("git", families.get("integration", []))

    def test_hyphenated_topics_still_match(self):
        families = derive_tags(
            plugin(description="", topics=["multi-agent", "model-context-protocol"], package=None),
            observed_at="2026-09-15T00:00:00Z",
        )
        self.assertIn("orchestration", families["capability"])
        self.assertIn("mcp", families["integration"])

    def test_maturity_reflects_recency_licence_and_visibility(self):
        families = derive_tags(plugin(), observed_at="2026-09-15T00:00:00Z")
        self.assertIn("actively-maintained", families["maturity"])
        self.assertIn("has-license", families["maturity"])
        self.assertIn("pinned-release", families["maturity"])
        self.assertIn("low-visibility", families["maturity"])

    def test_archived_replaces_actively_maintained(self):
        families = derive_tags(plugin(archived=True), observed_at="2026-09-15T00:00:00Z")
        self.assertIn("archived", families["maturity"])
        self.assertNotIn("actively-maintained", families["maturity"])

    def test_a_popular_record_is_not_a_hidden_gem(self):
        families = derive_tags(plugin(github_stars=5000), observed_at="2026-09-15T00:00:00Z")
        self.assertIn("well-known", families["maturity"])
        self.assertNotIn("low-visibility", families["maturity"])

    def test_missing_license_drops_the_licence_tag(self):
        for value in ({"spdx": "NOASSERTION"}, {"spdx": ""}, None):
            families = derive_tags(plugin(license=value), observed_at="2026-09-15T00:00:00Z")
            self.assertNotIn("has-license", families.get("maturity", []))

    def test_flatten_is_stable_and_deduplicated(self):
        families = {"capability": ["memory"], "integration": ["mcp"], "maturity": ["memory"]}
        self.assertEqual(flatten_tags(families), ["memory", "mcp"])

    def test_primary_capability_is_empty_without_one(self):
        self.assertEqual(primary_capability({}), "")
        self.assertEqual(primary_capability({"capability": ["review", "search"]}), "review")


class DifferentiationTests(unittest.TestCase):
    boilerplate = frozenset({"deepseek harness: everything is a plugin.", ""})

    def test_an_unmodified_clone_is_not_differentiated(self):
        record = {
            "description": "DeepSeek Harness: Everything is a Plugin.",
            "topics": [],
            "github_stars": 0,
        }
        result = differentiation(record, self.boilerplate)
        self.assertFalse(result["differentiated"])
        self.assertEqual(result["signals"], [])

    def test_its_own_description_differentiates_a_fork(self):
        record = {"description": "Adds Kafka-backed multi-user sessions.", "topics": [], "github_stars": 0}
        result = differentiation(record, self.boilerplate)
        self.assertTrue(result["differentiated"])
        self.assertIn("own-description", result["signals"])

    def test_divergence_differentiates_even_with_an_inherited_description(self):
        record = {
            "description": "DeepSeek Harness: Everything is a Plugin.",
            "topics": [],
            "github_stars": 0,
            "divergence": {"ahead_by": 7},
        }
        result = differentiation(record, self.boilerplate)
        self.assertTrue(result["differentiated"])
        self.assertIn("diverged-from-upstream", result["signals"])

    def test_zero_commits_ahead_is_not_divergence(self):
        record = {
            "description": "DeepSeek Harness: Everything is a Plugin.",
            "topics": [],
            "github_stars": 0,
            "divergence": {"ahead_by": 0},
        }
        self.assertFalse(differentiation(record, self.boilerplate)["differentiated"])

    def test_a_couple_of_stars_is_not_attention(self):
        base = {"description": "DeepSeek Harness: Everything is a Plugin.", "topics": []}
        self.assertFalse(differentiation({**base, "github_stars": 2}, self.boilerplate)["differentiated"])
        self.assertTrue(differentiation({**base, "github_stars": 3}, self.boilerplate)["differentiated"])


class SnapshotTests(unittest.TestCase):
    def snapshot(self):
        # One real fork among many clones, mirroring the published corpus.
        clones = [
            {
                "artifact_id": f"github:{index}",
                "artifact_type": "fork",
                "name": "deepseek-harness",
                "description": "DeepSeek Harness: Everything is a Plugin.",
                "topics": [],
                "github_stars": 0,
                "pushed_at": "2026-09-01T00:00:00Z",
                "license": {"spdx": "MIT"},
            }
            for index in range(200)
        ]
        real = {
            "artifact_id": "github:999",
            "artifact_type": "fork",
            "name": "harness-kafka",
            "description": "Multi-user DeepSeek Harness with Kafka and Redis session fan-out.",
            "topics": ["kafka"],
            "github_stars": 40,
            "pushed_at": "2026-09-10T00:00:00Z",
            "license": {"spdx": "Apache-2.0"},
        }
        return {
            "completed_at": "2026-09-15T00:00:00Z",
            "entries": [*clones, real],
            "supplemental_entries": [plugin()],
            "package_entries": [],
        }

    def test_every_record_is_tagged_and_the_clones_are_marked(self):
        snapshot = self.snapshot()
        counts = enrich_snapshot(snapshot)
        self.assertEqual(counts["records"], 202)
        self.assertEqual(counts["coverage"], 1.0)
        # Only the distinctive fork and the plugin carry signal.
        self.assertEqual(counts["differentiated"], 2)
        self.assertEqual(counts["boilerplate"], 200)

    def test_inherited_descriptions_are_detected_per_corpus(self):
        # The plugin reuses wording that is boilerplate among forks, but it is
        # judged against the plugin corpus, so it stays differentiated.
        snapshot = self.snapshot()
        snapshot["supplemental_entries"] = [
            plugin(description="DeepSeek Harness: Everything is a Plugin.")
        ]
        enrich_snapshot(snapshot)
        self.assertTrue(snapshot["supplemental_entries"][0]["enrichment"]["differentiated"])
        self.assertFalse(snapshot["entries"][0]["enrichment"]["differentiated"])

    def test_enrichment_never_claims_the_code_was_examined(self):
        record = enrich_record(plugin(), observed_at="2026-09-15T00:00:00Z")
        self.assertEqual(
            record["claims"],
            {"executed": False, "code_inspected": False, "metadata_only": True},
        )

    def test_enriching_twice_changes_nothing(self):
        first, second = self.snapshot(), self.snapshot()
        enrich_snapshot(first)
        enrich_snapshot(second)
        enrich_snapshot(second)
        self.assertEqual(first["entries"], second["entries"])

    def test_facet_counts_match_the_records_that_carry_the_tag(self):
        snapshot = self.snapshot()
        enrich_snapshot(snapshot)
        facets = build_facets(snapshot)
        fork_tags = dict(facets["facets"]["fork"]["tag"])
        tagged = sum(
            1 for record in snapshot["entries"]
            if "has-license" in record["enrichment"]["tags"]
        )
        self.assertEqual(fork_tags["has-license"], tagged)
        self.assertEqual(dict(facets["facets"]["fork"]["license"])["MIT"], 200)

    def test_an_empty_corpus_does_not_divide_by_zero(self):
        snapshot = {"entries": [], "supplemental_entries": [], "package_entries": []}
        counts = enrich_snapshot(snapshot)
        self.assertEqual(counts["records"], 0)
        self.assertEqual(counts["coverage"], 0.0)
        self.assertEqual(counts["differentiated_share"], 0.0)
        self.assertEqual(build_facets(snapshot)["facets"], {})

    def test_boilerplate_share_stays_a_small_fraction(self):
        self.assertLess(BOILERPLATE_SHARE, 0.05)


if __name__ == "__main__":
    unittest.main()
