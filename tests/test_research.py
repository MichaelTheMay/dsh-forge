import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from dsh_forge.catalog_store import CatalogStore, build
from dsh_forge.marketplace import normalize_catalog
from dsh_forge.packages import verify
from dsh_forge.research import (
    POLICY_VERSION,
    ResearchError,
    certify_proposal,
    compose_proposal,
    discovery_queue,
    evaluate_artifact,
    fetch_npm_pin,
    rank_artifacts,
    signed_review_statement,
)
from tests.test_marketplace import sample_catalog


def plugin_record():
    return normalize_catalog(sample_catalog(), "https://catalog.example/plugins.json")["supplemental_entries"][0]


class Response(io.BytesIO):
    def __init__(self, value, url="https://registry.npmjs.org/@example%2Fdsh-memory/0.5.2"):
        payload = json.dumps(value).encode()
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}
        self._url = url

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def npm_pin(name="@example/dsh-memory", version="0.5.2"):
    return {
        "kind": "npm",
        "name": name,
        "version": version,
        "url": f"https://registry.npmjs.org/example/-/dsh-memory-{version}.tgz",
        "integrity": "sha512-YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYQ==",
    }


class ResearchTests(unittest.TestCase):
    def test_hidden_gem_score_is_explainable_and_rewards_low_visibility(self):
        record = plugin_record()
        report = evaluate_artifact(record, "2026-09-10T08:07:32Z")
        self.assertTrue(report["candidate"])
        self.assertEqual(report["policy"], POLICY_VERSION)
        self.assertEqual(report["visibility"], "nearly unseen")
        self.assertFalse(report["security_verified"])
        self.assertIn("low-visibility", {signal["id"] for signal in report["signals"]})

        popular = {**record, "artifact_id": "github:2", "github_stars": 500}
        ranked = rank_artifacts([popular, record], "2026-09-10T08:07:32Z")
        self.assertLess(ranked[record["artifact_id"]]["rank"], ranked[popular["artifact_id"]]["rank"])

    def test_invalid_or_archived_artifact_never_becomes_candidate(self):
        record = plugin_record()
        record["external_validation"] = {"status": "invalid", "code": "bad-manifest"}
        record["archived"] = True
        report = evaluate_artifact(record, "2026-09-10T08:07:32Z")
        self.assertFalse(report["candidate"])
        self.assertIn("invalid", {signal["id"] for signal in report["signals"]})

    def test_store_returns_research_evidence_separately_from_source_record(self):
        snapshot = normalize_catalog(sample_catalog(), "https://catalog.example/plugins.json")
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "catalog.sqlite3"
            build(path, snapshot)
            store = CatalogStore(path)
            try:
                page = store.search(types=["plugin"], sort="rank")
                identity = page["artifacts"][0]["artifact_id"]
                self.assertEqual(page["research"][identity], store.get_research(identity))
                self.assertNotIn("hidden_gem", page["artifacts"][0])
            finally:
                store.close()

    def test_discovery_queue_is_bounded_without_dropping_source_breadth(self):
        record = plugin_record()
        records = [
            {**record, "artifact_id": f"github:{index + 1}", "github_id": index + 1}
            for index in range(300)
        ]
        snapshot = {
            "snapshot_id": "wide-catalog",
            "fetched_at": "2026-09-10T08:07:32Z",
            "provenance": {"source": "test"},
            "supplemental_entries": records,
        }
        queue = discovery_queue(snapshot)
        self.assertEqual(queue["source_count"], 300)
        self.assertEqual(queue["candidate_count"], 250)
        self.assertEqual(len(queue["candidates"]), 250)
        self.assertTrue(all(item["research"]["candidate"] for item in queue["candidates"]))
        self.assertFalse(queue["claims"]["security_verified"])

    def test_npm_pin_resolution_checks_identity_sri_and_tarball(self):
        metadata = {
            "name": "@example/dsh-memory",
            "version": "0.5.2",
            "dist": npm_pin()["integrity"] and {
                "integrity": npm_pin()["integrity"],
                "tarball": npm_pin()["url"],
            },
        }
        pin = fetch_npm_pin(
            "@example/dsh-memory",
            "0.5.2",
            opener=lambda *_args, **_kwargs: Response(metadata),
        )
        self.assertEqual(pin, npm_pin())
        metadata["name"] = "wrong"
        with self.assertRaisesRegex(ResearchError, "identity"):
            fetch_npm_pin("@example/dsh-memory", "0.5.2", opener=lambda *_args, **_kwargs: Response(metadata))

    def test_certification_requires_every_explicit_review_before_signing(self):
        proposal, _ = compose_proposal(
            [plugin_record()],
            package_id="hidden-memory",
            name="Hidden Memory",
            version="1.0.0",
            description="A curator-reviewed memory plugin candidate.",
            created_at="2026-09-11T05:00:00Z",
            pin_resolver=lambda name, version: npm_pin(name, version),
        )
        with self.assertRaisesRegex(ResearchError, "explicit source"):
            certify_proposal(
                proposal,
                private_key="not-opened.pem",
                public_key="not-opened.pem",
                root_id="forge.curator",
                expires_at="2099-01-01T00:00:00Z",
                reviewer="Release curator",
                reviews=("source", "permissions", "license"),
                destination_root="not-created",
            )

        proposal["research"][0]["subject"]["package_version"] = "9.9.9"
        with self.assertRaisesRegex(ResearchError, "does not match"):
            certify_proposal(
                proposal,
                private_key="not-opened.pem",
                public_key="not-opened.pem",
                root_id="forge.curator",
                expires_at="2099-01-01T00:00:00Z",
                reviewer="Release curator",
                reviews=("source", "permissions", "license", "compatibility"),
                destination_root="not-created",
            )

    @unittest.skipUnless(shutil.which("openssl"), "OpenSSL is required for certification")
    def test_proposal_and_certification_publish_a_verified_local_recipe(self):
        proposal, reports = compose_proposal(
            [plugin_record()],
            package_id="hidden-memory",
            name="Hidden Memory",
            version="1.0.0",
            description="A curator-reviewed memory plugin candidate.",
            created_at="2026-09-11T05:00:00Z",
            pin_resolver=lambda name, version: npm_pin(name, version),
        )
        self.assertEqual(proposal["status"], "pending_curator_review")
        self.assertEqual(len(reports), 1)
        self.assertFalse(proposal["security_verified"])

        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            private = root / "private.pem"
            public = root / "public.pem"
            subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", private], check=True, capture_output=True)
            private.chmod(0o600)
            subprocess.run(["openssl", "pkey", "-in", private, "-pubout", "-out", public], check=True, capture_output=True)
            result = certify_proposal(
                proposal,
                private_key=private,
                public_key=public,
                root_id="forge.curator",
                expires_at="2099-01-01T00:00:00Z",
                reviewer="Release curator",
                reviews=("source", "permissions", "license", "compatibility"),
                destination_root=root / "published",
            )
            directory = Path(result["directory"])
            envelope = json.loads((directory / "envelope.json").read_text(encoding="utf-8"))
            trust = json.loads((directory / "trust-root.json").read_text(encoding="utf-8"))
            certification = json.loads((directory / "certification.json").read_text(encoding="utf-8"))
            verified = verify(envelope, trust)
            self.assertEqual(verified["payload_digest"], certification["payload_digest"])
            self.assertEqual(
                verified["manifest"]["provenance"]["created_by"],
                signed_review_statement("Release curator"),
            )
            self.assertFalse(certification["sandbox_verified"])


if __name__ == "__main__":
    unittest.main()
