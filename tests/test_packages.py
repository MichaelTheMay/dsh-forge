import base64
import contextlib
import copy
import datetime as dt
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from dsh_forge import cli
from dsh_forge.packages import (
    PACKAGE_SCHEMA,
    PAYLOAD_TYPE,
    SPEC_SCHEMA,
    PackageError,
    canonical_bytes,
    compose,
    create_trust_root,
    read_json,
    sign,
    verify,
)


def package_spec():
    return {
        "schema": SPEC_SCHEMA,
        "package": {
            "id": "example.review-stack",
            "name": "Review stack",
            "version": "1.0.0",
            "description": "Two pinned metadata records for deterministic composition tests.",
            "license": "MIT",
            "created_at": "2026-09-05T20:00:00Z",
        },
        "compatibility": {
            "dsh": ">=0.1.2-alpha.3 <0.2.0",
            "node": ">=22.19.0 <23",
            "platforms": ["linux-x64", "linux-arm64"],
        },
        "plugins": [
            {
                "id": "dsh-vet",
                "source": {
                    "kind": "npm",
                    "name": "dsh-vet",
                    "version": "0.3.0",
                    "url": "https://registry.npmjs.org/dsh-vet/-/dsh-vet-0.3.0.tgz",
                    "integrity": "sha512-HdQoj+ZxoYJRp3/PUK7fIIc/bj6FhyF86SDxyKapRQB1X23GY9hPM7PNoarzAvSa7k4isv6nrnXR8S7IqfQ0Ig==",
                },
                "repository": {
                    "url": "https://github.com/rogerdigital/dsh-vet",
                    "commit": "3005968cc708d12b7e1f98f1a312239b5312ce7f",
                },
                "permissions": ["process:spawn", "filesystem:read", "environment:read"],
                "requires": [],
                "conflicts_with": [],
            },
            {
                "id": "dsh-code-index",
                "source": {
                    "kind": "npm",
                    "name": "dsh-code-index",
                    "version": "0.3.1",
                    "url": "https://registry.npmjs.org/dsh-code-index/-/dsh-code-index-0.3.1.tgz",
                    "integrity": "sha512-rTCRRKrw/qJa7BQSE/CRV+I95KQnlgv35CDg1QHHu9cFEO6xH5ugLL4NDdcKoZH4x8fPxrITVIsXbe8rgUpWxg==",
                },
                "repository": {
                    "url": "https://github.com/lemonxiny55/dsh-code-index",
                    "commit": "de81accbc5104fa2a872d692de7205b59d1e6130",
                },
                "permissions": ["filesystem:read"],
                "requires": [],
                "conflicts_with": [],
            },
        ],
        "load_order": ["dsh-vet", "dsh-code-index"],
        "provenance": {
            "created_by": "DSH Forge test fixture",
            "source": "user_composed",
            "evidence": "metadata_only_unexecuted",
        },
    }


class SignedPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.private = self.root / "private.pem"
        self.public = self.root / "public.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", self.private], check=True, capture_output=True)
        self.private.chmod(0o600)
        subprocess.run(
            ["openssl", "pkey", "-in", self.private, "-pubout", "-out", self.public],
            check=True,
            capture_output=True,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_composition_is_deterministic_and_records_exact_pins(self):
        first = compose(package_spec())
        reordered = package_spec()
        reordered["plugins"].reverse()
        reordered["compatibility"]["platforms"].reverse()
        second = compose(reordered)

        self.assertEqual(first, second)
        self.assertEqual(first["schema"], PACKAGE_SCHEMA)
        self.assertRegex(first["composition_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual([plugin["id"] for plugin in first["plugins"]], ["dsh-code-index", "dsh-vet"])
        self.assertEqual(first["plugins"][0]["source"]["version"], "0.3.1")
        self.assertNotIn(b"latest", canonical_bytes(first))

    def test_documented_example_has_a_stable_composition_digest(self):
        source = Path(__file__).resolve().parents[1] / "examples/package-spec.v1.json"
        manifest = compose(json.loads(source.read_text(encoding="utf-8")))
        self.assertEqual(
            manifest["composition_digest"],
            "sha256:ad9ab93d80ad3e6a693dbca528fb0115fdc4581d768fa2df292475191d7bc40c",
        )

    def test_composer_rejects_ambiguous_or_incompatible_selections(self):
        ranged = package_spec()
        ranged["plugins"][0]["source"]["version"] = "^0.3.0"
        with self.assertRaisesRegex(PackageError, "exact version"):
            compose(ranged)

        missing = package_spec()
        missing["plugins"][0]["requires"] = ["not-selected"]
        with self.assertRaisesRegex(PackageError, "requires missing"):
            compose(missing)

        conflict = package_spec()
        conflict["plugins"][0]["conflicts_with"] = ["dsh-code-index"]
        with self.assertRaisesRegex(PackageError, "conflicts with"):
            compose(conflict)

        permission = package_spec()
        permission["plugins"][0]["permissions"] = ["host:root"]
        with self.assertRaisesRegex(PackageError, "unsupported"):
            compose(permission)

    def test_ed25519_dsse_round_trip_and_tamper_rejection(self):
        manifest = compose(package_spec())
        envelope = sign(manifest, self.private)
        root = create_trust_root(self.public, "example.release", "2099-01-01T00:00:00Z")
        result = verify(envelope, root, now=dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc))

        self.assertEqual(envelope["payloadType"], PAYLOAD_TYPE)
        self.assertEqual(result["manifest"], manifest)
        self.assertEqual(result["valid_signers"], [envelope["signatures"][0]["keyid"]])
        self.assertEqual(result["threshold"], 1)

        tampered = copy.deepcopy(envelope)
        payload = bytearray(base64.b64decode(tampered["payload"]))
        payload[-2] ^= 1
        tampered["payload"] = base64.b64encode(payload).decode("ascii")
        with self.assertRaises(PackageError):
            verify(tampered, root, now=dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc))

    def test_expired_roots_and_insecure_private_keys_fail_closed(self):
        manifest = compose(package_spec())
        self.private.chmod(0o644)
        with self.assertRaisesRegex(PackageError, "Private key"):
            sign(manifest, self.private)

        self.private.chmod(0o600)
        envelope = sign(manifest, self.private)
        expired = create_trust_root(self.public, "example.release", "2026-01-01T00:00:00Z")
        with self.assertRaisesRegex(PackageError, "expired"):
            verify(envelope, expired, now=dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc))

        wrong_identity = create_trust_root(self.public, "example.release", "2099-01-01T00:00:00Z")
        wrong_identity["keys"][0]["keyid"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(PackageError, "does not match"):
            verify(envelope, wrong_identity, now=dt.datetime(2026, 9, 5, tzinfo=dt.timezone.utc))

    def test_cli_composes_signs_and_verifies_without_constructing_launcher(self):
        spec_path = self.root / "spec.json"
        manifest_path = self.root / "manifest.json"
        bundle_path = self.root / "bundle.json"
        root_path = self.root / "root.json"
        spec_path.write_text(json.dumps(package_spec()), encoding="utf-8")

        def invoke(*arguments):
            stdout = io.StringIO()
            stderr = io.StringIO()

            def forbidden_launcher(**_options):
                raise AssertionError("package commands must not construct the launcher")

            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = cli.run(["--json", *arguments], launcher_factory=forbidden_launcher)
            return code, json.loads(stdout.getvalue() or stderr.getvalue())

        code, composed = invoke("packages", "compose", "--spec", str(spec_path), "--output", str(manifest_path))
        self.assertEqual(code, 0)
        self.assertEqual(composed["data"]["plugin_count"], 2)

        code, signed = invoke(
            "packages", "sign", "--manifest", str(manifest_path), "--private-key", str(self.private),
            "--output", str(bundle_path),
        )
        self.assertEqual(code, 0)
        self.assertRegex(signed["data"]["keyid"], r"^sha256:[0-9a-f]{64}$")

        code, trusted = invoke(
            "packages", "trust-root", "--public-key", str(self.public), "--root-id", "example.release",
            "--expires-at", "2099-01-01T00:00:00Z", "--output", str(root_path),
        )
        self.assertEqual(code, 0)
        self.assertEqual(trusted["data"]["root_id"], "example.release")

        code, verified = invoke(
            "packages", "verify", "--bundle", str(bundle_path), "--trust-root", str(root_path)
        )
        self.assertEqual(code, 0)
        self.assertFalse(verified["data"]["execution_authorized"])
        self.assertEqual(verified["data"]["plugin_count"], 2)


class PackageJsonSafetyTests(unittest.TestCase):
    def test_public_json_schemas_are_bounded_and_closed(self):
        root = Path(__file__).resolve().parents[1] / "schemas"
        expected = {
            "dsh-forge-catalog-feed-v1.schema.json",
            "dsh-forge-catalog-package-v1.schema.json",
            "dsh-forge-catalog-sources-v1.schema.json",
            "dsh-forge-archive-inspection-v1.schema.json",
            "dsh-forge-package-spec-v1.schema.json",
            "dsh-forge-package-installation-registry-v1.schema.json",
            "dsh-forge-package-v1.schema.json",
            "dsh-forge-promoted-profile-v1.schema.json",
            "dsh-forge-quarantine-receipt-v1.schema.json",
            "dsh-forge-sandbox-install-receipt-v1.schema.json",
            "dsh-forge-signed-envelope-v1.schema.json",
            "dsh-forge-trust-root-v1.schema.json",
        }
        self.assertEqual({path.name for path in root.glob("*.json")}, expected)
        for name in expected:
            schema = json.loads((root / name).read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(schema.get("additionalProperties", True))
            self.assertNotIn("https://dsh-forge.invalid", json.dumps(schema))

    def test_duplicate_json_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "duplicate.json"
            source.write_text('{"schema":"one","schema":"two"}', encoding="utf-8")
            with self.assertRaisesRegex(PackageError, "Duplicate JSON key"):
                read_json(source)


if __name__ == "__main__":
    unittest.main()
