import tempfile
from pathlib import Path
import unittest

from dsh_forge.research import ResearchError, create_discovery_study
from dsh_forge.study_packet import assign_review_ballot, build_review_packet
from tests.test_research import plugin_record


class StudyPacketTests(unittest.TestCase):
    def ballot(self):
        record = plugin_record()
        record["description"] = "Useful memory workflow </script><script>throw new Error('unsafe')</script>"
        ballot, _ = create_discovery_study({
            "snapshot_id": "packet-source",
            "fetched_at": "2026-09-13T18:00:00Z",
            "supplemental_entries": [record],
        }, per_arm=1, seed="packet-test-seed")
        return ballot

    def test_packet_is_self_contained_blinded_and_escapes_embedded_json(self):
        rendered = build_review_packet(self.ballot())
        self.assertIn("connect-src 'none'", rendered)
        self.assertIn("dsh-forge.discovery-judgments/v2", rendered)
        self.assertIn("packet-source", rendered)
        self.assertIn("\\u003c/script\\u003e", rendered)
        self.assertNotIn("</script><script>throw", rendered)
        self.assertNotIn('"github_stars":', rendered)
        self.assertNotIn('"arms":', rendered)
        self.assertIn("Export rated JSON", rendered)

    def test_packet_rejects_an_unblinded_queue(self):
        ballot = self.ballot()
        ballot["candidates"][0]["artifact"]["github_stars"] = 2
        with self.assertRaisesRegex(ResearchError, "blinded current-policy"):
            build_review_packet(ballot)

    def test_balanced_assignment_gives_every_candidate_the_requested_overlap(self):
        record = plugin_record()
        records = [
            {
                **record,
                "artifact_id": f"github:{index + 1}",
                "owner": f"owner-{index}",
                "full_name": f"owner-{index}/plugin-{index}",
            }
            for index in range(20)
        ]
        ballot, _ = create_discovery_study({
            "snapshot_id": "assignment-source",
            "fetched_at": "2026-09-13T18:00:00Z",
            "supplemental_entries": records,
        }, per_arm=10, seed="assignment-test-seed")
        assigned = [
            assign_review_ballot(
                ballot, reviewer_index=index, reviewer_count=5, reviews_per_candidate=3
            )
            for index in range(1, 6)
        ]
        coverage = {
            candidate["artifact"]["artifact_id"]: 0
            for candidate in ballot["candidates"]
        }
        for subset in assigned:
            for candidate in subset["candidates"]:
                coverage[candidate["artifact"]["artifact_id"]] += 1
        self.assertEqual(set(coverage.values()), {3})
        loads = [subset["candidate_count"] for subset in assigned]
        self.assertLessEqual(max(loads) - min(loads), 1)


if __name__ == "__main__":
    unittest.main()
