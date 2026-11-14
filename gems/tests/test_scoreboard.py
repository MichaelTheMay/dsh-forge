import json
from pathlib import Path
import tempfile
import unittest

from gems.eval import labels, scoreboard


def picks(names):
    return {"policy": "p", "generated_at": "t", "counts": {"reviewed": 2},
            "picks": [{"full_name": name, "score": 100 - index} for index, name in enumerate(names)]}


class LabelsTests(unittest.TestCase):
    def test_round_trip_and_case_insensitive_names(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "labels.json"
            self.assertEqual(labels.load(path), {})
            self.assertEqual(labels.save_one("Owner/Repo", True, by="m", at="2026-11-13", path=path), 1)
            self.assertEqual(labels.save_one("other/thing", False, by="m", at="2026-11-13", path=path), 2)
            self.assertEqual(labels.save_one("Owner/Repo", False, by="m", at="2026-11-14", path=path), 2)
            self.assertEqual(labels.load(path), {"owner/repo": False, "other/thing": False})

    def test_rejects_bad_names_and_foreign_files(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "labels.json"
            with self.assertRaises(ValueError):
                labels.save_one("../x", True, by="m", at="t", path=path)
            path.write_text(json.dumps({"schema": "other"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                labels.load(path)


class ScoreboardTests(unittest.TestCase):
    def test_scores_picks_against_labels(self):
        row = scoreboard.score(picks(["A/gem", "b/dud", "c/gem"]), {"a/gem": True, "b/dud": False, "c/gem": True, "z/missed": True})
        self.assertEqual(row["precision_at_10"], 0.667)
        self.assertEqual(row["labelled_in_top_10"], 3)
        # a>b, c<b, z (left out) < b: one win of three.
        self.assertEqual(row["label_agreement"], 0.333)
        self.assertNotIn("backtest_spearman", row)

    def test_backtest_columns_appear_when_given(self):
        backtest = {"rows": [{"score": s, "stars_gained": g, "took_off": g >= 5}
                             for s, g in [(9, 30), (8, 20), (3, 1), (2, 0), (1, 0)]]}
        row = scoreboard.score(picks([]), {}, backtest)
        self.assertEqual(row["backtest_repositories"], 5)
        self.assertEqual(row["backtest_took_off"], 2)
        self.assertEqual(row["backtest_agreement"], 1.0)
        self.assertGreater(row["backtest_spearman"], 0.9)
        self.assertIsNone(row["precision_at_10"])
        self.assertIn("backtest agreement     1.0", scoreboard.render(row))

    def test_history_and_render(self):
        row = scoreboard.score(picks(["a/b"]), {"a/b": True})
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "history.jsonl"
            scoreboard.append_history(row, "first", path)
            scoreboard.append_history(row, "second", path)
            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(line)["note"] for line in lines], ["first", "second"])
        self.assertIn("precision in top 10    1.0", scoreboard.render(row))


if __name__ == "__main__":
    unittest.main()
