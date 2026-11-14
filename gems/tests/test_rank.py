import unittest

from gems import PICKS_SCHEMA, REVIEW_SCHEMA
from gems.rank import Weights, picks_document, rank, review_score, substance_score


def inspection(lines=1200, test_lines=300, kind="plugin", **changes):
    base = {
        "kind": kind,
        "manifest": {"valid": True, "declares_plugin": True, "patch_file_present": True, "entry_present": True, "lifecycle_scripts": []},
        "code": {"lines": lines, "files": 8},
        "tests": {"lines": test_lines, "files": 4},
        "docs": {"readme_bytes": 5000, "bytes": 9000},
        "practices": {"ci": True, "license": True, "changelog": False},
        "risk_hints": {},
    }
    base.update(changes)
    return base


def candidate(name, score=80, stars=2, commit="a" * 40):
    return {"artifact_id": "github:1", "full_name": name, "commit": commit, "stars": stars,
            "description": "From the catalog", "capabilities": ["memory"], "stage1": {"score": score}}


def review(name, verdict="gem", value=4, commit="a" * 40):
    return {"schema": REVIEW_SCHEMA, "full_name": name, "commit": commit, "source": "claude-session",
            "summary": "What it does.", "showcase": "Why you want it.", "verdict": verdict,
            "scores": {key: value for key in ("usefulness", "novelty", "craft", "works", "trust")}}


class ScoreTests(unittest.TestCase):
    def test_substance_rewards_real_tested_wired_code(self):
        strong = substance_score(inspection(lines=6000, test_lines=1500, docs={"bytes": 60000}))
        ordinary = substance_score(inspection())
        self.assertGreater(strong, 75)
        self.assertGreater(strong, ordinary)
        self.assertLess(substance_score(inspection(lines=30, test_lines=0, kind="stub")), 25)
        self.assertLess(substance_score(inspection(test_lines=0)), ordinary)
        # Missing plugin wiring halves the score rather than costing a few points.
        unwired = inspection()
        unwired["manifest"] = {"valid": False, "declares_plugin": False, "patch_file_present": False, "entry_present": False}
        self.assertAlmostEqual(substance_score(unwired), ordinary / 2, delta=3)

    def test_substance_penalises_copies_install_scripts_and_risk_hints(self):
        clean = substance_score(inspection())
        self.assertAlmostEqual(substance_score(inspection(), copy_overlap=0.5), clean / 2, delta=0.1)
        scripted = inspection()
        scripted["manifest"]["lifecycle_scripts"] = ["postinstall"]
        self.assertEqual(substance_score(scripted), round(clean - 8, 1))
        self.assertEqual(substance_score(inspection(risk_hints={"remote_shell": 1})), round(clean - 6, 1))

    def test_review_score_spans_the_scale(self):
        self.assertEqual(review_score(review("a/b", value=1)), 0.0)
        self.assertEqual(review_score(review("a/b", value=5)), 100.0)
        self.assertEqual(review_score(review("a/b", value=3)), 50.0)


class RankTests(unittest.TestCase):
    def test_a_liked_review_outranks_better_statistics(self):
        candidates = [candidate("stats/king", score=100), candidate("read/gem", score=60)]
        inspections = {"stats/king": inspection(), "read/gem": inspection()}
        picks = rank(candidates, inspections, {"read/gem": review("read/gem", value=5)}, {})
        self.assertEqual([pick["full_name"] for pick in picks], ["read/gem", "stats/king"])
        self.assertEqual(picks[0]["confidence"], "reviewed")
        self.assertEqual(picks[1]["confidence"], "measured")
        self.assertLessEqual(picks[1]["score"], Weights().unreviewed_ceiling)
        self.assertEqual(picks[0]["rank"], 1)

    def test_unread_repositories_keep_their_order_under_the_ceiling(self):
        candidates = [candidate("a/weaker", score=70), candidate("b/stronger", score=99)]
        picks = rank(candidates, {"a/weaker": inspection(), "b/stronger": inspection()}, {}, {})
        self.assertEqual([pick["full_name"] for pick in picks], ["b/stronger", "a/weaker"])
        self.assertLess(picks[1]["score"], picks[0]["score"])
        self.assertLessEqual(picks[0]["score"], Weights().unreviewed_ceiling)

    def test_skips_copies_and_uninspected_repositories_are_left_out(self):
        candidates = [candidate("a/skip"), candidate("b/copy"), candidate("c/unseen"), candidate("d/ok")]
        inspections = {"a/skip": inspection(), "b/copy": inspection(), "d/ok": inspection()}
        picks = rank(candidates, inspections, {"a/skip": review("a/skip", verdict="skip")}, {"b/copy": 0.9})
        self.assertEqual([pick["full_name"] for pick in picks], ["d/ok"])

    def test_a_review_of_an_older_commit_still_counts_but_says_so(self):
        picks = rank([candidate("a/b", commit="b" * 40)], {"a/b": inspection()}, {"a/b": review("a/b")}, {})
        self.assertEqual(picks[0]["confidence"], "reviewed at an earlier version")

    def test_reasons_are_plain_sentences_led_by_the_reviewer(self):
        pick = rank([candidate("a/b", stars=0)], {"a/b": inspection()}, {"a/b": review("a/b")}, {})[0]
        self.assertEqual(pick["reasons"], ["Why you want it.", "1,200 lines of its own code with 4 test files", "No stars yet"])
        self.assertEqual(pick["summary"], "What it does.")

    def test_limit_and_document_shape(self):
        candidates = [candidate(f"o{index}/r", score=index) for index in range(5)]
        inspections = {item["full_name"]: inspection() for item in candidates}
        picks = rank(candidates, inspections, {}, {}, limit=3)
        self.assertEqual(len(picks), 3)
        document = picks_document(picks, generated_at="2026-11-13T00:00:00Z", queue={"snapshot_id": "s", "policy": "p"}, considered=5, inspected=5)
        self.assertEqual(document["schema"], PICKS_SCHEMA)
        self.assertEqual(document["counts"], {"considered": 5, "inspected": 5, "reviewed": 0, "picks": 3})
        self.assertEqual(document["claims"], {"executed": False, "security_verified": False})


if __name__ == "__main__":
    unittest.main()
