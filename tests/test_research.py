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
    benchmark_queue,
    certify_proposal,
    compose_proposal,
    create_fork_assessment,
    discovery_queue,
    evaluate_artifact,
    fetch_npm_pin,
    rank_artifacts,
    record_judgment,
    signed_review_statement,
)
from tests.test_marketplace import sample_catalog
from tests.test_registry import fork
from dsh_forge.registry import _fork


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
    def test_fork_assessment_binds_curator_decision_to_evidence_and_never_authorizes_install(self):
        record = _fork(fork(7, "review-gem"), "deepseek-ai/deepseek-harness")
        record.update({
            "head_sha": "a" * 40,
            "divergence": {"ahead_by": 2, "listed_file_count": 3, "status": "ahead"},
            "analysis_evidence": {"digest": "sha256:" + "b" * 64},
        })
        report = evaluate_artifact(record, "2026-09-11T12:00:00Z")
        assessment = create_fork_assessment(
            record,
            report,
            decision="advance",
            reviewer="Release curator",
            reviewed_at="2026-09-11T13:00:00-05:00",
            reviews=("source", "risk", "license", "compatibility"),
            notes="Advance to isolated source review.",
        )
        self.assertEqual(assessment["commit"], "a" * 40)
        self.assertEqual(assessment["reviewed_at"], "2026-09-11T18:00:00Z")
        self.assertFalse(assessment["claims"]["installation_authorized"])
        self.assertFalse(assessment["claims"]["signed"])
        self.assertRegex(assessment["assessment_digest"], r"^sha256:[0-9a-f]{64}$")
        record["head_sha"] = "c" * 40
        with self.assertRaisesRegex(ResearchError, "does not match"):
            create_fork_assessment(
                record,
                report,
                decision="advance",
                reviewer="Release curator",
                reviewed_at="2026-09-11T18:00:00Z",
                reviews=("source", "risk", "license", "compatibility"),
            )

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
        self.assertEqual(queue["quality"]["selection_policy"], "dsh-forge.discovery-diversity/v1")
        self.assertEqual(queue["quality"]["unique_owners"], 1)

    def test_selection_rotates_owners_without_leaving_the_quality_window(self):
        record = plugin_record()
        records = []
        for index, owner in enumerate(("same", "same", "same", "other-a", "other-b")):
            records.append({
                **record,
                "artifact_id": f"github:{index + 1}",
                "github_id": index + 1,
                "owner": owner,
                "full_name": f"{owner}/plugin-{index}",
            })
        ranked = rank_artifacts(records, "2026-09-10T08:07:32Z")
        first_three = sorted(records, key=lambda item: ranked[item["artifact_id"]]["rank"])[:3]
        self.assertEqual(len({item["owner"] for item in first_three}), 3)
        self.assertTrue(all(ranked[item["artifact_id"]]["selection"] for item in first_three))

        high = [
            {**record, "artifact_id": f"github:{index + 20}", "owner": "same"}
            for index in range(2)
        ]
        lower = {
            **record, "artifact_id": "github:30", "owner": "unique",
            "risk_signals": ["first", "second", "third", "fourth"],
        }
        ranked = rank_artifacts([*high, lower], "2026-09-10T08:07:32Z")
        self.assertLess(ranked[high[1]["artifact_id"]]["rank"], ranked[lower["artifact_id"]]["rank"])
        self.assertGreater(
            ranked[high[1]["artifact_id"]]["score"] - ranked[lower["artifact_id"]]["score"], 5
        )

    def test_queue_interleaves_artifact_types_and_reports_quality(self):
        plugin = plugin_record()
        plugins = [
            {**plugin, "artifact_id": f"github:{index + 1}", "github_id": index + 1}
            for index in range(3)
        ]
        forks = []
        for index in range(3):
            record = _fork(fork(100 + index, f"fork-{index}"), "deepseek-ai/deepseek-harness")
            record.update({
                "head_sha": f"{index + 1:040x}",
                "divergence": {"ahead_by": 2, "listed_file_count": 3, "status": "ahead"},
                "analysis_evidence": {"digest": "sha256:" + f"{index + 1:064x}"},
            })
            forks.append(record)
        queue = discovery_queue({
            "snapshot_id": "mixed",
            "fetched_at": "2026-09-10T08:07:32Z",
            "entries": forks,
            "supplemental_entries": plugins,
        }, limit=4)
        types = [item["artifact"]["artifact_type"] for item in queue["candidates"]]
        self.assertEqual(types, ["fork", "plugin", "fork", "plugin"])
        self.assertEqual(queue["quality"]["by_type"], {"fork": 2, "plugin": 2})
        self.assertEqual(queue["quality"]["score_window"], 5)

    def test_judgments_are_snapshot_bound_and_produce_rank_metrics(self):
        record = plugin_record()
        records = [
            {**record, "artifact_id": f"github:{index + 1}", "github_id": index + 1}
            for index in range(3)
        ]
        queue = discovery_queue({
            "snapshot_id": "judged",
            "fetched_at": "2026-09-10T08:07:32Z",
            "supplemental_entries": records,
        }, limit=3)
        first = queue["candidates"][0]["artifact"]["artifact_id"]
        second = queue["candidates"][1]["artifact"]["artifact_id"]
        ledger = record_judgment(
            queue, None, artifact_id=first, rating="exceptional",
            reviewer="Test curator", reviewed_at="2026-09-11T18:00:00Z",
        )
        ledger = record_judgment(
            queue, ledger, artifact_id=second, rating="irrelevant",
            reviewer="Test curator", reviewed_at="2026-09-11T18:01:00Z",
        )
        benchmark = benchmark_queue(queue, ledger)
        self.assertEqual(benchmark["judged_count"], 2)
        self.assertEqual(benchmark["ratings"]["exceptional"], 1)
        self.assertEqual(benchmark["metrics"][0]["judgment_coverage"], 0.6667)
        self.assertEqual(benchmark["metrics"][0]["ndcg"], 1.0)
        stale = {**queue, "snapshot_id": "new-snapshot"}
        with self.assertRaisesRegex(ResearchError, "same current discovery snapshot"):
            benchmark_queue(stale, ledger)

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
