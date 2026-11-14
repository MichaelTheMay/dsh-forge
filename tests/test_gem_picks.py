import json
from pathlib import Path
import tempfile
import unittest

from dsh_forge.gem_picks import GemPicksError, apply_picks, load_picks


def pick(identity, **changes):
    base = {"artifact_id": identity, "score": 88.4, "confidence": "reviewed", "verdict": "gem",
            "summary": "Does one thing well.", "reasons": ["Worth a look.", "900 lines of its own code"]}
    base.update(changes)
    return base


def document(picks, **changes):
    base = {"schema": "dsh-forge.gem-picks/v1", "claims": {"executed": False, "security_verified": False}, "picks": picks}
    base.update(changes)
    return base


def candidate(identity, rank, kind="plugin"):
    return {"artifact": {"artifact_id": identity, "artifact_type": kind},
            "research": {"artifact_id": identity, "rank": rank, "reasons": ["Statistics reason"]}}


class LoadPicksTests(unittest.TestCase):
    def load(self, value):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "gem-picks.json"
            path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
            return load_picks(path)

    def test_loads_picks_in_rank_order_with_whole_number_scores(self):
        picks = self.load(document([pick("github:2"), pick("github:1", score=70, verdict=None, confidence="measured")]))
        self.assertEqual(list(picks), ["github:2", "github:1"])
        self.assertEqual(picks["github:2"]["score"], 88)
        self.assertIsNone(picks["github:1"]["verdict"])

    def test_pick_text_is_made_plain_and_bounded(self):
        picks = self.load(document([pick("github:1", summary="<b>Bold</b>\nclaim " + "x" * 400, reasons=["<script>x</script>", ""])]))
        self.assertTrue(picks["github:1"]["summary"].startswith("Bold claim"))
        self.assertEqual(len(picks["github:1"]["summary"]), 240)
        self.assertEqual(picks["github:1"]["reasons"], ["x"])

    def test_rejects_files_outside_the_contract(self):
        cases = [
            "{not json",
            document([], schema="other"),
            document([], claims={"executed": True, "security_verified": False}),
            document([pick("github:1"), pick("github:1")]),
            document([pick("github:1", score=140)]),
            document([pick("github:1", score=True)]),
            document([pick("github:1", confidence="trust me")]),
            document([pick("github:1", verdict="skip")]),
            document([pick("github:1", reasons="one string")]),
            document([pick("")]),
            document("nope"),
        ]
        for case in cases:
            with self.subTest(case=str(case)[:60]), self.assertRaises(GemPicksError):
                self.load(case)

    def test_a_missing_file_is_a_clear_error(self):
        with self.assertRaises(GemPicksError):
            load_picks("/nonexistent/gem-picks.json")


class ApplyPicksTests(unittest.TestCase):
    def test_picked_plugins_lead_and_the_rest_keep_their_order(self):
        queue = {"quality": {}, "candidates": [
            candidate("a", 1), candidate("b", 2), candidate("c", 3), candidate("d", 4),
            candidate("f1", 1, "fork"), candidate("f2", 2, "fork"),
        ]}
        picks = {"c": {"score": 90, "confidence": "reviewed", "verdict": "gem", "summary": "s", "reasons": ["Reviewer line"]},
                 "unknown": {"score": 80, "confidence": "measured", "verdict": None, "summary": "", "reasons": []},
                 "b": {"score": 70, "confidence": "measured", "verdict": None, "summary": "", "reasons": []}}
        self.assertEqual(apply_picks(queue, picks), 2)
        plugins = [(item["research"]["artifact_id"], item["research"]["rank"]) for item in queue["candidates"]
                   if item["artifact"]["artifact_type"] == "plugin"]
        self.assertEqual(sorted(plugins, key=lambda pair: pair[1]), [("c", 1), ("b", 2), ("a", 3), ("d", 4)])
        by_id = {item["research"]["artifact_id"]: item["research"] for item in queue["candidates"]}
        self.assertEqual(by_id["c"]["gem"]["rank"], 1)
        self.assertEqual(by_id["c"]["reasons"], ["Reviewer line"])
        # A pick without reasons keeps the statistics reasons.
        self.assertEqual(by_id["b"]["reasons"], ["Statistics reason"])
        self.assertNotIn("gem", by_id["a"])
        # Forks are untouched.
        self.assertEqual((by_id["f1"]["rank"], by_id["f2"]["rank"]), (1, 2))
        self.assertEqual(queue["quality"]["gem_picks"], {"schema": "dsh-forge.gem-picks/v1", "applied": 2})

    def test_no_picks_changes_nothing_and_clears_stale_gem_blocks(self):
        queue = {"candidates": [candidate("a", 1), candidate("b", 2)]}
        queue["candidates"][0]["research"]["gem"] = {"stale": True}
        self.assertEqual(apply_picks(queue, {}), 0)
        self.assertEqual([item["research"]["rank"] for item in queue["candidates"]], [1, 2])
        self.assertNotIn("gem", queue["candidates"][0]["research"])


if __name__ == "__main__":
    unittest.main()
