import base64
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

from dsh_forge import cli
from dsh_forge.acquisition import (
    AcquisitionError,
    RECEIPT_SCHEMA,
    _RedirectPolicy,
    _stream_artifact,
    acquire,
)
from dsh_forge.packages import PackageError, compose, create_trust_root, sign
from tests.test_packages import package_spec


class FakeResponse(io.BytesIO):
    def __init__(self, payload, url, *, content_length=True, content_encoding=None):
        super().__init__(payload)
        self.status = 200
        self._url = url
        self.headers = {}
        if content_length:
            self.headers["Content-Length"] = str(len(payload))
        if content_encoding is not None:
            self.headers["Content-Encoding"] = content_encoding

    def geturl(self):
        return self._url


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.private = self.root / "private.pem"
        self.public = self.root / "public.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "Ed25519", "-out", self.private],
            check=True,
            capture_output=True,
        )
        self.private.chmod(0o600)
        subprocess.run(
            ["openssl", "pkey", "-in", self.private, "-pubout", "-out", self.public],
            check=True,
            capture_output=True,
        )
        self.payloads = {
            "dsh-vet": b"first exact tarball bytes",
            "dsh-code-index": b"second exact tarball bytes",
        }
        spec = package_spec()
        for plugin in spec["plugins"]:
            payload = self.payloads[plugin["id"]]
            plugin["source"]["integrity"] = "sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode("ascii")
        self.manifest = compose(spec)
        self.envelope = sign(self.manifest, self.private)
        self.trust_root = create_trust_root(self.public, "test.release", "2099-01-01T00:00:00Z")
        self.quarantine = self.root / "quarantine"

    def tearDown(self):
        self.temp.cleanup()

    def downloader(self, plugin, handle):
        payload = self.payloads[plugin["id"]]
        handle.write(payload)
        digest = hashlib.sha256(payload).hexdigest()
        return {
            "bytes": len(payload),
            "content_sha256": "sha256:" + digest,
            "original_url": plugin["source"]["url"],
            "final_url": plugin["source"]["url"],
            "redirect_chain": [],
        }

    def test_verified_artifacts_are_content_addressed_read_only_and_reusable(self):
        first = acquire(
            self.envelope,
            self.trust_root,
            self.quarantine,
            downloader=self.downloader,
        )

        self.assertEqual(first["schema"], RECEIPT_SCHEMA)
        self.assertFalse(first["credentials_forwarded"])
        self.assertFalse(first["archives_extracted"])
        self.assertFalse(first["installation_authorized"])
        self.assertFalse(first["execution_authorized"])
        self.assertEqual(len(first["artifacts"]), 2)
        self.assertTrue(Path(first["receipt"]).is_file())
        self.assertEqual(stat.S_IMODE(Path(first["receipt"]).stat().st_mode), 0o400)

        for artifact in first["artifacts"]:
            path = self.quarantine / artifact["object"]
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_bytes(), self.payloads[artifact["plugin_id"]])
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o400)
            self.assertFalse(artifact["reused"])

        second = acquire(
            self.envelope,
            self.trust_root,
            self.quarantine,
            downloader=self.downloader,
        )
        self.assertTrue(all(artifact["reused"] for artifact in second["artifacts"]))

    def test_signature_failure_precedes_network_and_quarantine_side_effects(self):
        tampered = copy.deepcopy(self.envelope)
        payload = bytearray(base64.b64decode(tampered["payload"]))
        payload[-1] ^= 1
        tampered["payload"] = base64.b64encode(payload).decode("ascii")
        called = False

        def forbidden_downloader(_plugin, _handle):
            nonlocal called
            called = True
            raise AssertionError("network seam must not be reached")

        with self.assertRaises(PackageError):
            acquire(tampered, self.trust_root, self.quarantine, downloader=forbidden_downloader)
        self.assertFalse(called)
        self.assertFalse(self.quarantine.exists())

    def test_unapproved_hosts_and_signed_url_queries_fail_before_download(self):
        for url in (
            "https://example.invalid/dsh-vet-0.3.0.tgz",
            "https://registry.npmjs.org/dsh-vet/-/dsh-vet-0.3.0.tgz?token=secret",
            "https://registry.npmjs.org:444/dsh-vet/-/dsh-vet-0.3.0.tgz",
        ):
            spec = package_spec()
            spec["plugins"][0]["source"]["url"] = url
            manifest = compose(spec)
            envelope = sign(manifest, self.private)
            with self.assertRaisesRegex(AcquisitionError, "approved source host"):
                acquire(envelope, self.trust_root, self.quarantine, downloader=self.downloader)

    def test_invalid_downloader_result_is_removed_without_a_receipt(self):
        def lying_downloader(plugin, handle):
            payload = self.payloads[plugin["id"]]
            handle.write(payload)
            return {
                "bytes": len(payload),
                "content_sha256": "sha256:" + "0" * 64,
                "original_url": plugin["source"]["url"],
                "final_url": plugin["source"]["url"],
                "redirect_chain": [],
            }

        with self.assertRaisesRegex(AcquisitionError, "staged bytes"):
            acquire(self.envelope, self.trust_root, self.quarantine, downloader=lying_downloader)
        self.assertEqual(list((self.quarantine / ".incoming").iterdir()), [])
        self.assertEqual(list((self.quarantine / "receipts" / "sha256").iterdir()), [])

    def test_self_consistent_download_metadata_cannot_bypass_signed_integrity(self):
        def wrong_bytes_downloader(plugin, handle):
            payload = b"different bytes with a matching self-reported digest"
            handle.write(payload)
            return {
                "bytes": len(payload),
                "content_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "original_url": plugin["source"]["url"],
                "final_url": plugin["source"]["url"],
                "redirect_chain": [],
            }

        with self.assertRaisesRegex(AcquisitionError, "signed artifact integrity"):
            acquire(self.envelope, self.trust_root, self.quarantine, downloader=wrong_bytes_downloader)
        self.assertEqual(list((self.quarantine / ".incoming").iterdir()), [])
        self.assertEqual(list((self.quarantine / "receipts" / "sha256").iterdir()), [])

    def test_per_package_byte_budget_is_fail_closed(self):
        total = sum(len(payload) for payload in self.payloads.values())
        with self.assertRaisesRegex(AcquisitionError, "total byte limit"):
            acquire(
                self.envelope,
                self.trust_root,
                self.quarantine,
                max_total_bytes=total - 1,
                downloader=self.downloader,
            )
        self.assertEqual(list((self.quarantine / "receipts" / "sha256").iterdir()), [])

    def test_corrupt_existing_content_address_fails_closed(self):
        first = acquire(self.envelope, self.trust_root, self.quarantine, downloader=self.downloader)
        path = self.quarantine / first["artifacts"][0]["object"]
        path.chmod(0o600)
        path.write_bytes(b"x" * path.stat().st_size)
        with self.assertRaisesRegex(AcquisitionError, "failed its content address"):
            acquire(self.envelope, self.trust_root, self.quarantine, downloader=self.downloader)

    def test_stream_checks_signed_integrity_and_transfer_bounds(self):
        plugin = self.manifest["plugins"][0]
        payload = self.payloads[plugin["id"]]
        response = FakeResponse(payload, plugin["source"]["url"])
        with mock.patch("dsh_forge.acquisition._open_https", return_value=(response, plugin["source"]["url"], [])):
            result = _stream_artifact(plugin, io.BytesIO(), max_bytes=1024, timeout=5)
        self.assertEqual(result["bytes"], len(payload))

        response = FakeResponse(payload + b"tampered", plugin["source"]["url"])
        with mock.patch("dsh_forge.acquisition._open_https", return_value=(response, plugin["source"]["url"], [])):
            with self.assertRaisesRegex(AcquisitionError, "Integrity mismatch"):
                _stream_artifact(plugin, io.BytesIO(), max_bytes=1024, timeout=5)

        response = FakeResponse(payload, plugin["source"]["url"])
        with mock.patch("dsh_forge.acquisition._open_https", return_value=(response, plugin["source"]["url"], [])):
            with self.assertRaisesRegex(AcquisitionError, "byte limit"):
                _stream_artifact(plugin, io.BytesIO(), max_bytes=4, timeout=5)

    def test_redirects_are_bounded_to_approved_https_hosts_and_redacted(self):
        policy = _RedirectPolicy(frozenset({"github.com", "codeload.github.com"}))
        request = mock.Mock(full_url="https://github.com/example/repo/archive/" + "a" * 40 + ".tar.gz")
        redirected = policy.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "https://codeload.github.com/example/repo/tar.gz/" + "a" * 40 + "?temporary=secret",
        )
        self.assertNotIn("temporary", policy.chain[0])
        self.assertIn("temporary=secret", redirected.full_url)
        with self.assertRaisesRegex(AcquisitionError, "approved source host"):
            policy.redirect_request(request, None, 302, "Found", {}, "https://evil.example/payload")

    def test_cli_dispatches_acquisition_without_constructing_launcher(self):
        bundle = self.root / "bundle.json"
        root = self.root / "root.json"
        bundle.write_text(json.dumps(self.envelope), encoding="utf-8")
        root.write_text(json.dumps(self.trust_root), encoding="utf-8")
        captured = {}

        def fake_acquirer(envelope, trust_root, quarantine, **options):
            captured.update({"envelope": envelope, "trust_root": trust_root, "quarantine": quarantine, **options})
            return {
                "schema": RECEIPT_SCHEMA,
                "installation_authorized": False,
                "execution_authorized": False,
            }

        def forbidden_launcher(**_options):
            raise AssertionError("package acquisition must not construct the launcher")

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cli.run(
                [
                    "--json",
                    "packages",
                    "acquire",
                    "--bundle",
                    str(bundle),
                    "--trust-root",
                    str(root),
                    "--quarantine",
                    str(self.quarantine),
                    "--max-artifact-bytes",
                    "4096",
                    "--timeout",
                    "10",
                    "--max-total-bytes",
                    "8192",
                    "--total-timeout",
                    "20",
                ],
                launcher_factory=forbidden_launcher,
                acquirer=fake_acquirer,
            )
        output = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertFalse(output["data"]["installation_authorized"])
        self.assertFalse(output["data"]["execution_authorized"])
        self.assertEqual(captured["max_artifact_bytes"], 4096)
        self.assertEqual(captured["max_total_bytes"], 8192)
        self.assertEqual(captured["timeout_seconds"], 10.0)
        self.assertEqual(captured["total_timeout_seconds"], 20.0)


if __name__ == "__main__":
    unittest.main()
