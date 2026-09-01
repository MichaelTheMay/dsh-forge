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


FAKE_DSH = """#!/bin/sh
trap 'exit 0' TERM INT
echo 'fake dsh ready'
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
        self.launcher = serve.Launcher([self.tree_root], state_root=self.root / "state")

    def tearDown(self):
        self.launcher.shutdown()
        self.temp.cleanup()

    def tree(self):
        return self.launcher.status()["trees"][0]


class ScannerAndRunner(LauncherFixture):
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

    def test_preview_lists_keys_not_secret_values(self):
        old = os.environ.get("DEEPSEEK_API_KEY")
        os.environ["DEEPSEEK_API_KEY"] = "never-return-this-secret"
        try:
            preview = self.launcher.preview({
                "tree_id": self.tree()["id"], "surface": "headless", "home_mode": "fresh", "workspace": "none"
            })
        finally:
            if old is None:
                os.environ.pop("DEEPSEEK_API_KEY", None)
            else:
                os.environ["DEEPSEEK_API_KEY"] = old
        rendered = json.dumps(preview)
        self.assertIn("DEEPSEEK_API_KEY", rendered)
        self.assertNotIn("never-return-this-secret", rendered)
        self.assertIn("not observed", rendered)

    def test_owned_process_launch_logs_and_verified_stop(self):
        # The managed test executor does not expose child /proc records, so the
        # OS birth-identity probe is mocked while the ownership checks remain.
        with mock.patch("dsh_forge.launcher._process_birth", return_value="test-birth"):
            cell = self.launcher.launch({
                "tree_id": self.tree()["id"], "surface": "headless", "home_mode": "fresh", "workspace": "none"
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

    def test_persisted_identity_is_recovered_and_can_be_stopped(self):
        with mock.patch("dsh_forge.launcher._process_birth", return_value="test-birth"):
            cell = self.launcher.launch({
                "tree_id": self.tree()["id"], "surface": "headless", "home_mode": "fresh", "workspace": "none"
            })
            recovered = serve.Launcher([self.tree_root], state_root=self.root / "state")
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

    def test_exclusive_home_has_one_writer(self):
        with mock.patch("dsh_forge.launcher._process_birth", return_value="test-birth"):
            first = self.launcher.launch({
                "tree_id": self.tree()["id"], "surface": "headless", "home_mode": "exclusive", "workspace": "none"
            })
            with self.assertRaisesRegex(serve.LauncherError, "writable-home lease"):
                self.launcher.launch({
                    "tree_id": self.tree()["id"], "surface": "headless", "home_mode": "exclusive", "workspace": "none"
                })
            self.launcher.stop(first["id"])

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
                "tree_id": self.tree()["id"], "surface": "headless", "home_mode": "clone",
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
        for path in ["/", "/support.js", "/vendor/react.production.min.js", "/vendor/react-dom.production.min.js"]:
            with urllib.request.urlopen(self.url + path, timeout=3) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
                self.assertGreater(len(response.read()), 1000)

    def test_source_git_and_directory_listings_are_not_served(self):
        for path in ["/.git/config", "/../.git/config", "/scripts/seed_catalog.py", "/vendor/"]:
            with self.assertRaises(urllib.error.HTTPError) as context:
                urllib.request.urlopen(self.url + path, timeout=3)
            self.assertEqual(context.exception.code, 404)

    def test_mutations_require_the_launcher_session(self):
        body = {"tree_id": self.tree()["id"], "surface": "headless", "home_mode": "fresh", "workspace": "none"}
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

    def test_api_does_not_accept_non_loopback_host(self):
        request = urllib.request.Request(self.url + "/api/v1/status", headers={"Host": "example.com"})
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(context.exception.code, 403)


if __name__ == "__main__":
    unittest.main()
