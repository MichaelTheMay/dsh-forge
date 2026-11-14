import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from dsh_forge.comparisons import ComparisonError, ComparisonRegistry, validate_request
from dsh_forge.launcher import Launcher, LauncherError
from tests.helpers import FakeCellSandbox

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


# A stand-in Harness: in headless mode it prints an answer that names its task and exits.
FAKE_DSH = """#!/bin/sh
if [ "$1" = "headless" ]; then
  echo "answer to: $2"
  exit 0
fi
trap 'exit 0' TERM INT
while true; do sleep 1; done
"""


class LauncherComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        tree = self.root / "deepseek-harness"
        tree.mkdir()
        (tree / "package.json").write_text(json.dumps({"name": "@deepseek-ai/deepseek-harness", "version": "0.1.2-rc.1"}), encoding="utf-8")
        executable = tree / "dsh"
        executable.write_text(FAKE_DSH, encoding="utf-8")
        executable.chmod(0o755)
        self.env = mock.patch.dict(os.environ, {"DSH_FORGE_VERSIONS_DIR": str(self.root / "versions")})
        self.env.start()
        self.launcher = Launcher(state_root=self.root / "state", sandbox=FakeCellSandbox())
        self.saved = self.launcher.add_scan_roots([str(tree)])["saved_versions"][0]

    def tearDown(self):
        self.launcher.shutdown()
        self.env.stop()
        self.temp.cleanup()

    def configuration(self, name, **changes):
        return self.launcher.save_configuration(
            name=name, version_id=self.saved["id"], launch={"surface": "web", "profile": "web"}, **changes,
        )

    def finished(self, comparison_id, timeout=10.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            view = self.launcher.comparison(comparison_id)
            if view["done"]:
                return view
            time.sleep(0.1)
        self.fail("comparison did not finish")

    def test_runs_one_task_on_each_configuration_and_collects_the_answers(self):
        fast, careful = self.configuration("Fast"), self.configuration("Careful")
        started = self.launcher.run_comparison([fast["id"], careful["id"]], "summarise the repo")
        self.assertEqual([run["name"] for run in started["runs"]], ["Fast", "Careful"])
        self.assertEqual(len({run["cell_id"] for run in started["runs"]}), 2)
        view = self.finished(started["id"])
        for run in view["runs"]:
            self.assertEqual(run["state"], "finished")
            self.assertIn("answer to: summarise the repo", "\n".join(run["output"]))
        # Each run was a separate headless session tied to its configuration.
        cells = {cell["id"]: cell for cell in self.launcher.status()["cells"]}
        for run, saved in zip(view["runs"], (fast, careful)):
            self.assertEqual(cells[run["cell_id"]]["surface"], "headless")
            self.assertEqual(cells[run["cell_id"]]["configuration_id"], saved["id"])
        self.assertEqual(self.launcher.comparisons()[0]["id"], started["id"])

    def test_the_user_can_pick_one_run_and_only_one_of_this_comparison(self):
        first, second = self.configuration("One"), self.configuration("Two")
        started = self.launcher.run_comparison([first["id"], second["id"]], "task")
        pick = started["runs"][1]["cell_id"]
        view = self.launcher.choose_comparison_run(started["id"], pick)
        self.assertEqual([run["chosen"] for run in view["runs"]], [False, True])
        self.assertTrue(self.launcher.comparisons()[0]["chosen"])
        with self.assertRaisesRegex(LauncherError, "not part of this comparison"):
            self.launcher.choose_comparison_run(started["id"], "cell_0000000000")

    def test_nothing_starts_unless_every_configuration_is_ready(self):
        ready = self.configuration("Ready")
        draft = self.configuration("Draft one", draft=True)
        before = len(self.launcher.status()["cells"])
        with self.assertRaisesRegex(LauncherError, "Draft one is not ready to run"):
            self.launcher.run_comparison([ready["id"], draft["id"]], "task")
        self.assertEqual(len(self.launcher.status()["cells"]), before)
        for arguments, message in [(([ready["id"]], "task"), "between 2 and 4"), (([ready["id"], draft["id"]], ""), "Describe the task")]:
            with self.assertRaisesRegex(LauncherError, message):
                self.launcher.run_comparison(*arguments)

    def test_a_run_that_fails_to_start_is_recorded_and_the_rest_continue(self):
        good, bad = self.configuration("Good"), self.configuration("Bad")
        real = self.launcher.run_configuration

        def flaky(identity, **options):
            if identity == bad["id"]:
                raise LauncherError("No free port")
            return real(identity, **options)

        with mock.patch.object(self.launcher, "run_configuration", side_effect=flaky):
            started = self.launcher.run_comparison([good["id"], bad["id"]], "task")
        self.assertEqual([(run["name"], run["state"], run["error"]) for run in started["runs"]][1], ("Bad", "failed", "No free port"))
        self.assertTrue(started["runs"][0]["cell_id"])
        with mock.patch.object(self.launcher, "run_configuration", side_effect=LauncherError("down")):
            with self.assertRaisesRegex(LauncherError, "None of the configurations could start"):
                self.launcher.run_comparison([good["id"], bad["id"]], "task")

    def test_unknown_comparisons_are_refused(self):
        with self.assertRaisesRegex(LauncherError, "Unknown comparison"):
            self.launcher.comparison("cmp_" + "0" * 16)


if __name__ == "__main__":
    unittest.main()
