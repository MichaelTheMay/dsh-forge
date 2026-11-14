import json
from pathlib import Path
import tempfile
import unittest

from dsh_forge.comparisons import ComparisonError, ComparisonRegistry, validate_request

A, B, C = ("config_" + letter * 20 for letter in "abc")


class RequestTests(unittest.TestCase):
    def test_accepts_two_to_four_distinct_configurations_and_trims_the_task(self):
        self.assertEqual(validate_request([A, B, A], "  compare this  "), ([A, B], "compare this"))

    def test_rejects_bad_requests_with_plain_reasons(self):
        cases = [
            (([A, B], ""), "Describe the task"),
            (([A, B], "   "), "Describe the task"),
            (([A, B], 7), "Describe the task"),
            (([A, B], "x" * 20_001), "too long"),
            (("nope", "task"), "Choose the configurations"),
            (([A, 5], "task"), "Choose the configurations"),
            (([A], "task"), "between 2 and 4"),
            (([A, A], "task"), "between 2 and 4"),
            (([A, B, C, "config_" + "d" * 20, "config_" + "e" * 20], "task"), "between 2 and 4"),
            (([A, "../etc/passwd"], "task"), "Unknown configuration"),
        ]
        for arguments, message in cases:
            with self.subTest(arguments=str(arguments)[:50]), self.assertRaisesRegex(ComparisonError, message):
                validate_request(*arguments)


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.registry = ComparisonRegistry(self.temp.name)

    def runs(self):
        return [
            {"configuration_id": A, "name": "Fast", "cell_id": "cell_aaaaaaaaaa"},
            {"configuration_id": B, "name": "Careful", "cell_id": None, "error": "Not ready"},
            {"configuration_id": C, "name": "Odd", "cell_id": "../../etc"},
        ]

    def test_records_runs_and_keeps_only_well_formed_session_ids(self):
        record = self.registry.create("do the thing", self.runs())
        self.assertRegex(record["id"], r"^cmp_[a-f0-9]{16}$")
        self.assertEqual([run["cell_id"] for run in record["runs"]], ["cell_aaaaaaaaaa", None, None])
        self.assertEqual(record["runs"][1]["error"], "Not ready")
        self.assertEqual(self.registry.get(record["id"]), record)
        self.assertEqual(ComparisonRegistry(self.temp.name).get(record["id"])["task"], "do the thing")

    def test_lists_newest_first(self):
        first = self.registry.create("one", self.runs())
        second = self.registry.create("two", self.runs())
        self.assertEqual([record["id"] for record in self.registry.list()], [second["id"], first["id"]])
        self.assertEqual(len(self.registry.list(limit=1)), 1)

    def test_only_a_session_from_this_comparison_can_be_chosen(self):
        record = self.registry.create("task", self.runs())
        chosen = self.registry.choose(record["id"], "cell_aaaaaaaaaa")
        self.assertEqual(chosen["chosen_cell_id"], "cell_aaaaaaaaaa")
        self.assertEqual(self.registry.get(record["id"])["chosen_cell_id"], "cell_aaaaaaaaaa")
        with self.assertRaisesRegex(ComparisonError, "not part of this comparison"):
            self.registry.choose(record["id"], "cell_bbbbbbbbbb")
        with self.assertRaisesRegex(ComparisonError, "not part of this comparison"):
            self.registry.choose(record["id"], None)

    def test_unknown_or_malformed_ids_are_refused(self):
        for bad in ("cmp_" + "0" * 16, "../x", None, 5):
            with self.subTest(bad=bad), self.assertRaisesRegex(ComparisonError, "Unknown comparison"):
                self.registry.get(bad)
            with self.subTest(bad=bad), self.assertRaisesRegex(ComparisonError, "Unknown comparison"):
                self.registry.choose(bad, "cell_aaaaaaaaaa")

    def test_the_file_is_private_and_a_damaged_one_is_reported(self):
        self.registry.create("task", self.runs())
        self.assertEqual(self.registry.path.stat().st_mode & 0o777, 0o600)
        self.registry.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(ComparisonError):
            self.registry.list()
        self.registry.path.write_text(json.dumps({"schema_version": 99, "comparisons": []}), encoding="utf-8")
        with self.assertRaisesRegex(ComparisonError, "unsupported format"):
            self.registry.list()


if __name__ == "__main__":
    unittest.main()
