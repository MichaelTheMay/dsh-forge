import gzip
import json
from pathlib import Path
import tempfile
import unittest

from gems.eval import backtest, scoreboard
from gems.fetch import FetchError


def registry(root, name, records, fetched_at):
    path = Path(root) / name
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump({"fetched_at": fetched_at, "supplemental_entries": records, "entries": []}, handle)
    return path


def record(name, stars, sha="a" * 40, **changes):
    base = {"artifact_type": "plugin", "full_name": name, "github_stars": stars, "head_sha": sha,
            "archived": False, "parent_repository": None}
    base.update(changes)
    return base


class OutcomeTests(unittest.TestCase):
    def test_loads_only_live_original_plugins(self):
        with tempfile.TemporaryDirectory() as root:
            path = registry(root, "r.json.gz", [
                record("A/Ok", 3), record("b/archived", 1, archived=True), record("c/fork", 1, parent_repository="x/y"),
                record("d/fork-type", 1, artifact_type="fork"), record("bad name", 1), record("e/nostars", None),
            ], "2026-10-15T15:00:00Z")
            plugins, date = backtest.load_plugins(path)
        self.assertEqual(plugins, {"a/ok": {"full_name": "A/Ok", "stars": 3, "commit": "a" * 40}})
        self.assertEqual(date, "2026-10-15")

    def test_outcomes_cover_plugins_that_were_obscure_and_still_exist(self):
        then = {"a/rose": {"full_name": "a/rose", "stars": 2, "commit": "a" * 40},
                "b/flat": {"full_name": "b/flat", "stars": 0, "commit": "b" * 40},
                "c/famous": {"full_name": "c/famous", "stars": 500, "commit": "c" * 40},
                "d/gone": {"full_name": "d/gone", "stars": 1, "commit": "d" * 40},
                "e/nocommit": {"full_name": "e/nocommit", "stars": 1, "commit": ""}}
        now = {"a/rose": {"stars": 30}, "b/flat": {"stars": 0}, "c/famous": {"stars": 900}, "e/nocommit": {"stars": 9}}
        self.assertEqual(backtest.outcomes(then, now), [
            {"full_name": "a/rose", "commit_then": "a" * 40, "stars_then": 2, "stars_gained": 28},
            {"full_name": "b/flat", "commit_then": "b" * 40, "stars_then": 0, "stars_gained": 0},
        ])

    def test_sample_is_repeatable_and_takes_both_kinds(self):
        rows = [{"full_name": f"o{index}/r", "stars_gained": 9 if index % 10 == 0 else 0} for index in range(300)]
        first = backtest.sample(rows, took_off=5, others=20, seed=1)
        self.assertEqual(first, backtest.sample(rows, took_off=5, others=20, seed=1))
        self.assertNotEqual(first, backtest.sample(rows, took_off=5, others=20, seed=2))
        self.assertEqual(sum(1 for row in first if row["stars_gained"] >= backtest.TOOK_OFF), 5)
        self.assertEqual(len(first), 25)


class CollectTests(unittest.TestCase):
    def test_a_holdout_leaves_out_repositories_used_before(self):
        def fetch(name, commit, destination):
            root = Path(destination)
            root.mkdir(parents=True)
            (root / "index.js").write_text("const a = 1;\n" * 50, encoding="utf-8")
            return root

        with tempfile.TemporaryDirectory() as root:
            then = registry(root, "then.json.gz", [record("a/one", 1), record("b/two", 1), record("c/three", 1)], "2026-10-15T00:00:00Z")
            now = registry(root, "now.json.gz", [record("a/one", 9), record("b/two", 1), record("c/three", 1)], "2026-11-10T00:00:00Z")
            dataset = backtest.collect(then, now, Path(root) / "work", exclude=["A/One", "c/three"], fetch=fetch)
        self.assertEqual([row["full_name"] for row in dataset["rows"]], ["b/two"])
        self.assertEqual((dataset["excluded"], dataset["population"]), (2, 1))

    def test_measures_the_older_code_and_scores_it(self):
        fetched = []

        def fetch(name, commit, destination):
            fetched.append((name, commit))
            if name == "c/broken":
                raise FetchError("gone")
            root = Path(destination)
            root.mkdir(parents=True)
            (root / "package.json").write_text(json.dumps({"dsh": {"x": 1}, "main": "index.js"}), encoding="utf-8")
            (root / "index.js").write_text("const a = 1;\n" * (400 if name == "a/big" else 50), encoding="utf-8")
            return root

        with tempfile.TemporaryDirectory() as root:
            then = registry(root, "then.json.gz", [
                record("a/big", 1, "1" * 40), record("b/small", 1, "2" * 40), record("c/broken", 0, "3" * 40),
            ], "2026-10-15T00:00:00Z")
            now = registry(root, "now.json.gz", [
                record("a/big", 12, "9" * 40), record("b/small", 1, "9" * 40), record("c/broken", 0, "9" * 40),
            ], "2026-11-10T00:00:00Z")
            dataset = backtest.collect(then, now, Path(root) / "work", fetch=fetch)
            self.assertEqual(list((Path(root) / "work").glob("*")), [])
        self.assertEqual((dataset["then"], dataset["now"]), ("2026-10-15", "2026-11-10"))
        self.assertEqual((dataset["population"], dataset["population_took_off"]), (3, 1))
        self.assertEqual(dataset["excluded"], 0)
        self.assertEqual([row["full_name"] for row in dataset["rows"]], ["a/big", "b/small"])
        # The code is fetched as it was then, not as it is now.
        self.assertIn(("a/big", "1" * 40), fetched)
        self.assertNotIn("fingerprints", dataset["rows"][0]["inspection"])

        scored = backtest.score_rows(dataset)
        by_name = {row["full_name"]: row for row in scored["rows"]}
        self.assertTrue(by_name["a/big"]["took_off"])
        self.assertFalse(by_name["b/small"]["took_off"])
        self.assertGreater(by_name["a/big"]["score"], by_name["b/small"]["score"])
        row = scoreboard.score({"picks": []}, {}, scored)
        self.assertEqual((row["backtest_repositories"], row["backtest_took_off"], row["backtest_agreement"]), (2, 1, 1.0))


if __name__ == "__main__":
    unittest.main()
