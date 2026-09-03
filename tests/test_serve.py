import importlib.util
import json
import os
from functools import partial
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest import mock
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("serve", ROOT / "scripts/serve.py")
serve = importlib.util.module_from_spec(spec)
spec.loader.exec_module(serve)
import dsh_forge.launcher as launcher_module
from tests.helpers import FakeCellSandbox


FAKE_DSH = """#!/bin/sh
trap 'exit 0' TERM INT
echo 'fake dsh ready'
mode="$1"
port=""
while [ "$#" -gt 0 ]; do
    if [ "$1" = "--port" ]; then
        shift
        port="$1"
    fi
    shift
done
if [ "$mode" = "web" ]; then
    echo "dsh web: http://127.0.0.1:${port}/?token=test-capability"
fi
while true; do
    sleep 1
done
"""


class LauncherFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tree_root = self.root / "deepseek-harness"
        self.tree_root.mkdir()
        (self.tree_root / "package.json").write_text(
            json.dumps({"name": "@deepseek-ai/deepseek-harness", "version": "0.0-test"}),
            encoding="utf-8",
        )
        executable = self.tree_root / "dsh"
        executable.write_text(FAKE_DSH, encoding="utf-8")
        executable.chmod(0o755)
        self.launcher = serve.Launcher(
            [self.tree_root], state_root=self.root / "state", sandbox=FakeCellSandbox()
        )

    def tearDown(self):
        self.launcher.shutdown()
        self.temp.cleanup()

    def tree(self):
        return self.launcher.status()["trees"][0]


class ScannerAndRunner(LauncherFixture):
    def test_only_canonical_upstream_remotes_are_official(self):
        self.assertTrue(launcher_module._official_remote("https://github.com/deepseek-ai/deepseek-harness.git"))
        self.assertTrue(launcher_module._official_remote("git@github.com:deepseek-ai/deepseek-harness.git"))
        self.assertFalse(launcher_module._official_remote("https://example.com/deepseek-ai/deepseek-harness.git"))
        self.assertFalse(launcher_module._official_remote("https://github.com/community/deepseek-harness.git"))

    def test_scanner_uses_strong_artifacts_without_execution(self):
        status = self.launcher.status()
        self.assertEqual(len(status["trees"]), 1)
        tree = status["trees"][0]
        self.assertEqual(tree["version"], "0.0-test")
        self.assertEqual(tree["launchability"], "ready")
        self.assertNotIn("real_path", tree)
        self.assertFalse((self.tree_root / "was-executed").exists())

    def test_unrelated_directory_is_a_coverage_gap(self):
        unrelated = self.root / "unrelated"
        unrelated.mkdir()
        status = self.launcher.add_scan_roots([str(unrelated)])
        self.assertTrue(any("no strong DSH signature" in gap for gap in status["coverage_gaps"]))

    def test_current_upstream_source_layout_and_cli_shape(self):
        upstream = self.root / "upstream-layout"
        cli = upstream / "apps" / "cli"
        (cli / "lib").mkdir(parents=True)
        (cli / "package.json").write_text(
            json.dumps({"name": "@deepseek-ai/dsh", "version": "0.1.2-alpha.3"}), encoding="utf-8"
        )
        (cli / "lib" / "bin.js").write_text("#!/usr/bin/env node\n", encoding="utf-8")
        # Discovery should be tested independently of whichever tools happen to
        # be installed on the host running the Python suite. The real launcher
        # still reports ``missing-node`` when Node is genuinely unavailable.
        fake_node = self.root / "node"
        fake_node.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_node.chmod(0o755)
        real_which = launcher_module.shutil.which

        def fixture_which(command):
            return str(fake_node) if command == "node" else real_which(command)

        with mock.patch("dsh_forge.launcher.shutil.which", side_effect=fixture_which):
            detected = serve.Launcher(
                [upstream], state_root=self.root / "upstream-state", sandbox=FakeCellSandbox()
            )
        try:
            tree = detected.status()["trees"][0]
            preview = detected.preview({
                "tree_id": tree["id"], "surface": "web", "port": detected.suggested_port(),
                "home_mode": "fresh", "workspace": "none"
            })
            self.assertEqual(tree["version"], "0.1.2-alpha.3")
            self.assertIn("apps/cli/lib/bin.js", tree["exe"])
            self.assertEqual(preview["argv"][-6:-5], ["web"])
            self.assertIn("--host", preview["argv"])
            self.assertIn("--no-open", preview["argv"])
            self.assertNotIn("--workspace", preview["argv"])
        finally:
            detected.shutdown()

    def test_scanner_excludes_internal_monorepo_tools(self):
        upstream = self.root / "upstream-monorepo"
        cli = upstream / "apps" / "cli"
        (cli / "lib").mkdir(parents=True)
        (cli / "package.json").write_text(
            json.dumps({"name": "@deepseek-ai/dsh", "version": "0.1.2-alpha.3"}), encoding="utf-8"
        )
        (cli / "lib" / "bin.js").write_text("#!/usr/bin/env node\n", encoding="utf-8")
        internal_packages = (
            ("packages/experimental/webworker-packer", "@deepseek-ai/dsh-experimental-webworker-packer", "lib/bin.js"),
            ("packages/test-support/llm-mock-server", "@deepseek-ai/dsh-llm-mock-server", "src/bin.ts"),
        )
        for relative, name, executable in internal_packages:
            package_root = upstream / relative
            (package_root / Path(executable).parent).mkdir(parents=True)
            (package_root / "package.json").write_text(
                json.dumps({"name": name, "version": "0.1.2-alpha.3"}), encoding="utf-8"
            )
            (package_root / executable).write_text("#!/usr/bin/env node\n", encoding="utf-8")

        real_which = launcher_module.shutil.which

        def fixture_which(command):
            return str(self.root / "node") if command == "node" else real_which(command)

        with mock.patch("dsh_forge.launcher.shutil.which", side_effect=fixture_which):
            detected = serve.Launcher(
                [upstream], state_root=self.root / "monorepo-state", sandbox=FakeCellSandbox()
            )
        try:
            trees = detected.status()["trees"]
            self.assertEqual([tree["name"] for tree in trees], ["@deepseek-ai/dsh"])
            self.assertEqual(trees[0]["path"], launcher_module._display_path(upstream))
        finally:
            detected.shutdown()

    def test_preview_lists_keys_not_secret_values(self):
        old = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = "never-return-this-secret"
        try:
            preview = self.launcher.preview({
                "tree_id": self.tree()["id"], "surface": "headless", "task": "test task", "home_mode": "fresh", "workspace": "none"
            })
        finally:
            if old is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = old
        rendered = json.dumps(preview)
        self.assertNotIn("DEEPSEEK_API_KEY", rendered)
        self.assertNotIn("never-return-this-secret", rendered)
        self.assertIn("not observed", rendered)

    def test_owned_process_launch_logs_and_verified_stop(self):
        # The managed test executor does not expose child /proc records, so the
        # OS birth-identity probe is mocked while the ownership checks remain.
        with mock.patch("dsh_forge.launcher._process_birth", return_value="test-birth"):
            cell = self.launcher.launch({
                "tree_id": self.tree()["id"], "surface": "headless", "task": "test task", "home_mode": "fresh", "workspace": "none"
            })
            self.assertGreater(cell["pid"], 1)
            self.assertEqual(cell["loader"], "not observed")
            for _ in range(20):
                if self.launcher.logs(cell["id"]):
                    break
                import time
                time.sleep(0.02)
            self.assertIn("fake dsh ready", json.dumps(self.launcher.logs(cell["id"])))
            stopped = self.launcher.stop(cell["id"])
            self.assertEqual(stopped["state"], "stopped")

    def test_parallel_web_cells_get_unique_ports_homes_and_workspaces(self):
        with mock.patch("dsh_forge.launcher._process_birth", return_value="test-birth"):
            first = self.launcher.launch({
                "tree_id": self.tree()["id"], "surface": "web", "port": "auto",
                "home_mode": "fresh", "workspace": "managed"
            })
            second = self.launcher.launch({
                "tree_id": self.tree()["id"], "surface": "web", "port": "auto",
                "home_mode": "fresh", "workspace": "managed"
            })
            self.assertNotEqual(first["port"], second["port"])
            self.assertNotEqual(first["home"], second["home"])
            self.assertNotEqual(first["workspace"], second["workspace"])
            self.assertEqual(first["workspace_isolation"], "managed empty")
            self.assertTrue(first["resources"]["enforced"])
            self.assertTrue(first["sandboxed"])
            self.assertEqual(first["execution_backend"], "apptainer-cell-v1")
            self.assertIn(first["agent_state"], {"working", "idle"})
            self.assertIsInstance(first["recent_logs"], list)
            self.launcher.stop(first["id"])
            self.launcher.stop(second["id"])

    def test_clone_session_gets_another_port_and_sanitized_state_copy(self):
        with mock.patch("dsh_forge.launcher._process_birth", return_value="test-birth"):
            source = self.launcher.launch({
                "tree_id": self.tree()["id"], "surface": "web", "port": "auto",
                "home_mode": "fresh", "workspace": "managed"
            })
            source_private = self.launcher._cells[source["id"]]
            home = Path(source_private["real_home"])
            workspace = Path(source_private["real_workspace"])
            (home / "sessions").mkdir()
            (home / "sessions" / "one.jsonl").write_text("session", encoding="utf-8")
            (home / ".env").write_text("SECRET=value", encoding="utf-8")
            (workspace / "artifact.txt").write_text("artifact", encoding="utf-8")
            cloned = self.launcher.clone(source["id"])
            cloned_private = self.launcher._cells[cloned["id"]]
            self.assertNotEqual(source["id"], cloned["id"])
            self.assertNotEqual(source["port"], cloned["port"])
            self.assertEqual((Path(cloned_private["real_home"]) / "sessions" / "one.jsonl").read_text(), "session")
            self.assertFalse((Path(cloned_private["real_home"]) / ".env").exists())
            self.assertEqual((Path(cloned_private["real_workspace"]) / "artifact.txt").read_text(), "artifact")
            self.assertEqual(self.launcher.artifacts(cloned["id"])[0]["path"], "artifact.txt")
            self.launcher.stop(source["id"])
            self.launcher.stop(cloned["id"])

    def test_persisted_identity_is_recovered_and_can_be_stopped(self):
        with mock.patch("dsh_forge.launcher._process_birth", return_value="test-birth"):
            cell = self.launcher.launch({
                "tree_id": self.tree()["id"], "surface": "headless", "task": "test task", "home_mode": "fresh", "workspace": "none"
            })
            recovered = serve.Launcher(
                [self.tree_root], state_root=self.root / "state", sandbox=FakeCellSandbox()
            )
            try:
                restored = next(item for item in recovered.status()["cells"] if item["id"] == cell["id"])
                self.assertEqual(restored["process"], "alive")
                self.assertEqual(recovered.stop(cell["id"])["state"], "stopped")
            finally:
                recovered.shutdown()

    def test_protected_and_unmanaged_ports_are_never_killed(self):
        with self.assertRaisesRegex(serve.LauncherError, "protected"):
            self.launcher.preview({
                "tree_id": self.tree()["id"], "surface": "web", "port": 3090,
                "home_mode": "fresh", "workspace": "none"
            })
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupant:
            occupant.bind(("127.0.0.1", 0))
            occupant.listen()
            port = occupant.getsockname()[1]
            with self.assertRaisesRegex(serve.LauncherError, "unmanaged"):
                self.launcher.preview({
                    "tree_id": self.tree()["id"], "surface": "web", "port": port,
                    "home_mode": "fresh", "workspace": "none"
                })
            self.assertGreater(occupant.fileno(), -1)

    def test_authenticated_web_url_is_explicit_and_not_in_cell_status(self):
        port = self.launcher.suggested_port()
        with mock.patch("dsh_forge.launcher._process_birth", return_value="test-birth"):
            cell = self.launcher.launch({
                "tree_id": self.tree()["id"], "surface": "web", "port": port,
                "home_mode": "fresh", "workspace": "none"
            })
            for _ in range(20):
                try:
                    url = self.launcher.open_url(cell["id"])
                    break
                except serve.LauncherError:
                    import time
                    time.sleep(0.02)
            else:
                self.fail("authenticated web URL was not observed")
            self.assertIn("token=test-capability", url)
            public = next(item for item in self.launcher.status()["cells"] if item["id"] == cell["id"])
            self.assertNotIn("open_url", public)
            self.assertTrue(public["open_ready"])
            rendered_logs = json.dumps(self.launcher.logs(cell["id"]))
            self.assertNotIn("token=test-capability", rendered_logs)
            self.assertIn("authenticated URL redacted", rendered_logs)
            self.launcher.stop(cell["id"])

    def test_host_home_and_existing_workspace_are_rejected(self):
        with self.assertRaisesRegex(serve.LauncherError, "host DSH home is never mounted"):
            self.launcher.preview({
                "tree_id": self.tree()["id"], "surface": "headless", "task": "test task",
                "home_mode": "exclusive", "workspace": "managed",
            })
        with self.assertRaisesRegex(serve.LauncherError, "host workspaces are not mounted writable"):
            self.launcher.preview({
                "tree_id": self.tree()["id"], "surface": "headless", "task": "test task",
                "home_mode": "fresh", "workspace": str(self.root),
            })

    def test_safe_clone_excludes_secrets_sessions_and_symlinks(self):
        source = self.root / "home-template"
        source.mkdir()
        (source / "safe.txt").write_text("safe", encoding="utf-8")
        (source / ".env").write_text("SECRET=value", encoding="utf-8")
        (source / "sessions").mkdir()
        (source / "sessions" / "active").write_text("session", encoding="utf-8")
        (self.root / "outside-secret").write_text("outside", encoding="utf-8")
        (source / "linked-secret").symlink_to(self.root / "outside-secret")
        with mock.patch("dsh_forge.launcher._process_birth", return_value="test-birth"):
            cell = self.launcher.launch({
                "tree_id": self.tree()["id"], "surface": "headless", "task": "test task", "home_mode": "clone",
                "clone_source": str(source), "workspace": "none"
            })
            cloned = Path(self.launcher._cells[cell["id"]]["real_home"])
            self.assertEqual((cloned / "safe.txt").read_text(encoding="utf-8"), "safe")
            self.assertFalse((cloned / ".env").exists())
            self.assertFalse((cloned / "sessions").exists())
            self.assertFalse((cloned / "linked-secret").exists())
            self.launcher.stop(cell["id"])


class LauncherServer(LauncherFixture):
    def setUp(self):
        super().setUp()

        class QuietHandler(serve.LauncherUIHandler):
            def log_message(self, *_args):
                pass

        self.server = serve.LauncherHTTPServer(
            ("127.0.0.1", 0), partial(QuietHandler, directory=str(serve.WEB_ROOT)), self.launcher, session_token="test-session"
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = "http://127.0.0.1:" + str(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        super().tearDown()

    def establish_session(self):
        with urllib.request.urlopen(self.url + "/api/v1/status", timeout=3) as response:
            self.assertEqual(response.status, 200)
            cookie = response.headers["Set-Cookie"].split(";", 1)[0]
            payload = json.load(response)
        return cookie, payload

    def request(self, path, body, cookie=None, origin=True):
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = cookie
        if origin:
            headers["Origin"] = self.url
        return urllib.request.urlopen(
            urllib.request.Request(self.url + path, data=json.dumps(body).encode(), headers=headers, method="POST"), timeout=3
        )

    def test_index_and_local_dependencies(self):
        for path in ["/", "/launcher.js", "/support.js", "/vendor/react.production.min.js", "/vendor/react-dom.production.min.js"]:
            with urllib.request.urlopen(self.url + path, timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                csp = response.headers["Content-Security-Policy"]
                self.assertIn("script-src 'self'", csp)
                self.assertNotIn("'unsafe-eval'", csp)
                self.assertGreater(len(response.read()), 1000)

    def test_source_git_and_directory_listings_are_not_served(self):
        for path in ["/.git/config", "/../.git/config", "/scripts/seed_catalog.py", "/vendor/"]:
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(self.url + path, timeout=3)
            self.assertEqual(context.exception.code, 404)

    def test_mutations_require_the_launcher_session(self):
        body = {"tree_id": self.tree()["id"], "surface": "headless", "task": "test task", "home_mode": "fresh", "workspace": "none"}
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.request("/api/v1/launches/preview", body)
        self.assertEqual(context.exception.code, 403)
        cookie, _ = self.establish_session()
        with self.request("/api/v1/launches/preview", body, cookie=cookie) as response:
            payload = json.load(response)
        self.assertIn("argv", payload)
        bad_origin = urllib.request.Request(
            self.url + "/api/v1/launches/preview",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Cookie": cookie, "Origin": "http://127.0.0.1:65534"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(bad_origin, timeout=3)
        self.assertEqual(context.exception.code, 403)

    def test_status_is_live_and_cookie_is_hardened(self):
        _, payload = self.establish_session()
        self.assertEqual(payload["mode"], "live-local-sidecar")
        with urllib.request.urlopen(self.url + "/api/v1/status", timeout=3) as response:
            cookie = response.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertEqual(payload["sandbox"]["mode"], "fake-apptainer-cell-v1")
        self.assertTrue(payload["sandbox"]["ready"])
        self.assertFalse(payload["sandbox"]["hostile_code_isolation"])

    def test_sandbox_mutation_requires_session_and_uses_tree_endpoint(self):
        tree = self.launcher._trees[self.tree()["id"]]
        tree["trust"] = "foreign"
        tree["launchability"] = "sandbox-testable"
        self.launcher.sandbox = mock.Mock()
        self.launcher.sandbox.status.return_value = {
            "ready": True, "image_sha256": "b" * 64, "hostile_code_isolation": False
        }
        self.launcher.sandbox.test_tree.return_value = {
            "status": "passed", "exit_code": 0, "duration_ms": 1, "output": "help",
            "network": "none", "secrets_forwarded": False, "image_sha256": "b" * 64,
            "command_summary": "captured CLI help probe",
        }
        path = "/api/v1/trees/" + tree["id"] + "/sandbox-test"
        with self.assertRaises(urllib.error.HTTPError) as context:
            self.request(path, {})
        self.assertEqual(context.exception.code, 403)
        cookie, _ = self.establish_session()
        with mock.patch.object(self.launcher, "scan", return_value=self.launcher.status()):
            tree["git"] = {"sha": "abc123", "branch": "main", "dirty": False}
            with self.request(path, {}, cookie=cookie) as response:
                payload = json.load(response)
        self.assertEqual(payload["status"], "passed")
        self.launcher.sandbox.test_tree.assert_called_once()

    def test_api_does_not_accept_non_loopback_host(self):
        request = urllib.request.Request(self.url + "/api/v1/status", headers={"Host": "example.com"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(context.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
