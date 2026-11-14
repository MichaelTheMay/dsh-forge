import json
from pathlib import Path
import tempfile
import unittest

from gems import REVIEW_SCHEMA
from gems.review import ReviewError, load_reviews, review_filename, template, validate


def review(**changes):
    base = {
        "schema": REVIEW_SCHEMA,
        "full_name": "owner/repo",
        "commit": "a" * 40,
        "source": "claude-session",
        "reviewer": "test",
        "reviewed_at": "2026-11-13",
        "summary": "Keeps a searchable memory of past sessions.",
        "showcase": "Recalls decisions from last week without being asked.",
        "scores": {"usefulness": 4, "novelty": 3, "craft": 4, "works": 4, "trust": 3},
        "verdict": "gem",
        "concerns": ["No tests for the sync path"],
        "evidence": ["lib/store.js: SQLite with migrations"],
    }
    base.update(changes)
    return base


class ValidateTests(unittest.TestCase):
    def test_accepts_a_complete_review(self):
        self.assertEqual(validate(review())["verdict"], "gem")

    def test_rejects_wrong_shapes(self):
        cases = [
            {"schema": "other"},
            {"full_name": "../etc"},
            {"commit": "main"},
            {"source": "rumour"},
            {"verdict": "amazing"},
            {"scores": {"usefulness": 4}},
            {"scores": {"usefulness": 9, "novelty": 3, "craft": 4, "works": 4, "trust": 3}},
            {"scores": {"usefulness": True, "novelty": 3, "craft": 4, "works": 4, "trust": 3}},
            {"summary": ""},
            {"summary": 12},
            {"concerns": ["x"] * 9},
        ]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(ReviewError):
                validate(review(**change))

    def test_text_from_an_untrusted_repository_is_made_plain(self):
        cleaned = validate(review(
            summary="Good <script>alert(1)</script> plugin\n\x00 with   gaps",
            showcase="x" * 500,
        ))
        self.assertEqual(cleaned["summary"], "Good alert(1) plugin with gaps")
        self.assertEqual(len(cleaned["showcase"]), 200)


class LoadReviewsTests(unittest.TestCase):
    def test_loads_valid_reviews_and_reports_the_rest(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder / review_filename("owner/repo", "a" * 40)).write_text(json.dumps(review()), encoding="utf-8")
            (folder / "broken.json").write_text("{", encoding="utf-8")
            (folder / "wrong.json").write_text(json.dumps(review(verdict="nope")), encoding="utf-8")
            reviews, problems = load_reviews(folder)
        self.assertEqual(list(reviews), ["owner/repo"])
        self.assertEqual(len(problems), 2)

    def test_the_latest_review_of_a_repository_wins(self):
        with tempfile.TemporaryDirectory() as root:
            folder = Path(root)
            (folder / "old.json").write_text(json.dumps(review(reviewed_at="2026-10-01", verdict="solid")), encoding="utf-8")
            (folder / "new.json").write_text(json.dumps(review(reviewed_at="2026-11-13", verdict="gem")), encoding="utf-8")
            reviews, _ = load_reviews(folder)
        self.assertEqual(reviews["owner/repo"]["verdict"], "gem")

    def test_a_missing_folder_is_simply_no_reviews(self):
        self.assertEqual(load_reviews("/nonexistent/reviews"), ({}, []))

    def test_template_names_the_repository_but_is_not_yet_valid(self):
        with self.assertRaises(ReviewError):
            validate(template("owner/repo", "a" * 40))


if __name__ == "__main__":
    unittest.main()
