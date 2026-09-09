import json
import io
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from dsh_forge.assistant_server import AssistantServer
from dsh_forge.configurations import ConfigurationError, ConfigurationRegistry
from dsh_forge.launcher import Launcher, LauncherError
from dsh_forge.mcp_server import CatalogIndex, ForgeMCP, serve_stdio
from tests.helpers import FakeCellSandbox


FAKE_DSH = """#!/bin/sh
trap 'exit 0' TERM INT
while true; do sleep 1; done
"""


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tree = self.root / "deepseek-harness"
        self.tree.mkdir()
        (self.tree / "package.json").write_text(
            json.dumps({"name": "@deepseek-ai/deepseek-harness", "version": "0.1.2-rc.1"}),
            encoding="utf-8",
        )
        executable = self.tree / "dsh"
        executable.write_text(FAKE_DSH, encoding="utf-8")
        executable.chmod(0o755)
        self.env = mock.patch.dict(os.environ, {"DSH_FORGE_VERSIONS_DIR": str(self.root / "versions")})
        self.env.start()
        self.launcher = Launcher(state_root=self.root / "state", sandbox=FakeCellSandbox())
        self.saved = self.launcher.add_scan_roots([str(self.tree)])["saved_versions"][0]

    def tearDown(self):
        self.launcher.shutdown()
        self.env.stop()
        self.temp.cleanup()

    def test_registry_is_schema_versioned_persistent_and_non_destructive(self):
        saved = self.launcher.save_configuration(
            name="Base review", version_id=self.saved["id"],
            launch={"surface": "web", "profile": "web"},
        )
        self.assertTrue(saved["runtime"]["runnable"])
        payload = json.loads((self.root / "state" / "configurations.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        recovered = ConfigurationRegistry(self.root / "state").get(saved["id"])
        self.assertEqual(recovered["schema"], "dsh-forge.configuration/v1")
        remaining = self.launcher.remove_configuration(saved["id"])
        self.assertEqual(remaining, [])
        self.assertTrue(self.tree.is_dir())

    def test_catalog_selection_remains_inert_without_signed_package(self):
        draft = self.launcher.save_configuration(
            name="Potential pair", version_id=self.saved["id"], draft=True,
            source="mcp-draft",
            selections=[{"type": "plugin", "id": "github:1332073142"}],
        )
        self.assertFalse(draft["runtime"]["runnable"])
        approved = self.launcher.approve_configuration(draft["id"])
        self.assertFalse(approved["runtime"]["runnable"])
        self.assertIn("signed package recipe", approved["runtime"]["reason"])
        with self.assertRaisesRegex(LauncherError, "signed package recipe"):
            self.launcher.run_configuration(draft["id"])

    def test_ready_base_configuration_passes_stable_identity_to_launcher(self):
        saved = self.launcher.save_configuration(
            name="Base Harness", version_id=self.saved["id"],
            launch={"surface": "web", "profile": "web", "port": "auto"},
        )
        with mock.patch.object(self.launcher, "launch", return_value={"id": "cell_test"}) as launch:
            self.assertEqual(self.launcher.run_configuration(saved["id"]), {"id": "cell_test"})
        raw = launch.call_args.args[0]
        self.assertEqual(raw["configuration_id"], saved["id"])
        self.assertEqual(raw["tree_id"], self.saved["primary_tree"]["id"])
        self.assertEqual(raw["home_mode"], "fresh")

    def test_registry_rejects_symlinked_state_file(self):
        registry = ConfigurationRegistry(self.root / "unsafe")
        target = self.root / "target.json"
        target.write_text("{}", encoding="utf-8")
        registry.path.symlink_to(target)
        with self.assertRaisesRegex(ConfigurationError, "symlink"):
            registry.list()

    def test_mcp_exposes_discovery_and_drafts_but_not_install_or_run(self):
        server = ForgeMCP(self.launcher, CatalogIndex())
        tools = server.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})["result"]["tools"]
        names = {tool["name"] for tool in tools}
        self.assertEqual(names, {"catalog_search", "versions_list", "configurations_list", "configuration_save_draft"})
        self.assertFalse(any("install" in name or "run" in name for name in names))
        result = server.dispatch({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "catalog_search", "arguments": {"type": "package", "featured": True}},
        })["result"]["structuredContent"]
        self.assertGreaterEqual(result["count"], 1)
        artifact = result["results"][0]
        drafted = server.dispatch({
            "jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "configuration_save_draft", "arguments": {
                "name": "MCP proposal", "version_id": self.saved["id"],
                "selections": [{"type": artifact["type"], "id": artifact["id"]}],
            }},
        })["result"]["structuredContent"]
        self.assertEqual(drafted["status"], "draft")
        self.assertFalse(drafted["runtime"]["runnable"])

    def test_mcp_stdio_is_newline_delimited_json_only(self):
        source = io.StringIO(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}) + "\n" +
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}) + "\n"
        )
        destination = io.StringIO()
        serve_stdio(ForgeMCP(self.launcher, CatalogIndex()), source, destination)
        lines = destination.getvalue().splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(all(json.loads(line)["jsonrpc"] == "2.0" for line in lines))
        self.assertEqual(json.loads(lines[0])["result"]["protocolVersion"], "2025-06-18")

    def test_mcp_does_not_advertise_unimplemented_2026_protocol(self):
        server = ForgeMCP(self.launcher, CatalogIndex())
        initialized = server.dispatch({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2026-07-28"},
        })
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-06-18")

        index = CatalogIndex()
        catalog = self.root / "assistant-catalog.json"
        catalog.write_text(json.dumps({"entries": index.rows, "saved_versions": [self.saved]}), encoding="utf-8")
        assistant = AssistantServer(catalog, self.root / "assistant-drafts")
        initialized = assistant.dispatch({
            "jsonrpc": "2.0", "id": 2, "method": "initialize",
            "params": {"protocolVersion": "2026-07-28"},
        })
        self.assertEqual(initialized["result"]["protocolVersion"], "2025-06-18")

        node_server = Path(__file__).resolve().parents[1] / "dsh_forge" / "assistant_server.mjs"
        completed = subprocess.run(
            ["node", str(node_server), "--catalog", str(catalog), "--draft-dir", str(self.root / "node-drafts")],
            input=json.dumps({
                "jsonrpc": "2.0", "id": 3, "method": "initialize",
                "params": {"protocolVersion": "2026-07-28"},
            }) + "\n",
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(json.loads(completed.stdout)["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(completed.stderr, "")

    def test_embedded_assistant_saves_only_bounded_workspace_drafts(self):
        index = CatalogIndex()
        catalog = self.root / "catalog.json"
        catalog.write_text(json.dumps({"entries": index.rows, "saved_versions": [self.saved]}), encoding="utf-8")
        draft_dir = self.root / "drafts"
        server = AssistantServer(catalog, draft_dir)
        artifact = index.rows[0]
        saved = server.call("configuration_save_draft", {
            "name": "Assistant proposal", "version_id": self.saved["id"],
            "selections": [{"type": artifact["type"], "id": artifact["id"]}],
        })["structuredContent"]
        self.assertFalse(saved["execution_authorized"])
        destination = Path(saved["saved_to"])
        self.assertEqual(destination.parent, draft_dir)
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["status"], "draft")

    def test_assistant_launch_is_an_isolated_cell_with_bounded_mcp_inputs(self):
        with mock.patch("dsh_forge.launcher._process_birth", return_value="assistant-birth"):
            cell = self.launcher.launch_assistant(self.saved["id"])
            self.assertEqual(cell["purpose"], "forge-assistant")
            internal = self.launcher._cells[cell["id"]]
            workspace = Path(internal["real_workspace"])
            self.assertTrue((workspace / "dsh-forge-catalog.json").is_file())
            self.assertTrue((workspace / "dsh-forge-assistant-mcp.mjs").is_file())
            patch = (workspace / "forge-assistant.cordis.yml").read_text(encoding="utf-8")
            self.assertIn("@deepseek-ai/dsh-mcp-client", patch)
            self.assertIn("transport: stdio", patch)
            self.assertIn("command: node", patch)
            self.assertNotIn(str(self.root / "state"), patch)
            self.launcher.stop(cell["id"])


if __name__ == "__main__":
    unittest.main()
