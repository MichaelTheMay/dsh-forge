import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from dsh_forge.launcher import Launcher, LauncherError
from dsh_forge.sandbox import ApptainerSandbox, SandboxConfig, SandboxError


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, command, **options):
        self.calls.append((command, options))
        output = "v22.19.0\n" if command[-2:] == ["node", "--version"] else "DeepSeek Harness help\n"
        return subprocess.CompletedProcess(command, 0, stdout=output)


class SandboxFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image = self.root / "node.sif"
        self.image.write_bytes(b"immutable sandbox fixture")
        self.image.chmod(0o400)
        self.digest = hashlib.sha256(self.image.read_bytes()).hexdigest()
        self.binary = self.root / "apptainer"
        self.binary.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        self.binary.chmod(0o700)
        self.runner = RecordingRunner()

    def tearDown(self):
        self.temp.cleanup()

    def sandbox(self):
        return ApptainerSandbox(
            SandboxConfig.from_values(
                image=self.image,
                image_sha256=self.digest,
                binary=str(self.binary),
                cpus="2",
                memory="4G",
                pids_limit=128,
                timeout_seconds=12,
            ),
            self.root / "sandbox-state",
            runner=self.runner,
        )


class ApptainerPolicyTests(SandboxFixture):
    def test_capability_probe_is_fail_closed_and_records_enforced_policy(self):
        sandbox = self.sandbox()
        status = sandbox.status()
        self.assertTrue(status["ready"])
        self.assertEqual(status["network"], "none")
        self.assertFalse(status["host_home_exposed"])
        self.assertFalse(status["secrets_forwarded"])
        self.assertFalse(status["hostile_code_isolation"])
        command, options = self.runner.calls[0]
        rendered = " ".join(command)
        for flag in (
            "--containall", "--cleanenv", "--no-eval", "--no-privs",
            "--no-mount", "--net", "--network none", "--cpus 2",
            "--memory 4G", "--pids-limit 128",
        ):
            self.assertIn(flag, rendered)
        self.assertNotIn("GITHUB_TOKEN", options["env"])
        self.assertNotIn("GH_TOKEN", options["env"])
        self.assertEqual(options["stdin"], subprocess.DEVNULL)

    def test_image_pin_and_file_permissions_are_required(self):
        mismatch = ApptainerSandbox(
            SandboxConfig.from_values(self.image, "0" * 64, str(self.binary)),
            self.root / "bad-pin",
            runner=self.runner,
        )
        self.assertFalse(mismatch.ready)
        self.assertIn("does not match", mismatch.status()["reason"])
        self.image.chmod(0o600)
        writable = ApptainerSandbox(
            SandboxConfig.from_values(self.image, self.digest, str(self.binary)),
            self.root / "bad-mode",
            runner=self.runner,
        )
        self.assertFalse(writable.ready)
        self.assertIn("must be read-only", writable.status()["reason"])

    def test_image_symlink_is_rejected_instead_of_resolved(self):
        link = self.root / "linked.sif"
        link.symlink_to(self.image)
        sandbox = ApptainerSandbox(
            SandboxConfig.from_values(link, self.digest, str(self.binary)),
            self.root / "linked-state",
            runner=self.runner,
        )
        self.assertFalse(sandbox.ready)
        self.assertIn("non-symlink", sandbox.status()["reason"])

    def test_tree_probe_mounts_source_read_only_and_writable_state_separately(self):
        sandbox = self.sandbox()
        tree = self.root / "community-fork"
        tree.mkdir()
        cli = tree / "dsh.js"
        cli.write_text("#!/usr/bin/env node\n", encoding="utf-8")
        result = sandbox.test_tree({"real_path": str(tree), "real_exe": str(cli)})
        self.assertEqual(result["status"], "passed")
        command, options = self.runner.calls[-1]
        rendered = " ".join(command)
        self.assertIn("dst=/opt/dsh,ro,nonested", rendered)
        self.assertIn("dst=/home/dsh,rw,nonested", rendered)
        self.assertIn("dst=/workspace,rw,nonested", rendered)
        self.assertEqual(command[-3:], ["node", "/opt/dsh/dsh.js", "--help"])
        self.assertEqual(result["executable_sha256"], hashlib.sha256(cli.read_bytes()).hexdigest())
        self.assertNotIn(str(Path.home()), rendered)
        self.assertEqual(set(options["env"]).intersection({"GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY"}), set())

    def test_invalid_limits_are_rejected_before_runtime_execution(self):
        with self.assertRaisesRegex(SandboxError, "CPU"):
            SandboxConfig.from_values(cpus="0")
        with self.assertRaisesRegex(SandboxError, "memory"):
            SandboxConfig.from_values(memory="unlimited")
        with self.assertRaisesRegex(SandboxError, "PID"):
            SandboxConfig.from_values(pids_limit=1)


class FakeSandbox:
    ready = True

    def status(self):
        return {
            "mode": "apptainer-networkless-test",
            "ready": True,
            "reason": "test fixture",
            "image_sha256": "a" * 64,
            "hostile_code_isolation": False,
        }

    def test_tree(self, _tree):
        return {
            "status": "passed",
            "exit_code": 0,
            "duration_ms": 3,
            "output": "help only",
            "network": "none",
            "secrets_forwarded": False,
            "image_sha256": "a" * 64,
            "command_summary": "captured CLI help probe",
        }


class LauncherSandboxBoundaryTests(unittest.TestCase):
    def test_foreign_tree_can_be_tested_but_never_host_launched(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            tree = root / "fork"
            tree.mkdir()
            (tree / "package.json").write_text(
                '{"name":"@community/deepseek-harness","version":"1.0.0"}', encoding="utf-8"
            )
            cli = tree / "dsh"
            cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            cli.chmod(0o755)
            subprocess.run(["git", "init", "-q", str(tree)], check=True)
            subprocess.run(["git", "-C", str(tree), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(tree), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(tree), "add", "package.json", "dsh"], check=True)
            subprocess.run(["git", "-C", str(tree), "commit", "-qm", "fixture"], check=True)
            state = root / "state"
            with mock.patch("dsh_forge.launcher._trust_for", return_value="foreign"):
                launcher = Launcher([tree], state_root=state, sandbox=FakeSandbox())
                try:
                    record = launcher.status()["trees"][0]
                    self.assertEqual(record["launchability"], "sandbox-testable")
                    result = launcher.sandbox_test(record["id"])
                    self.assertEqual(result["status"], "passed")
                    self.assertEqual(launcher.status()["trees"][0]["launchability"], "sandbox-tested")
                    with self.assertRaisesRegex(LauncherError, "cannot launch as host processes"):
                        launcher.preview({"tree_id": record["id"], "surface": "web"})
                finally:
                    launcher.shutdown()
            with mock.patch("dsh_forge.launcher._trust_for", return_value="foreign"):
                recovered = Launcher([tree], state_root=state, sandbox=FakeSandbox())
            try:
                restored = recovered.status()["trees"][0]
                self.assertEqual(restored["launchability"], "sandbox-tested")
                self.assertEqual(restored["sandbox_test"]["status"], "passed")
            finally:
                recovered.shutdown()


if __name__ == "__main__":
    unittest.main()
