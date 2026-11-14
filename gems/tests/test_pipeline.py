import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from gems import PICKS_SCHEMA, REVIEW_SCHEMA
from gems.__main__ import main
from gems.fetch import FetchError
from gems import pipeline


def queue_entry(name, score, commit="a" * 40):
    return {
        "artifact": {"artifact_id": "github:" + name, "artifact_type": "plugin", "full_name": name, "head_sha": commit,
                     "github_stars": 1, "archived": False, "parent_repository": None, "description": "catalog text"},
        "research": {"score": score, "candidate": True, "capabilities": ["memory"], "policy": "v3"},
    }


def fake_fetch(calls):
    def fetch(full_name, commit, destination):
        calls.append(full_name)
        if full_name == "gone/away":
            raise FetchError("repository not found")
        root = Path(destination)
        (root / "lib").mkdir(parents=True)
        (root / "package.json").write_text(json.dumps({"main": "lib/index.js", "dsh": {"bundle": {}}}), encoding="utf-8")
        (root / "cordis.patch.yml").write_text("x: 1\n", encoding="utf-8")
        body = "".join(f"const {full_name.split('/')[0]}{index} = {index};\n" for index in range(120))
        (root / "lib" / "index.js").write_text(body, encoding="utf-8")
        return root
    return fetch


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.queue = {"snapshot_id": "snap", "policy": "v3", "candidates": [
            queue_entry("alpha/one", 90), queue_entry("beta/two", 80), queue_entry("gone/away", 70),
        ]}
        self.candidates = pipeline.select(self.queue)

    def test_inspects_each_candidate_and_records_failures(self):
        calls = []
        result = pipeline.inspect_candidates(self.candidates, self.root / "work", fetch=fake_fetch(calls))
        self.assertEqual(sorted(result["repositories"]), ["alpha/one", "beta/two"])
        self.assertEqual(result["failures"], {"gone/away": "repository not found"})
        self.assertEqual(result["repositories"]["alpha/one"]["inspection"]["code"]["lines"], 120)
        # Checkouts are deleted once measured.
        self.assertFalse(any((self.root / "work").glob("*")))

    def test_does_not_refetch_a_repository_measured_at_the_same_commit(self):
        first = pipeline.inspect_candidates(self.candidates, self.root / "work", fetch=fake_fetch([]))
        calls = []
        pipeline.inspect_candidates(self.candidates, self.root / "work", previous=first, fetch=fake_fetch(calls))
        self.assertEqual(calls, ["gone/away"])
        moved = pipeline.select({"candidates": [queue_entry("alpha/one", 90, commit="b" * 40)]})
        calls = []
        pipeline.inspect_candidates(moved, self.root / "work", previous=first, fetch=fake_fetch(calls))
        self.assertEqual(calls, ["alpha/one"])

    def test_keep_leaves_checkouts_for_a_reviewer(self):
        pipeline.inspect_candidates(self.candidates[:1], self.root / "work", keep=True, fetch=fake_fetch([]))
        self.assertTrue((self.root / "work" / "alpha__one" / "lib" / "index.js").is_file())

    def test_build_joins_inspections_and_reviews_into_picks(self):
        inspections = pipeline.inspect_candidates(self.candidates, self.root / "work", fetch=fake_fetch([]))
        reviews = self.root / "reviews"
        reviews.mkdir()
        (reviews / "beta.json").write_text(json.dumps({
            "schema": REVIEW_SCHEMA, "full_name": "beta/two", "commit": "a" * 40, "source": "human",
            "reviewer": "t", "reviewed_at": "2026-11-13", "summary": "Reads well.", "showcase": "Worth it.",
            "scores": {"usefulness": 5, "novelty": 5, "craft": 5, "works": 5, "trust": 5}, "verdict": "gem",
        }), encoding="utf-8")
        (reviews / "junk.json").write_text("{", encoding="utf-8")
        document, problems = pipeline.build_picks(self.queue, inspections, reviews)
        self.assertEqual(document["schema"], PICKS_SCHEMA)
        self.assertEqual([pick["full_name"] for pick in document["picks"]], ["beta/two", "alpha/one"])
        self.assertEqual(document["counts"], {"considered": 3, "inspected": 2, "reviewed": 1, "picks": 2})
        self.assertEqual(document["based_on"], {"snapshot_id": "snap", "stage1_policy": "v3"})
        self.assertEqual(len(problems), 1)
        self.assertEqual(document["not_featured"], [])
        # A project reviewed as "skip" is named so the app can keep it off every shelf.
        skipped = json.loads((reviews / "beta.json").read_text(encoding="utf-8"))
        skipped["verdict"] = "skip"
        (reviews / "beta.json").write_text(json.dumps(skipped), encoding="utf-8")
        document, _problems = pipeline.build_picks(self.queue, inspections, reviews)
        self.assertEqual([pick["full_name"] for pick in document["picks"]], ["alpha/one"])
        self.assertEqual(document["not_featured"], ["github:beta/two"])

    def test_write_json_is_atomic_and_readable(self):
        target = self.root / "nested" / "out.json"
        pipeline.write_json(target, {"b": 1, "a": 2})
        self.assertEqual(pipeline.read_json(target), {"a": 2, "b": 1})
        self.assertEqual([path.name for path in target.parent.iterdir()], ["out.json"])


class CommandLineTests(unittest.TestCase):
    def run_main(self, *arguments):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(arguments))
        return code, out.getvalue(), err.getvalue()

    def test_candidates_rubric_and_template(self):
        with tempfile.TemporaryDirectory() as root:
            queue = Path(root) / "queue.json"
            queue.write_text(json.dumps({"candidates": [queue_entry("alpha/one", 90)]}), encoding="utf-8")
            code, out, _ = self.run_main("candidates", "--queue", str(queue), "--reviews", root)
            self.assertEqual((code, out.strip()), (0, "alpha/one " + "a" * 40))
        code, out, _ = self.run_main("rubric")
        self.assertIn("usefulness", out)
        code, out, err = self.run_main("review-template", "alpha/one", "a" * 40)
        self.assertEqual(json.loads(out)["full_name"], "alpha/one")
        self.assertIn("alpha__one@aaaaaaaaaaaa.json", err)

    def test_a_missing_queue_is_a_clean_error(self):
        code, _, err = self.run_main("candidates", "--queue", "/nonexistent/queue.json")
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_eval_prints_a_scoreboard(self):
        with tempfile.TemporaryDirectory() as root:
            picks = Path(root) / "picks.json"
            picks.write_text(json.dumps({"picks": [{"full_name": "a/b", "score": 9}]}), encoding="utf-8")
            code, out, _ = self.run_main("eval", "--picks", str(picks), "--labels", str(Path(root) / "none.json"))
        self.assertEqual(code, 0)
        self.assertIn("human labels           0", out)


if __name__ == "__main__":
    unittest.main()
