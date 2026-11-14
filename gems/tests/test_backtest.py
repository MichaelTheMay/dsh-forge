import datetime as dt
import gzip
import json
from pathlib import Path
import tempfile
import unittest

from gems.eval import backtest
from gems.fetch import FetchError

NOW = dt.datetime(2026, 11, 13, tzinfo=dt.timezone.utc)
THEN = "2026-09-14T00:00:00Z"


def registry(root, records):
    path = Path(root) / "registry.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        json.dump({"supplemental_entries": records, "entries": []}, handle)
    return path


def record(name, stars, **changes):
    base = {"artifact_type": "plugin", "full_name": name, "github_stars": stars, "archived": False, "parent_repository": None}
    base.update(changes)
    return base


def node(created="2026-06-01T00:00:00Z", now=5, recent=3, old=2, commit="c" * 40, more=False):
    edges = [{"starredAt": "2026-10-20T00:00:00Z"}] * recent + [{"starredAt": "2026-07-01T00:00:00Z"}] * old
    return {
        "createdAt": created, "stargazerCount": now,
        "defaultBranchRef": {"target": {"history": {"nodes": [{"oid": commit}] if commit else []}}},
        "stargazers": {"pageInfo": {"hasNextPage": more, "endCursor": "cur"}, "edges": edges},
    }


class PopulationTests(unittest.TestCase):
    def test_loads_only_live_original_plugins(self):
        with tempfile.TemporaryDirectory() as root:
            path = registry(root, [
                record("a/ok", 3), record("b/archived", 1, archived=True), record("c/fork", 1, parent_repository="x/y"),
                record("d/fork-type", 1, artifact_type="fork"), record("bad name", 1), record("e/nostars", None),
            ])
            self.assertEqual(backtest.load_population(path), [{"full_name": "a/ok", "stars_now": 3}])

    def test_sample_is_repeatable_and_spans_star_bands(self):
        population = [{"full_name": f"o{index}/r", "stars_now": index % 60} for index in range(600)]
        first = backtest.sample(population, 50, seed=1)
        self.assertEqual(first, backtest.sample(population, 50, seed=1))
        self.assertNotEqual(first, backtest.sample(population, 50, seed=2))
        stars = {item["stars_now"] for item in first}
        self.assertTrue(0 in stars and any(value >= 40 for value in stars))


class HistoryTests(unittest.TestCase):
    def test_counts_stars_gained_since_the_rewind_date(self):
        calls = []

        def post(query, variables):
            calls.append(variables)
            return {"data": {"r0": node(), "r1": node(created="2026-10-01T00:00:00Z"), "r2": None, "r3": node(commit=None)}}

        found = backtest.collect_history(["a/b", "too/new", "gone/x", "empty/y"], dt.datetime(2026, 9, 14, tzinfo=dt.timezone.utc), post)
        self.assertEqual(found, {"a/b": {"commit_then": "c" * 40, "stars_then": 2, "stars_gained": 3}})
        self.assertEqual(calls[0], {"until": THEN})

    def test_pages_through_recent_stars_and_gives_up_on_runaway_projects(self):
        def post(query, variables):
            if "after" in variables:
                return {"data": {"repository": {"stargazers": {
                    "pageInfo": {"hasNextPage": False}, "edges": [{"starredAt": "2026-08-01T00:00:00Z"}]}}}}
            return {"data": {"r0": node(now=4, recent=3, old=0, more=True)}}

        found = backtest.collect_history(["a/b"], dt.datetime(2026, 9, 14, tzinfo=dt.timezone.utc), post)
        self.assertEqual(found["a/b"]["stars_gained"], 3)
        self.assertEqual(found["a/b"]["stars_then"], 1)

        def endless(query, variables):
            page = {"pageInfo": {"hasNextPage": True, "endCursor": "c"}, "edges": [{"starredAt": "2026-11-01T00:00:00Z"}]}
            if "after" in variables:
                return {"data": {"repository": {"stargazers": page}}}
            return {"data": {"r0": {**node(), "stargazers": page}}}

        self.assertEqual(backtest.collect_history(["a/b"], dt.datetime(2026, 9, 14, tzinfo=dt.timezone.utc), endless), {})


class CollectTests(unittest.TestCase):
    def test_measures_code_as_of_the_rewind_date_and_scores_it(self):
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

        def post(query, variables):
            # Repositories arrive in sampled order; answer by position.
            order = [part.split('name: "')[1].split('"')[0] for part in query.split("repository(")[1:]]
            answers = {"big": node(recent=9, old=1, now=10), "small": node(recent=0, old=1, now=1),
                       "broken": node(), "famous": node(recent=1, old=50, now=51)}
            return {"data": {f"r{index}": answers[name] for index, name in enumerate(order)}}

        with tempfile.TemporaryDirectory() as root:
            path = registry(root, [record("a/big", 10), record("b/small", 1), record("c/broken", 5), record("d/famous", 51)])
            dataset = backtest.collect(path, Path(root) / "work", post=post, now=NOW, size=20, fetch=fetch)
        self.assertEqual(dataset["rewound_to"], "2026-09-14")
        self.assertEqual([row["full_name"] for row in dataset["rows"]], ["a/big", "b/small"])
        self.assertEqual({name for name, _ in fetched}, {"a/big", "b/small", "c/broken"})
        self.assertNotIn("fingerprints", dataset["rows"][0]["inspection"])
        scored = backtest.score_rows(dataset)
        by_name = {row["full_name"]: row for row in scored["rows"]}
        self.assertGreater(by_name["a/big"]["score"], by_name["b/small"]["score"])
        self.assertEqual(by_name["a/big"]["stars_gained"], 9)

    def test_needs_a_token(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(backtest.BacktestError):
            backtest.token_from_environment()


if __name__ == "__main__":
    unittest.main()
