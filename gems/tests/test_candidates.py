import gzip
import json
from pathlib import Path
import tempfile
import unittest

from gems.candidates import CandidateError, load_queue, select


def entry(name, *, score=90, stars=3, kind="plugin", archived=False, parent=None, candidate=True, sha="a" * 40):
    return {
        "artifact": {
            "artifact_id": f"github:{abs(hash(name)) % 10**9}",
            "artifact_type": kind,
            "full_name": name,
            "head_sha": sha,
            "github_stars": stars,
            "archived": archived,
            "parent_repository": parent,
            "description": "Does a thing",
            "package": {"name": name.split("/")[1]},
            "pushed_at": "2026-10-01T00:00:00Z",
        },
        "research": {
            "policy": "dsh-forge.hidden-gems/v3",
            "score": score,
            "rank": 1,
            "candidate": candidate,
            "capabilities": ["memory"],
            "confidence": "evidence",
            "reasons": ["Has tests and CI"],
        },
    }


class SelectTests(unittest.TestCase):
    def test_orders_by_stage_one_score_and_respects_the_limit(self):
        queue = {"candidates": [entry("a/low", score=60), entry("b/high", score=95), entry("c/mid", score=80)]}
        self.assertEqual([item["full_name"] for item in select(queue, limit=2)], ["b/high", "c/mid"])

    def test_drops_what_the_deep_stage_should_not_open(self):
        queue = {"candidates": [
            entry("a/archived", archived=True),
            entry("b/fork", parent="up/stream"),
            entry("c/famous", stars=5000),
            entry("d/blocked", candidate=False),
            entry("e/forktype", kind="fork"),
            entry("f/badsha", sha="not-a-commit"),
            entry("bad name/x"),
            entry("g/keeper"),
        ]}
        self.assertEqual([item["full_name"] for item in select(queue)], ["g/keeper"])

    def test_keeps_one_repository_per_owner(self):
        queue = {"candidates": [entry("Same/one", score=90), entry("same/two", score=99), entry("other/x", score=50)]}
        self.assertEqual([item["full_name"] for item in select(queue)], ["same/two", "other/x"])

    def test_candidate_carries_what_later_stages_need(self):
        chosen = select({"candidates": [entry("a/b", score=88, stars=4)]})[0]
        self.assertEqual(chosen["commit"], "a" * 40)
        self.assertEqual(chosen["stars"], 4)
        self.assertEqual(chosen["stage1"]["score"], 88)
        self.assertEqual(chosen["capabilities"], ["memory"])


class LoadQueueTests(unittest.TestCase):
    def test_reads_plain_and_gzipped_queues(self):
        queue = {"candidates": [entry("a/b")]}
        with tempfile.TemporaryDirectory() as root:
            plain = Path(root) / "queue.json"
            plain.write_text(json.dumps(queue), encoding="utf-8")
            packed = Path(root) / "queue.json.gz"
            with gzip.open(packed, "wt", encoding="utf-8") as handle:
                json.dump(queue, handle)
            self.assertEqual(len(load_queue(plain)["candidates"]), 1)
            self.assertEqual(len(load_queue(packed)["candidates"]), 1)

    def test_rejects_missing_and_malformed_queues(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(CandidateError):
                load_queue(Path(root) / "absent.json")
            broken = Path(root) / "broken.json"
            broken.write_text("{not json", encoding="utf-8")
            with self.assertRaises(CandidateError):
                load_queue(broken)
            shapeless = Path(root) / "shapeless.json"
            shapeless.write_text("{}", encoding="utf-8")
            with self.assertRaises(CandidateError):
                load_queue(shapeless)


if __name__ == "__main__":
    unittest.main()
