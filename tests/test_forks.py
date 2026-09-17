"""Tests for preparing a catalog fork as a launchable Harness tree.

The acquisition half must keep the plugin lane's guarantees; the build half must
never be taken silently. These hold it to both.
"""

from __future__ import annotations

import io
import hashlib
import tarfile
import tempfile
import unittest
from pathlib import Path

from dsh_forge.forks import (
    MAX_ENTRIES,
    ForkError,
    classify_tree,
    download_archive,
    extract_tree,
    prepare_fork,
)

COMMIT = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"
ROOT = "harness-" + COMMIT[:7]


def archive(entries, root=ROOT):
    """Build a tarball. entries: (name, payload, kind) with kind f|dir|sym|fifo."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as handle:
        for name, payload, kind in entries:
            info = tarfile.TarInfo(f"{root}/{name}" if root else name)
            if kind == "dir":
                info.type = tarfile.DIRTYPE
                handle.addfile(info)
            elif kind == "sym":
                info.type = tarfile.SYMTYPE
                info.linkname = payload
                handle.addfile(info)
            elif kind == "fifo":
                info.type = tarfile.FIFOTYPE
                handle.addfile(info)
            else:
                info.size = len(payload)
                handle.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


class _Expands(unittest.TestCase):
    """Shared extraction helper that cleans up even when extraction raises."""

    def expand(self, blob):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        source = Path(directory.name) / "a.tar.gz"
        source.write_bytes(blob)
        tree = Path(directory.name) / "tree"
        layout = extract_tree(source, tree)
        return layout, classify_tree(tree), tree


PREBUILT = [("package.json", b'{"name":"deepseek-harness"}', "f"),
            ("apps/cli/lib/bin.js", b"#!/usr/bin/env node\n", "f")]
SOURCE_ONLY = [("package.json", b'{"name":"deepseek-harness"}', "f"),
               ("apps/cli/src/bin.ts", b"export {}\n", "f")]


class ExtractionTests(_Expands):
    def test_the_single_root_directory_is_stripped(self):
        layout, _, tree = self.expand(archive(PREBUILT))
        self.assertEqual(layout["root"], ROOT)
        self.assertTrue((tree / "apps/cli/lib/bin.js").is_file())
        self.assertFalse((tree / ROOT).exists())

    def test_a_traversal_path_is_refused(self):
        for name in ("../../etc/passwd", "a/../../b", "..", "a/../../../x"):
            with self.assertRaises(ForkError) as caught:
                self.expand(archive([(name, b"x", "f")]))
            self.assertEqual(caught.exception.code, "unsafe_archive")

    def test_an_absolute_path_is_refused(self):
        with self.assertRaises(ForkError) as caught:
            self.expand(archive([("a", b"x", "f")], root="/abs"))
        self.assertEqual(caught.exception.code, "unsafe_archive")

    def test_a_symlink_is_refused_rather_than_skipped(self):
        # Skipping would leave a tree that looks complete but is not.
        with self.assertRaises(ForkError) as caught:
            self.expand(archive([("link", "/etc/passwd", "sym")]))
        self.assertEqual(caught.exception.code, "unsafe_archive")

    def test_a_device_or_fifo_member_is_refused(self):
        with self.assertRaises(ForkError) as caught:
            self.expand(archive([("pipe", b"", "fifo")]))
        self.assertEqual(caught.exception.code, "unsafe_archive")

    def test_a_backslash_or_control_character_is_refused(self):
        for name in ("a\\b", "a\x01b"):
            with self.assertRaises(ForkError) as caught:
                self.expand(archive([(name, b"x", "f")]))
            self.assertEqual(caught.exception.code, "unsafe_archive")

    def test_more_than_one_root_is_refused(self):
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as handle:
            for name in ("one/f", "two/f"):
                info = tarfile.TarInfo(name)
                info.size = 1
                handle.addfile(info, io.BytesIO(b"x"))
        with self.assertRaises(ForkError) as caught:
            self.expand(buffer.getvalue())
        self.assertEqual(caught.exception.code, "unsafe_archive")

    def test_an_oversized_expansion_is_refused_before_writing(self):
        from dsh_forge import forks
        original = forks.MAX_EXPANDED_BYTES
        forks.MAX_EXPANDED_BYTES = 16
        try:
            with self.assertRaises(ForkError) as caught:
                self.expand(archive([("big", b"x" * 64, "f")]))
            self.assertEqual(caught.exception.code, "artifact_too_large")
        finally:
            forks.MAX_EXPANDED_BYTES = original

    def test_the_entry_ceiling_is_bounded(self):
        self.assertLessEqual(MAX_ENTRIES, 1_000_000)


class ClassificationTests(_Expands):
    def test_a_prebuilt_fork_launches_without_running_scripts(self):
        _, verdict, _ = self.expand(archive(PREBUILT))
        self.assertTrue(verdict["launchable"])
        self.assertFalse(verdict["build_required"])
        self.assertEqual(verdict["entrypoint"], "apps/cli/lib/bin.js")
        self.assertIn("without running any scripts", verdict["reason"])

    def test_a_source_only_fork_reports_that_a_build_runs_its_scripts(self):
        _, verdict, _ = self.expand(archive(SOURCE_ONLY))
        self.assertFalse(verdict["launchable"])
        self.assertTrue(verdict["build_required"])
        # The reader has to be told what a build would actually do.
        self.assertIn("scripts", verdict["reason"])

    def test_a_repository_that_is_not_a_harness_says_so(self):
        _, verdict, _ = self.expand(archive([("README.md", b"hi", "f")]))
        self.assertFalse(verdict["launchable"])
        self.assertFalse(verdict["build_required"])
        self.assertIn("cannot launch", verdict["reason"])


class PrepareTests(unittest.TestCase):
    def record(self, **overrides):
        value = {
            "artifact_id": "github:1",
            "artifact_type": "fork",
            "full_name": "Owner/harness",
            "repository_url": "https://github.com/Owner/harness",
            "head_sha": COMMIT,
        }
        value.update(overrides)
        return value

    def opener(self, blob):
        def open_https(source, allowed_hosts, timeout):
            self.requested = source["url"]
            self.allowed = allowed_hosts
            return io.BytesIO(blob), source["url"], []
        return open_https

    def test_prepare_pins_the_commit_and_records_the_digest(self):
        blob = archive(PREBUILT)
        with tempfile.TemporaryDirectory() as tmp:
            result = prepare_fork(self.record(), Path(tmp) / "tree", opener=self.opener(blob))
            self.assertTrue(result["launchable"])
            self.assertEqual(result["commit"], COMMIT)
            self.assertEqual(result["pin"]["integrity"], "sha256-" + hashlib.sha256(blob).hexdigest())
            self.assertTrue(self.requested.endswith(COMMIT))
            self.assertIn("codeload.github.com", self.allowed)

    def test_prepare_never_claims_the_code_ran_or_was_reviewed(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = prepare_fork(self.record(), Path(tmp) / "tree", opener=self.opener(archive(PREBUILT)))
            self.assertEqual(result["claims"], {
                "executed": False, "scripts_run": False, "curator_reviewed": False,
                "security_verified": False, "commit_pinned": True,
            })

    def test_a_changed_archive_at_a_pinned_commit_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = prepare_fork(self.record(), Path(tmp) / "tree", opener=self.opener(archive(PREBUILT)))
            with self.assertRaises(ForkError) as caught:
                prepare_fork(
                    self.record(), Path(tmp) / "tree",
                    known_pin=first["pin"],
                    opener=self.opener(archive(SOURCE_ONLY)),
                )
            self.assertEqual(caught.exception.code, "integrity_mismatch")

    def test_an_unpinned_commit_is_refused_before_any_request(self):
        opener = self.opener(archive(PREBUILT))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ForkError) as caught:
                prepare_fork(self.record(head_sha="main"), Path(tmp) / "tree", opener=opener)
            self.assertEqual(caught.exception.code, "commit_not_pinned")
        self.assertFalse(hasattr(self, "requested"), "no request may be made for an unpinned record")

    def test_a_non_github_record_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ForkError) as caught:
                prepare_fork(
                    self.record(repository_url="https://evil.example/Owner/harness"),
                    Path(tmp) / "tree", opener=self.opener(archive(PREBUILT)),
                )
            self.assertEqual(caught.exception.code, "source_not_allowed")

    def test_preparing_twice_replaces_the_tree_rather_than_merging(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "tree"
            prepare_fork(self.record(), target, opener=self.opener(archive(SOURCE_ONLY)))
            self.assertTrue((target / "apps/cli/src/bin.ts").is_file())
            prepare_fork(self.record(), target, opener=self.opener(archive(PREBUILT)))
            self.assertTrue((target / "apps/cli/lib/bin.js").is_file())
            self.assertFalse((target / "apps/cli/src/bin.ts").exists(),
                             "a stale file from the previous tree must not survive")

    def test_an_empty_archive_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ForkError) as caught:
                prepare_fork(self.record(), Path(tmp) / "tree", opener=self.opener(b""))
            self.assertEqual(caught.exception.code, "response_rejected")


class DownloadTests(unittest.TestCase):
    def test_an_oversized_download_is_refused(self):
        from dsh_forge import forks
        original = forks.MAX_ARCHIVE_BYTES
        forks.MAX_ARCHIVE_BYTES = 8
        try:
            with tempfile.TemporaryDirectory() as tmp:
                def open_https(source, hosts, timeout):
                    return io.BytesIO(b"x" * 64), source["url"], []
                with self.assertRaises(ForkError) as caught:
                    download_archive("https://codeload.github.com/o/r/tar.gz/" + COMMIT,
                                     Path(tmp) / "a.tar.gz", opener=open_https)
                self.assertEqual(caught.exception.code, "artifact_too_large")
        finally:
            forks.MAX_ARCHIVE_BYTES = original


if __name__ == "__main__":
    unittest.main()
