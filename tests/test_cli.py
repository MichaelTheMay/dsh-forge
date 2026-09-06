import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from dsh_forge import cli
from dsh_forge.launcher import CELL_REGISTRY_SCHEMA_VERSION, Launcher
from tests.helpers import FakeCellSandbox


FAKE_DSH = """#!/bin/sh
trap 'exit 0' TERM INT
echo 'fake dsh ready'
while true; do
    sleep 1
done
"""


class LocalCellCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.versions_directory_environment = mock.patch.dict(
            os.environ,
            {"DSH_FORGE_VERSIONS_DIR": str(self.root / "managed-versions")},
        )
        self.versions_directory_environment.start()
        self.addCleanup(self.versions_directory_environment.stop)
        self.tree = self.root / "deepseek-harness"
        self.tree.mkdir()
        (self.tree / "package.json").write_text(
            json.dumps({"name": "@deepseek-ai/deepseek-harness", "version": "0.0-cli-test"}),
            encoding="utf-8",
        )
        executable = self.tree / "dsh"
        executable.write_text(FAKE_DSH, encoding="utf-8")
        executable.chmod(0o755)
        self.state = self.root / "state"
        self.launcher = Launcher([self.tree], state_root=self.state, sandbox=FakeCellSandbox())

    def tearDown(self):
        self.launcher.shutdown()
        self.temp.cleanup()

    def invoke(self, *arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()

        def factory(**_options):
            return self.launcher

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.run(["--json", *arguments], launcher_factory=factory)
        rendered = stdout.getvalue() or stderr.getvalue()
        return code, json.loads(rendered)

    def tree_id(self):
        return self.launcher.status()["trees"][0]["id"]

    def test_doctor_and_lists_use_the_versioned_machine_contract(self):
        code, doctor = self.invoke("doctor")
        self.assertEqual(code, 0)
        self.assertEqual(doctor["api_version"], "dsh-forge.cli/v1")
        self.assertTrue(doctor["ok"])
        self.assertTrue(doctor["data"]["capabilities"]["persistent_registry"]["available"])
        self.assertTrue(doctor["data"]["capabilities"]["sandboxed_cells"]["available"])
        self.assertEqual(doctor["data"]["capabilities"]["sandboxed_cells"]["backend"], "apptainer-cell-v1")

        code, versions = self.invoke("versions", "list")
        self.assertEqual(code, 0)
        self.assertEqual(versions["data"]["versions"][0]["version"], "0.0-cli-test")

        code, cells = self.invoke("cells", "list")
        self.assertEqual(code, 0)
        self.assertEqual(cells["data"]["cells"], [])
        self.assertEqual(cells["data"]["registry"]["schema_version"], CELL_REGISTRY_SCHEMA_VERSION)

    def test_versions_add_rescan_and_remove_manage_only_the_saved_registry(self):
        code, added = self.invoke("versions", "add", str(self.tree))
        self.assertEqual(code, 0)
        self.assertEqual(len(added["data"]["saved_versions"]), 1)
        saved_id = added["data"]["saved_versions"][0]["id"]

        code, rescanned = self.invoke("versions", "rescan")
        self.assertEqual(code, 0)
        self.assertEqual(rescanned["data"]["saved_versions"][0]["id"], saved_id)

        code, removed = self.invoke("versions", "remove", saved_id)
        self.assertEqual(code, 0)
        self.assertEqual(removed["data"]["saved_versions"], [])
        self.assertTrue(self.tree.is_dir())

    def test_versions_configure_persists_safe_one_click_preferences(self):
        _, added = self.invoke("versions", "add", str(self.tree))
        saved_id = added["data"]["saved_versions"][0]["id"]

        code, configured = self.invoke(
            "versions", "configure", saved_id, "--gpu", "allocated", "--open-browser"
        )
        self.assertEqual(code, 0)
        launch = configured["data"]["saved_versions"][0]["launch"]
        self.assertEqual(launch["resources"]["gpu"], "allocated")
        self.assertTrue(launch["open_browser"])
        self.assertEqual(launch["port"], "auto")

    def test_start_fails_when_apptainer_runner_is_unavailable(self):
        class UnavailableSandbox(FakeCellSandbox):
            ready = False

            def status(self):
                return {"ready": False, "reason": "required Apptainer probe failed", "resource_limits": {}}

        self.launcher.sandbox = UnavailableSandbox()
        code, result = self.invoke(
            "cells", "start", "--tree", self.tree_id(), "--surface", "headless", "--task", "test task"
        )
        self.assertEqual(code, 2)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "launcher_error")
        self.assertIn("Apptainer probe failed", result["error"]["message"])
        self.assertEqual(self.launcher.status()["cells"], [])

    def test_persistent_lifecycle_survives_a_new_launcher_instance(self):
        with mock.patch("dsh_forge.launcher._process_birth", return_value="cli-test-birth"):
            code, started = self.invoke(
                "cells", "start", "--tree", self.tree_id(), "--surface", "headless",
                "--task", "test task",
            )
            self.assertEqual(code, 0)
            cell = started["data"]
            self.assertEqual(cell["execution_backend"], "apptainer-cell-v1")
            self.assertTrue(cell["sandboxed"])
            self.assertEqual(cell["lifecycle"][0]["event"], "started")

            registry = json.loads((self.state / "cells.json").read_text(encoding="utf-8"))
            self.assertEqual(registry["schema_version"], CELL_REGISTRY_SCHEMA_VERSION)
            self.assertGreater(registry["generation"], 0)

            recovered = Launcher([self.tree], state_root=self.state, sandbox=FakeCellSandbox())
            try:
                restored = recovered.cell(cell["id"])
                self.assertEqual(restored["process"], "alive")
                self.assertEqual(restored["id"], cell["id"])
                recovered.stop(cell["id"])
            finally:
                recovered.shutdown()

            code, stopped = self.invoke("cells", "inspect", cell["id"])
            self.assertEqual(code, 0)
            self.assertEqual(stopped["data"]["state"], "stopped")
            self.assertEqual(stopped["data"]["lifecycle"][-1]["event"], "stopped")
            code, stopped_again = self.invoke("cells", "stop", cell["id"])
            self.assertEqual(code, 0)
            self.assertEqual(stopped_again["data"]["state"], "stopped")

    def test_clone_records_lineage(self):
        with mock.patch("dsh_forge.launcher._process_birth", return_value="cli-test-birth"):
            _, started = self.invoke(
                "cells", "start", "--tree", self.tree_id(), "--surface", "headless",
                "--task", "test task",
            )
            source = started["data"]
            code, cloned = self.invoke("cells", "clone", source["id"])
            self.assertEqual(code, 0)
            self.assertEqual(cloned["data"]["parent_cell_id"], source["id"])
            self.assertEqual(cloned["data"]["lineage_action"], "clone")
            self.launcher.stop(source["id"])
            self.launcher.stop(cloned["data"]["id"])

    def test_prompt_and_session_transcript_fail_as_unavailable_capabilities(self):
        code, prompt = self.invoke("cells", "prompt", "cell_missing", "hello")
        self.assertEqual(code, 4)
        self.assertEqual(prompt["error"]["code"], "capability_unavailable")

        code, transcript = self.invoke("cells", "session-log", "cell_missing")
        self.assertEqual(code, 4)
        self.assertEqual(transcript["error"]["code"], "capability_unavailable")


if __name__ == "__main__":
    unittest.main()
