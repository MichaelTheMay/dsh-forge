import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from gems.fetch import FetchError, fetch_commit


def git(cwd, *arguments):
    environment = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(cwd),
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    }
    return subprocess.run(
        ["git", *arguments], cwd=cwd, env=environment, check=True, capture_output=True, text=True,
    ).stdout.strip()


class FetchCommitTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.remote = Path(self.root.name) / "remote"
        self.remote.mkdir()
        git(self.remote, "init", "--quiet", "-b", "main")
        (self.remote / "index.js").write_text("export default 1\n", encoding="utf-8")
        git(self.remote, "add", "index.js")
        git(self.remote, "commit", "--quiet", "-m", "first")
        self.first = git(self.remote, "rev-parse", "HEAD")
        (self.remote / "index.js").write_text("export default 2\n", encoding="utf-8")
        git(self.remote, "commit", "--quiet", "-am", "second")

    def test_writes_the_files_of_the_exact_commit_and_no_git_metadata(self):
        target = fetch_commit("owner/repo", self.first, Path(self.root.name) / "out", remote=str(self.remote))
        self.assertEqual((target / "index.js").read_text(encoding="utf-8"), "export default 1\n")
        self.assertFalse((target / ".git").exists())

    def test_rejects_bad_names_commits_and_used_destinations(self):
        out = Path(self.root.name) / "out"
        with self.assertRaisesRegex(FetchError, "owner/name"):
            fetch_commit("../escape", self.first, out, remote=str(self.remote))
        with self.assertRaisesRegex(FetchError, "commit id"):
            fetch_commit("owner/repo", "main", out, remote=str(self.remote))
        out.mkdir()
        (out / "existing").write_text("x", encoding="utf-8")
        with self.assertRaisesRegex(FetchError, "not empty"):
            fetch_commit("owner/repo", self.first, out, remote=str(self.remote))

    def test_a_missing_commit_fails_and_leaves_nothing_behind(self):
        out = Path(self.root.name) / "out"
        with self.assertRaises(FetchError):
            fetch_commit("owner/repo", "0" * 40, out, remote=str(self.remote))
        self.assertFalse(out.exists())

    def test_enforces_the_size_limit(self):
        out = Path(self.root.name) / "out"
        with self.assertRaisesRegex(FetchError, "larger than"):
            fetch_commit("owner/repo", self.first, out, remote=str(self.remote), max_bytes=5)
        self.assertFalse(out.exists())

    def test_git_runs_without_the_users_configuration_or_credentials(self):
        from gems import fetch

        environment = fetch._git_environment()
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(environment["GIT_TERMINAL_PROMPT"], "0")
        self.assertNotIn("GITHUB_TOKEN", environment)
        self.assertNotIn("GH_TOKEN", environment)
        self.assertNotEqual(environment["HOME"], os.path.expanduser("~"))


if __name__ == "__main__":
    unittest.main()
