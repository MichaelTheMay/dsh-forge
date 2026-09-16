"""Tests for the community install lane.

The lane's whole claim is that it adds no new way through the trust boundary: it
builds a manifest and signs it locally, then the existing signed pipeline does
the rest. These tests hold it to that.
"""

from __future__ import annotations

import io
import hashlib
import tempfile
import unittest

from dsh_forge.community import (
    LANE,
    CommunityError,
    archive_url,
    community_spec,
    local_identity,
    prepare_install,
    probe_archive,
)
from dsh_forge.packages import PackageError, compose, verify

PAYLOAD = b"fake-source-archive" * 64
COMMIT = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"


def record(**overrides):
    value = {
        "artifact_id": "github:1",
        "full_name": "Owner/dsh-memory",
        "name": "dsh-memory",
        "repository_url": "https://github.com/Owner/dsh-memory",
        "head_sha": COMMIT,
        "description": "Persistent memory for the harness.",
        "license": {"spdx": "MIT"},
    }
    value.update(overrides)
    return value


class _Response:
    def __init__(self, payload=PAYLOAD):
        self._buffer = io.BytesIO(payload)
        self.closed = False

    def read(self, size):
        return self._buffer.read(size)

    def close(self):
        self.closed = True


def opener(payload=PAYLOAD):
    captured = {}

    def open_https(source, allowed_hosts, timeout):
        captured["url"] = source["url"]
        captured["hosts"] = allowed_hosts
        captured["response"] = _Response(payload)
        return captured["response"], source["url"], []

    open_https.captured = captured
    return open_https


def probe_with(open_https):
    return lambda url: probe_archive(url, opener=open_https)


class ArchiveUrlTests(unittest.TestCase):
    def test_url_pins_the_commit(self):
        url = archive_url("https://github.com/Owner/repo", COMMIT)
        self.assertEqual(url, f"https://codeload.github.com/Owner/repo/tar.gz/{COMMIT}")

    def test_an_unpinned_commit_is_refused(self):
        for bad in ("", "main", "a" * 39, "A" * 40, "g" * 40):
            with self.assertRaises(CommunityError) as caught:
                archive_url("https://github.com/Owner/repo", bad)
            self.assertEqual(caught.exception.code, "commit_not_pinned")

    def test_only_github_repositories_are_accepted(self):
        for bad in ("https://evil.example/Owner/repo", "http://github.com/Owner/repo",
                    "https://github.com.evil.example/Owner/repo", "https://github.com/Owner"):
            with self.assertRaises(CommunityError) as caught:
                archive_url(bad, COMMIT)
            self.assertEqual(caught.exception.code, "source_not_allowed")


class ProbeTests(unittest.TestCase):
    def test_probe_reports_the_digest_of_what_it_received(self):
        pin = probe_archive("https://codeload.github.com/o/r/tar.gz/" + COMMIT, opener=opener())
        self.assertEqual(pin["integrity"], "sha256-" + hashlib.sha256(PAYLOAD).hexdigest())
        self.assertEqual(pin["bytes"], len(PAYLOAD))

    def test_probe_is_restricted_to_the_github_archive_hosts(self):
        open_https = opener()
        probe_archive("https://codeload.github.com/o/r/tar.gz/" + COMMIT, opener=open_https)
        self.assertIn("codeload.github.com", open_https.captured["hosts"])
        self.assertNotIn("evil.example", open_https.captured["hosts"])

    def test_an_oversized_archive_is_refused(self):
        with self.assertRaises(CommunityError) as caught:
            probe_archive("https://codeload.github.com/o/r/tar.gz/" + COMMIT,
                          max_bytes=16, opener=opener())
        self.assertEqual(caught.exception.code, "artifact_too_large")

    def test_an_empty_archive_is_refused(self):
        with self.assertRaises(CommunityError) as caught:
            probe_archive("https://codeload.github.com/o/r/tar.gz/" + COMMIT, opener=opener(b""))
        self.assertEqual(caught.exception.code, "response_rejected")

    def test_the_response_is_always_closed(self):
        open_https = opener()
        probe_archive("https://codeload.github.com/o/r/tar.gz/" + COMMIT, opener=open_https)
        self.assertTrue(open_https.captured["response"].closed)


class SpecTests(unittest.TestCase):
    pin = {"integrity": "sha256-" + "0" * 64}

    def test_the_spec_composes_into_a_valid_manifest(self):
        manifest = compose(community_spec(record(), self.pin))
        self.assertEqual(manifest["plugins"][0]["repository"]["commit"], COMMIT)
        self.assertEqual(manifest["plugins"][0]["source"]["kind"], "github_archive")

    def test_the_lane_grants_no_permissions(self):
        manifest = compose(community_spec(record(), self.pin))
        self.assertEqual(manifest["plugins"][0]["permissions"], [])

    def test_a_record_cannot_smuggle_permissions_in(self):
        # Nothing from the catalog record reaches the permission list.
        manifest = compose(community_spec(
            record(permissions=["filesystem:write", "network:outbound"]), self.pin))
        self.assertEqual(manifest["plugins"][0]["permissions"], [])

    def test_an_unreported_license_becomes_noassertion(self):
        for value in (None, {"spdx": "NOASSERTION"}, {"spdx": ""}):
            manifest = compose(community_spec(record(license=value), self.pin))
            self.assertEqual(manifest["package"]["license"], "NOASSERTION")

    def test_provenance_records_the_lane_and_claims_nothing_executed(self):
        manifest = compose(community_spec(record(), self.pin))
        self.assertIn(LANE, manifest["provenance"]["created_by"])
        self.assertEqual(manifest["provenance"]["evidence"], "metadata_only_unexecuted")

    def test_a_hostile_name_cannot_escape_the_identifier(self):
        manifest = compose(community_spec(record(name="../../etc/passwd"), self.pin))
        self.assertNotIn("/", manifest["plugins"][0]["id"])
        self.assertNotIn("..", manifest["plugins"][0]["id"])

    def test_an_invalid_digest_is_rejected_by_the_schema(self):
        with self.assertRaises(PackageError):
            compose(community_spec(record(), {"integrity": "sha256-not-hex"}))


class PrepareInstallTests(unittest.TestCase):
    def test_the_existing_verifier_accepts_the_locally_signed_envelope(self):
        with tempfile.TemporaryDirectory() as root:
            result = prepare_install(record(), identity_root=root, probe=probe_with(opener()))
            verified = verify(result["envelope"], result["trust_root"])
            manifest = verified["manifest"]
            self.assertEqual(len(verified["valid_signers"]), 1)
            self.assertEqual(manifest["plugins"][0]["repository"]["commit"], COMMIT)
            self.assertTrue(manifest["plugins"][0]["source"]["url"].endswith(COMMIT))

    def test_the_digest_pins_what_was_actually_downloaded(self):
        with tempfile.TemporaryDirectory() as root:
            result = prepare_install(record(), identity_root=root, probe=probe_with(opener()))
            self.assertEqual(result["pin"]["integrity"], "sha256-" + hashlib.sha256(PAYLOAD).hexdigest())

    def test_a_changed_artifact_at_a_pinned_commit_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            first = prepare_install(record(), identity_root=root, probe=probe_with(opener()))
            # Same commit, different bytes: this must not install.
            with self.assertRaises(CommunityError) as caught:
                prepare_install(record(), identity_root=root, known_pin=first["pin"],
                                probe=probe_with(opener(b"different-bytes")))
            self.assertEqual(caught.exception.code, "integrity_mismatch")

    def test_an_unchanged_artifact_matches_its_recorded_pin(self):
        with tempfile.TemporaryDirectory() as root:
            first = prepare_install(record(), identity_root=root, probe=probe_with(opener()))
            again = prepare_install(record(), identity_root=root, known_pin=first["pin"],
                                    probe=probe_with(opener()))
            self.assertEqual(again["pin"]["integrity"], first["pin"]["integrity"])

    def test_nothing_is_downloaded_for_a_record_without_a_pinned_commit(self):
        open_https = opener()
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(CommunityError) as caught:
                prepare_install(record(head_sha="main"), identity_root=root, probe=probe_with(open_https))
            self.assertEqual(caught.exception.code, "commit_not_pinned")
        self.assertNotIn("url", open_https.captured, "the probe must not run for an unpinned record")

    def test_the_lane_never_claims_review_or_verification(self):
        with tempfile.TemporaryDirectory() as root:
            result = prepare_install(record(), identity_root=root, probe=probe_with(opener()))
            self.assertEqual(result["lane"], LANE)
            self.assertIs(result["claims"]["curator_reviewed"], False)
            self.assertIs(result["claims"]["security_verified"], False)
            self.assertIs(result["claims"]["sandboxed"], True)
            self.assertEqual(result["claims"]["signed_by"], "local-operator")

    def test_a_curator_trust_root_does_not_accept_a_community_envelope(self):
        # The local key is its own trust root; it must not validate against another.
        with tempfile.TemporaryDirectory() as first_root, tempfile.TemporaryDirectory() as second_root:
            mine = prepare_install(record(), identity_root=first_root, probe=probe_with(opener()))
            other = local_identity(second_root)
            with self.assertRaises(PackageError):
                verify(mine["envelope"], other["trust_root"])


class LocalIdentityTests(unittest.TestCase):
    def test_the_key_is_stable_across_calls(self):
        with tempfile.TemporaryDirectory() as root:
            first = local_identity(root)
            second = local_identity(root)
            self.assertEqual(first["trust_root"]["keys"][0]["keyid"], second["trust_root"]["keys"][0]["keyid"])

    def test_the_private_key_is_not_group_or_world_readable(self):
        import os
        import stat as stat_module
        with tempfile.TemporaryDirectory() as root:
            identity = local_identity(root)
            mode = stat_module.S_IMODE(os.stat(identity["private_key"]).st_mode)
            self.assertEqual(mode & 0o077, 0)

    def test_the_trust_root_is_marked_local(self):
        with tempfile.TemporaryDirectory() as root:
            identity = local_identity(root)
            self.assertEqual(identity["trust_root"]["root_id"], "dsh-forge-community-local")
            self.assertEqual(identity["lane"], LANE)


if __name__ == "__main__":
    unittest.main()
