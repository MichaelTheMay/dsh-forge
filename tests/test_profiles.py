"""Local DSH profile auto-detection.

These tests cover the "already installed on this machine" path, which is
deliberately separate from the signed-package boundary: detection reads
manifests only, and running a detected profile is an explicit, unsandboxed
host action that the launcher must describe honestly.
"""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from dsh_forge import cli
from dsh_forge.launcher import Launcher, LauncherError
from tests.helpers import FakeCellSandbox


FAKE_DSH = """#!/bin/sh
trap 'exit 0' TERM INT
while true; do sleep 1; done
"""


def manifest(name, bundles, dependencies=None, extra=None):
    value = {
        "name": name,
        "version": "1.0.0",
        "dependencies": dependencies or {},
        "dsh": {"profile": {"bundles": bundles}},
    }
    value.update(extra or {})
    return json.dumps(value)


class ProfileFixture(unittest.TestCase):
    """Shared temporary DSH home. Holds no tests so subclasses never re-run them."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.home = self.root / "dsh-home"
        self.profiles = self.home / "profiles"
        self.profiles.mkdir(parents=True)

        self.tree = self.root / "deepseek-harness"
        self.tree.mkdir()
        (self.tree / "package.json").write_text(
            json.dumps({"name": "@deepseek-ai/deepseek-harness", "version": "0.1.2-rc.1"}),
            encoding="utf-8",
        )
        executable = self.tree / "dsh"
        executable.write_text(FAKE_DSH, encoding="utf-8")
        executable.chmod(0o755)

        # Pin DSH_HOME so a developer's real ~/.dsh can never leak into assertions.
        self.environment = mock.patch.dict(
            os.environ,
            {
                "DSH_HOME": str(self.home),
                "DSH_FORGE_VERSIONS_DIR": str(self.root / "managed-versions"),
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def tearDown(self):
        self.temp.cleanup()

    def write_profile(self, name, body):
        directory = self.profiles / name
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "package.json").write_text(body, encoding="utf-8")
        return directory

    def build(self, **options):
        launcher = Launcher([self.tree], state_root=self.root / "state", sandbox=FakeCellSandbox(), **options)
        self.addCleanup(launcher.shutdown)
        return launcher

    def profiles_by_name(self, launcher):
        return {profile["name"]: profile for profile in launcher.status()["profiles"]}


class LocalProfileDetectionTests(ProfileFixture):
    def test_installed_profiles_are_detected_from_manifests_without_executing_them(self):
        canary = self.root / "profile-code-ran"
        self.write_profile("web", manifest(
            "dsh-profile-web",
            ["@deepseek-ai/dsh-web-app"],
            {"dsh-vet": "0.3.0", "@nanmicoder/dsh-agent-teams": "0.1.16-rc.1"},
            # A hostile manifest cannot make detection run anything.
            {"scripts": {"postinstall": f"touch {canary}", "start": f"touch {canary}"}},
        ))
        self.write_profile("coding", manifest("dsh-profile-coding", ["@deepseek-ai/dsh-tui-app"]))

        found = self.profiles_by_name(self.build())
        self.assertEqual(sorted(found), ["coding", "web"])
        self.assertFalse(canary.exists(), "detection must never execute profile lifecycle scripts")

        web = found["web"]
        self.assertEqual(web["surface"], "web")
        self.assertEqual(web["launchability"], "one-click")
        self.assertEqual(web["bundles"], ["@deepseek-ai/dsh-web-app"])
        # Dependencies are the installed plugins, reported in a stable order.
        self.assertEqual(web["dependencies"], ["@nanmicoder/dsh-agent-teams", "dsh-vet"])
        self.assertEqual(found["coding"]["surface"], "terminal")
        self.assertEqual(found["coding"]["launchability"], "terminal-only")

    def test_public_profile_records_never_leak_absolute_host_paths(self):
        self.write_profile("web", manifest("dsh-profile-web", ["@deepseek-ai/dsh-web-app"]))
        profile = self.profiles_by_name(self.build())["web"]
        self.assertFalse(any(key.startswith("real_") for key in profile))
        self.assertNotIn(str(self.home), json.dumps(profile))

    def test_surface_classification_gates_one_click_to_web_and_headless(self):
        self.write_profile("web", manifest("w", ["@deepseek-ai/dsh-web-app"]))
        self.write_profile("headless", manifest("h", ["@deepseek-ai/dsh-headless"]))
        self.write_profile("coding", manifest("c", ["@deepseek-ai/dsh-tui-app"]))
        self.write_profile("sdk", manifest("s", ["@deepseek-ai/dsh-sdk-app"]))

        found = self.profiles_by_name(self.build())
        self.assertEqual(
            {name: profile["surface"] for name, profile in found.items()},
            {"web": "web", "headless": "headless", "coding": "terminal", "sdk": "service"},
        )
        one_click = {name for name, profile in found.items() if profile["launchability"] == "one-click"}
        self.assertEqual(one_click, {"web", "headless"})
        # Everything else still gets a runnable command instead of a dead button.
        for name in {"coding", "sdk"}:
            self.assertIn(found[name]["id"], found[name]["command"])

    def test_unusable_and_hostile_profile_entries_are_skipped(self):
        self.write_profile("web", manifest("w", ["@deepseek-ai/dsh-web-app"]))
        (self.profiles / "no-manifest").mkdir()
        self.write_profile("broken-json", "{ not json")
        self.write_profile("no-bundles", json.dumps({"name": "x", "dsh": {"profile": {}}}))
        self.write_profile("bundles-not-strings", json.dumps({"name": "x", "dsh": {"profile": {"bundles": [{}]}}}))
        self.write_profile("not-a-profile", json.dumps({"name": "plain-package"}))
        self.write_profile("bad name!", manifest("x", ["@deepseek-ai/dsh-web-app"]))
        (self.profiles / "loose-file.json").write_text("{}", encoding="utf-8")

        self.assertEqual(list(self.profiles_by_name(self.build())), ["web"])

    def test_symlinked_profiles_are_refused_rather_than_followed(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "package.json").write_text(manifest("x", ["@deepseek-ai/dsh-web-app"]), encoding="utf-8")
        try:
            (self.profiles / "linked").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"symlink creation is unavailable here: {error}")
        self.assertEqual(self.profiles_by_name(self.build()), {})

    def test_profile_identity_is_stable_per_home_and_survives_a_rescan(self):
        self.write_profile("web", manifest("w", ["@deepseek-ai/dsh-web-app"]))
        launcher = self.build()
        first = self.profiles_by_name(launcher)["web"]["id"]
        launcher.scan()
        self.assertEqual(self.profiles_by_name(launcher)["web"]["id"], first)

        other_home = self.root / "second-home"
        (other_home / "profiles" / "web").mkdir(parents=True)
        (other_home / "profiles" / "web" / "package.json").write_text(
            manifest("w", ["@deepseek-ai/dsh-web-app"]), encoding="utf-8"
        )
        combined = self.build(dsh_homes=[str(other_home)]).status()["profiles"]
        identities = {profile["id"] for profile in combined}
        self.assertEqual(len(combined), 2, "the same profile name in two homes must stay distinct")
        self.assertEqual(len(identities), 2)
        self.assertIn(first, identities)

    def test_status_declares_the_unsandboxed_local_profile_boundary(self):
        boundary = self.build().status()["capabilities"]["local_profiles"]
        self.assertFalse(boundary["discovery_executes_code"])
        self.assertFalse(boundary["sandboxed"])
        self.assertTrue(boundary["terminal_cli_available"])
        self.assertEqual(boundary["one_click_surfaces"], ["web", "headless"])


class LocalProfileRunPlanTests(ProfileFixture):
    def setUp(self):
        super().setUp()
        self.write_profile("web", manifest("w", ["@deepseek-ai/dsh-web-app"], {"dsh-vet": "0.3.0"}))
        self.write_profile("headless", manifest("h", ["@deepseek-ai/dsh-headless"]))
        self.write_profile("coding", manifest("c", ["@deepseek-ai/dsh-tui-app"]))
        self.launcher = self.build()
        self.found = self.profiles_by_name(self.launcher)

    def test_preview_states_the_host_boundary_and_discloses_forwarded_credentials(self):
        with mock.patch.dict(os.environ, {"DEEPSEEK_API_KEY": "secret-value"}):
            preview = self.launcher.preview_profile({"profile_id": self.found["web"]["id"]})

        self.assertIn("DEEPSEEK_API_KEY", preview["credential_keys"])
        # Keys are disclosed; the secret itself is never echoed back to the UI.
        self.assertNotIn("secret-value", json.dumps(preview))
        notes = " ".join(preview["notes"]).lower()
        self.assertIn("host", notes)
        self.assertIn("apptainer", notes)
        self.assertIn("--profile", preview["argv"])
        self.assertIn("web", preview["argv"])
        self.assertIn("DSH_HOME", preview["command"])

    def test_headless_profiles_require_a_task_and_reject_an_oversized_one(self):
        headless = self.found["headless"]["id"]
        with self.assertRaises(LauncherError):
            self.launcher.preview_profile({"profile_id": headless})
        with self.assertRaises(LauncherError):
            self.launcher.preview_profile({"profile_id": headless, "task": "x" * 20_001})
        preview = self.launcher.preview_profile({"profile_id": headless, "task": "summarize the repo"})
        self.assertEqual(preview["argv"][-1], "summarize the repo")

    def test_terminal_profiles_are_not_one_click_and_unknown_ids_are_refused(self):
        with self.assertRaises(LauncherError):
            self.launcher.preview_profile({"profile_id": self.found["coding"]["id"]})
        with self.assertRaises(LauncherError):
            self.launcher.preview_profile({"profile_id": "profile_" + "0" * 16})
        with self.assertRaises(LauncherError):
            self.launcher.preview_profile({"profile_id": ""})

    def test_protected_ports_and_invalid_arguments_are_refused(self):
        web = self.found["web"]["id"]
        with self.assertRaises(LauncherError):
            self.launcher.preview_profile({"profile_id": web, "port": 3090})
        with self.assertRaises(LauncherError):
            self.launcher.preview_profile({"profile_id": web, "port": "not-a-port"})
        with self.assertRaises(LauncherError):
            self.launcher.preview_profile({"profile_id": web, "extra_args": "--flag"})
        with self.assertRaises(LauncherError):
            self.launcher.preview_profile({"profile_id": web, "extra_args": ["--flag\0injected"]})

    def test_web_preview_binds_loopback_only(self):
        preview = self.launcher.preview_profile({"profile_id": self.found["web"]["id"]})
        self.assertIn("--host", preview["argv"])
        self.assertEqual(preview["argv"][preview["argv"].index("--host") + 1], "127.0.0.1")
        self.assertIn("--no-open", preview["argv"])


class LocalProfileCliTests(ProfileFixture):
    def invoke(self, launcher, *arguments):
        stdout = io.StringIO()
        stderr = io.StringIO()

        def factory(**_options):
            return launcher

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.run(["--json", *arguments], launcher_factory=factory)
        return code, json.loads(stdout.getvalue() or stderr.getvalue())

    def test_profiles_list_exposes_detected_profiles_over_the_cli(self):
        self.write_profile("web", manifest("w", ["@deepseek-ai/dsh-web-app"]))
        self.write_profile("coding", manifest("c", ["@deepseek-ai/dsh-tui-app"]))
        launcher = self.build()

        code, payload = self.invoke(launcher, "profiles", "list")
        self.assertEqual(code, 0)
        data = payload["data"] if "data" in payload else payload
        names = sorted(profile["name"] for profile in data["profiles"])
        self.assertEqual(names, ["coding", "web"])
        self.assertTrue(data["dsh_homes"])

    def test_profiles_run_refuses_an_unknown_profile_without_starting_anything(self):
        self.write_profile("web", manifest("w", ["@deepseek-ai/dsh-web-app"]))
        launcher = self.build()
        with mock.patch("subprocess.run") as runner:
            code, _ = self.invoke(launcher, "profiles", "run", "profile_" + "0" * 16)
        self.assertNotEqual(code, 0)
        runner.assert_not_called()

    def test_profiles_run_forwards_the_exact_argv_and_home_without_a_shell(self):
        self.write_profile("coding", manifest("c", ["@deepseek-ai/dsh-tui-app"]))
        launcher = self.build()
        identity = self.profiles_by_name(launcher)["coding"]["id"]

        with mock.patch("dsh_forge.launcher.subprocess.run") as runner:
            runner.return_value = mock.Mock(returncode=0)
            code, payload = self.invoke(launcher, "profiles", "run", identity, "--", "--verbose")

        self.assertEqual(code, 0)
        arguments, options = runner.call_args
        argv = arguments[0]
        self.assertIsInstance(argv, list)
        self.assertNotIn("shell", options)
        self.assertEqual(argv[-3:], ["--profile", "coding", "--verbose"])
        self.assertEqual(options["env"]["DSH_HOME"], str(self.home))
        data = payload["data"] if "data" in payload else payload
        self.assertEqual(data["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
