import hashlib
import json
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
        self.assertEqual(status["resource_limits"]["scope"], "per-cell-cgroup")
        command, options = self.runner.calls[-1]
        rendered = " ".join(command)
        for flag in (
            "--containall", "--cleanenv", "--no-eval", "--no-privs",
            "--no-mount", "--net", "--network none", "--cpus 2",
            "--memory 4G", "--pids-limit 128",
        ):
            self.assertIn(flag, rendered)
        self.assertNotIn("GITHUB_TOKEN", options["env"])
        self.assertNotIn("GH_TOKEN", options["env"])
        self.assertEqual(options["env"]["HOME"], str(sandbox.runtime_home))
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
        self.assertIn("dst=/opt/dsh,ro", rendered)
        self.assertIn("--home", command)
        self.assertIn(":/home/dsh", rendered)
        self.assertIn("dst=/workspace", rendered)
        self.assertNotIn(",rw", rendered)
        self.assertNotIn("nonested", rendered)
        self.assertEqual(command[-3:], ["node", "/opt/dsh/dsh.js", "--help"])
        self.assertEqual(result["executable_sha256"], hashlib.sha256(cli.read_bytes()).hexdigest())
        self.assertNotIn(str(Path.home()), rendered)
        self.assertEqual(set(options["env"]).intersection({"GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY"}), set())

    def test_mount_spec_uses_apptainer_compatible_unquoted_source(self):
        mount = ApptainerSandbox._mount(self.root / "plain path", "/workspace", read_only=False)
        self.assertEqual(mount, f"type=bind,src={self.root / 'plain path'},dst=/workspace")
        self.assertNotIn('src="', mount)
        with self.assertRaisesRegex(SandboxError, "unsupported characters"):
            ApptainerSandbox._mount(self.root / "comma,path", "/workspace", read_only=False)

    def test_replaced_source_symlink_is_rejected_before_process_creation(self):
        sandbox = self.sandbox()
        tree = self.root / "captured-tree"
        tree.mkdir()
        cli = tree / "dsh"
        cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        cli.chmod(0o755)
        linked = self.root / "replaced-tree"
        linked.symlink_to(tree, target_is_directory=True)
        calls_before = len(self.runner.calls)
        with self.assertRaisesRegex(SandboxError, "replaced by a symlink"):
            sandbox.cell_plan(
                tree={"real_path": str(linked), "real_exe": str(linked / "dsh")},
                home=self.root, workspace=self.root, surface="headless", task="task",
                port=None, profile="tui-min", network="none", gpu=False,
            )
        self.assertEqual(len(self.runner.calls), calls_before)

    def test_invalid_limits_are_rejected_before_runtime_execution(self):
        with self.assertRaisesRegex(SandboxError, "CPU"):
            SandboxConfig.from_values(cpus="0")
        with self.assertRaisesRegex(SandboxError, "memory"):
            SandboxConfig.from_values(memory="unlimited")
        with self.assertRaisesRegex(SandboxError, "PID"):
            SandboxConfig.from_values(pids_limit=1)

    def test_complete_cell_plan_is_supervised_pinned_and_secret_free(self):
        sandbox = self.sandbox()
        tree = self.root / "local-harness"
        tree.mkdir()
        cli = tree / "dsh"
        cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        cli.chmod(0o755)
        home = self.root / "cell-home"
        workspace = self.root / "cell-workspace"
        home.mkdir()
        workspace.mkdir()
        plan = sandbox.cell_plan(
            tree={
                "real_path": str(tree), "real_exe": str(cli),
                "executable_sha256": hashlib.sha256(cli.read_bytes()).hexdigest(),
            },
            home=home, workspace=workspace, surface="headless", task="complete task",
            port=None, profile="tui-min", network="none", gpu=False,
        )
        rendered = " ".join(plan["argv"])
        self.assertIn("timeout", plan["argv"][0])
        self.assertIn("--foreground", plan["argv"])
        self.assertIn(str(self.image), plan["argv"])
        self.assertIn("--network none", rendered)
        self.assertIn("dst=/opt/dsh,ro", rendered)
        self.assertEqual(plan["argv"][-3:], ["/opt/dsh/dsh", "headless", "complete task"])
        self.assertTrue(plan["resources"]["enforced"])
        self.assertFalse(plan["secrets_forwarded"])
        self.assertEqual(set(plan["environment"]).intersection({"GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY"}), set())

        web = sandbox.cell_plan(
            tree={"real_path": str(tree), "real_exe": str(cli)},
            home=home, workspace=workspace, surface="web", task="", port=3210,
            profile="web", network="host", gpu=False,
        )
        self.assertEqual(web["network"], "host")
        apptainer_args = web["argv"][web["argv"].index("exec"):]
        self.assertNotIn("--net", apptainer_args)
        self.assertNotIn("--network", apptainer_args)
        self.assertEqual(web["argv"][-7:], ["/opt/dsh/dsh", "web", "--host", "127.0.0.1", "--port", "3210", "--no-open"])

        patched = sandbox.cell_plan(
            tree={"real_path": str(tree), "real_exe": str(cli)},
            home=home, workspace=workspace, surface="web", task="", port=3211,
            profile="web", network="host", gpu=False,
            patches=["/workspace/forge-assistant.cordis.yml"],
        )
        self.assertEqual(patched["argv"][-2:], ["--patch", "/workspace/forge-assistant.cordis.yml"])
        with self.assertRaisesRegex(SandboxError, "managed workspace"):
            sandbox.cell_plan(
                tree={"real_path": str(tree), "real_exe": str(cli)},
                home=home, workspace=workspace, surface="web", task="", port=3212,
                profile="web", network="host", gpu=False,
                patches=["/host/unsafe.yml"],
            )

    def test_slurm_is_an_honest_shared_resource_boundary(self):
        with mock.patch.dict("os.environ", {"SLURM_JOB_ID": "123"}, clear=False):
            sandbox = self.sandbox()
            status = sandbox.status()
            self.assertTrue(status["ready"])
            self.assertEqual(status["resource_limits"]["scope"], "shared-slurm")
            rendered = " ".join(self.runner.calls[-1][0])
            self.assertNotIn("--cpus", rendered)
            self.assertNotIn("--memory", rendered)
            self.assertNotIn("--pids-limit", rendered)

            tree = self.root / "foreign-in-shared-job"
            tree.mkdir()
            cli = tree / "dsh"
            cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            cli.chmod(0o755)
            with self.assertRaisesRegex(SandboxError, "require per-cell cgroup controls"):
                sandbox.test_tree({"real_path": str(tree), "real_exe": str(cli)})

    def test_gpu_is_fail_closed_without_a_scheduler_allocation(self):
        sandbox = self.sandbox()
        tree = self.root / "gpu-harness"
        tree.mkdir()
        cli = tree / "dsh"
        cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        cli.chmod(0o755)
        home = self.root / "gpu-home"
        workspace = self.root / "gpu-workspace"
        home.mkdir()
        workspace.mkdir()
        with mock.patch.dict("os.environ", {"CUDA_VISIBLE_DEVICES": "", "SLURM_JOB_GPUS": ""}, clear=False):
            with self.assertRaisesRegex(SandboxError, "scheduler GPU allocation"):
                sandbox.cell_plan(
                    tree={"real_path": str(tree), "real_exe": str(cli)}, home=home,
                    workspace=workspace, surface="headless", task="task", port=None,
                    profile="tui-min", network="none", gpu=True,
                )
        with mock.patch.dict(
            "os.environ",
            {"SLURM_JOB_ID": "123", "CUDA_VISIBLE_DEVICES": "0", "SLURM_JOB_GPUS": "0"},
            clear=False,
        ):
            plan = sandbox.cell_plan(
                tree={"real_path": str(tree), "real_exe": str(cli)}, home=home,
                workspace=workspace, surface="headless", task="task", port=None,
                profile="tui-min", network="none", gpu=True,
            )
        self.assertIn("--nv", plan["argv"])
        self.assertEqual(plan["gpu"], "allocated")


class CompleteCellIntegrationTests(SandboxFixture):
    def test_launcher_executes_a_complete_session_through_the_apptainer_command(self):
        tree = self.root / "deepseek-harness"
        tree.mkdir()
        (tree / "package.json").write_text(
            json.dumps({"name": "@deepseek-ai/deepseek-harness", "version": "cell-test"}),
            encoding="utf-8",
        )
        cli = tree / "dsh"
        cli.write_text(
            "#!/bin/sh\ntrap 'exit 0' TERM INT\necho complete-sandbox-session\nwhile true; do sleep 1; done\n",
            encoding="utf-8",
        )
        cli.chmod(0o755)
        fake_apptainer = self.root / "fake-apptainer"
        fake_apptainer.write_text(
            "#!/bin/sh\n"
            "source_root=''\n"
            f"image={str(self.image)!r}\n"
            "while [ \"$#\" -gt 0 ]; do\n"
            "  if [ \"$1\" = \"--mount\" ]; then\n"
            "    shift; mount=$1\n"
            "    case \"$mount\" in *dst=/opt/dsh,*) source_root=${mount#*src=}; source_root=${source_root%%,dst=*};; esac\n"
            "  elif [ \"$1\" = \"$image\" ]; then shift; break\n"
            "  fi\n"
            "  shift\n"
            "done\n"
            "payload=$1; shift\n"
            "case \"$payload\" in /opt/dsh/*) payload=$source_root/${payload#/opt/dsh/};; esac\n"
            "exec \"$payload\" \"$@\"\n",
            encoding="utf-8",
        )
        fake_apptainer.chmod(0o755)
        config = SandboxConfig.from_values(
            image=self.image, image_sha256=self.digest, binary=str(fake_apptainer),
            cpus="2", memory="1G", pids_limit=64, timeout_seconds=10,
            cell_timeout_seconds=600,
        )
        sandbox = ApptainerSandbox(config, self.root / "cell-sandbox", runner=self.runner)
        launcher = Launcher([tree], state_root=self.root / "launcher-state", sandbox=sandbox)
        try:
            # The managed test executor does not consistently expose child
            # /proc birth records. Keep the ownership invariant deterministic
            # while still executing the complete timeout -> Apptainer -> DSH chain.
            with mock.patch("dsh_forge.launcher._process_birth", return_value="sandbox-cell-birth"):
                tree_id = launcher.status()["trees"][0]["id"]
                cell = launcher.launch({
                    "tree_id": tree_id, "surface": "headless", "task": "full task",
                    "home_mode": "fresh", "workspace": "managed", "network": "none",
                    "resources": {"gpu": "none"},
                })
                for _ in range(30):
                    if launcher.logs(cell["id"]):
                        break
                    import time
                    time.sleep(0.02)
                self.assertIn("complete-sandbox-session", json.dumps(launcher.logs(cell["id"])))
                self.assertTrue(cell["sandboxed"])
                self.assertEqual(cell["execution_backend"], "apptainer-cell-v1")
                self.assertEqual(cell["network"], "none")
                self.assertEqual(cell["container_identity"]["image_sha256"], self.digest)
                self.assertEqual(launcher.stop(cell["id"])["state"], "stopped")
        finally:
            launcher.shutdown()


class FakeSandbox:
    ready = True

    def status(self):
        return {
            "mode": "apptainer-cell-v1",
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
    def test_unavailable_runner_never_falls_back_to_host_execution(self):
        class UnavailableSandbox:
            ready = False

            def status(self):
                return {"mode": "unavailable", "ready": False, "reason": "capability probe failed"}

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            tree = root / "local-harness"
            tree.mkdir()
            (tree / "package.json").write_text(
                '{"name":"@deepseek-ai/deepseek-harness","version":"test"}', encoding="utf-8"
            )
            cli = tree / "dsh"
            cli.write_text("#!/bin/sh\necho host execution must never happen\n", encoding="utf-8")
            cli.chmod(0o755)
            launcher = Launcher([tree], state_root=root / "state", sandbox=UnavailableSandbox())
            try:
                tree_id = launcher.status()["trees"][0]["id"]
                with mock.patch("dsh_forge.launcher.subprocess.Popen") as popen:
                    with self.assertRaisesRegex(LauncherError, "capability probe failed"):
                        launcher.launch({"tree_id": tree_id, "surface": "headless", "task": "task"})
                    popen.assert_not_called()
                self.assertEqual(launcher.status()["cells"], [])
            finally:
                launcher.shutdown()

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
                    with self.assertRaisesRegex(LauncherError, "not promoted for complete cell execution"):
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
