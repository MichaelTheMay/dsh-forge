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
    benchmark_discovery_study,
    benchmark_queue,
    certify_proposal,
    compose_proposal,
    create_discovery_study,
    create_fork_assessment,
    discovery_queue,
    evaluate_artifact,
    fetch_npm_pin,
    merge_judgment_ledgers,
    plan_discovery_study,
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
    def test_power_plan_is_explicit_about_assumptions_and_supported_size(self):
        plan = plan_discovery_study(
            baseline_precision=0.4, minimum_lift=0.2, alpha=0.05, power=0.8
        )
        self.assertEqual(plan["required_per_arm"], 97)
        self.assertTrue(plan["supported_by_study_builder"])
        self.assertIn("Planning approximation only", plan["caveat"])
        with self.assertRaisesRegex(ResearchError, "outside supported bounds"):
            plan_discovery_study(baseline_precision=0.9, minimum_lift=0.2)

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
            queue, ledger, artifact_id=first, rating="exceptional",
            reviewer="TEST CURATOR", reviewed_at="2026-09-11T18:00:30Z",
        )
        self.assertEqual(len(ledger["judgments"]), 1)
        ledger = record_judgment(
            queue, ledger, artifact_id=second, rating="irrelevant",
            reviewer="Test curator", reviewed_at="2026-09-11T18:01:00Z",
        )
        ledger = record_judgment(
            queue, ledger, artifact_id=first, rating="promising",
            reviewer="Second curator", reviewed_at="2026-09-11T18:02:00Z",
        )
        benchmark = benchmark_queue(queue, ledger)
        self.assertEqual(benchmark["judged_count"], 3)
        self.assertEqual(benchmark["judged_artifact_count"], 2)
        self.assertEqual(benchmark["reviewer_count"], 2)
        self.assertEqual(benchmark["doubly_judged_count"], 1)
        self.assertEqual(benchmark["pairwise_exact_agreement"], 0.0)
        self.assertEqual(benchmark["ratings"]["exceptional"], 1)
        self.assertEqual(benchmark["abstention_count"], 0)
        self.assertEqual(benchmark["metrics"][0]["judgment_coverage"], 0.6667)
        self.assertEqual(benchmark["metrics"][0]["ndcg"], 1.0)
        self.assertEqual(
            [item["ordering"] for item in benchmark["comparisons"]],
            ["forge", "quality", "popularity", "recency"],
        )
        stale = {**queue, "snapshot_id": "new-snapshot"}
        with self.assertRaisesRegex(ResearchError, "same current discovery snapshot"):
            benchmark_queue(stale, ledger)

    def test_blinded_study_compares_selection_arms_without_leaking_rank_signals(self):
        record = plugin_record()
        records = [
            {
                **record,
                "artifact_id": f"github:{index + 1}",
                "github_id": index + 1,
                "owner": f"owner-{index}",
                "full_name": f"owner-{index}/plugin-{index}",
                "name": f"plugin-{index}",
                "github_stars": index,
                "pushed_at": f"2026-09-{index + 1:02d}T00:00:00Z",
            }
            for index in range(12)
        ]
        ballot, key = create_discovery_study({
            "snapshot_id": "study-source",
            "fetched_at": "2026-09-13T12:00:00Z",
            "supplemental_entries": records,
        }, per_arm=3, seed="fixed-test-seed")
        self.assertEqual(set(key["arms"]), {"forge", "quality", "popularity", "recency"})
        self.assertTrue(all(len(values) == 3 for values in key["arms"].values()))
        self.assertEqual(key["pool_size"], 12)
        self.assertEqual(key["arms"]["popularity"][0], "github:12")
        self.assertEqual(key["arms"]["recency"][0], "github:12")
        self.assertLessEqual(ballot["candidate_count"], 12)
        for item in ballot["candidates"]:
            self.assertNotIn("github_stars", item["artifact"])
            self.assertNotIn("pushed_at", item["artifact"])
            self.assertNotIn("score", item["research"])
            self.assertNotIn("visibility", item["research"])
            self.assertNotIn("arm", item)

        first_identity = ballot["candidates"][0]["artifact"]["artifact_id"]
        partial = record_judgment(
            ballot, None, artifact_id=first_identity, rating="exceptional",
            reviewer="First curator", reviewed_at="2026-09-13T18:00:00Z",
        )
        with self.assertRaisesRegex(ResearchError, "study is incomplete"):
            benchmark_discovery_study(
                ballot, key, partial, min_reviews_per_artifact=1, bootstrap_samples=100
            )
        ledger = None
        for index, candidate in enumerate(ballot["candidates"]):
            identity = candidate["artifact"]["artifact_id"]
            ledger = record_judgment(
                ballot, ledger, artifact_id=identity,
                rating="exceptional" if index % 2 == 0 else "weak",
                reviewer="First curator", reviewed_at=f"2026-09-13T18:{index:02d}:00Z",
            )
            ledger = record_judgment(
                ballot, ledger, artifact_id=identity,
                rating="promising" if index % 2 == 0 else "irrelevant",
                reviewer="Second curator", reviewed_at=f"2026-09-13T19:{index:02d}:00Z",
            )
        benchmark = benchmark_discovery_study(
            ballot, key, ledger, min_reviews_per_artifact=2, bootstrap_samples=100
        )
        self.assertTrue(benchmark["complete"])
        self.assertEqual(benchmark["reviewer_count"], 2)
        self.assertEqual(benchmark["doubly_judged_count"], ballot["candidate_count"])
        self.assertEqual(benchmark["bootstrap_samples"], 100)
        self.assertEqual(len(benchmark["comparisons"]), 3)
        self.assertIn("precision_ci_95", benchmark["arms"][0]["primary"])
        self.assertEqual(benchmark["weighted_kappa_reviewer_pairs"], 1)
        self.assertEqual(
            [item["ordering"] for item in benchmark["arms"]],
            ["forge", "quality", "popularity", "recency"],
        )

        tampered = json.loads(json.dumps(key))
        tampered["arms"]["forge"][0] = "github:missing"
        with self.assertRaisesRegex(ResearchError, "invalid ranking arm"):
            benchmark_discovery_study(
                ballot, tampered, ledger, min_reviews_per_artifact=2, bootstrap_samples=100
            )
        tampered_ballot = json.loads(json.dumps(ballot))
        tampered_ballot["candidates"][0]["artifact"]["description"] = "Changed after review"
        with self.assertRaisesRegex(ResearchError, "does not match the ballot"):
            benchmark_discovery_study(
                tampered_ballot, key, ledger, min_reviews_per_artifact=2, bootstrap_samples=100
            )

    def test_queue_benchmark_includes_the_full_candidate_set_above_one_hundred(self):
        record = plugin_record()
        records = [
            {
                **record,
                "artifact_id": f"github:{index + 1}",
                "github_id": index + 1,
                "owner": f"owner-{index}",
                "full_name": f"owner-{index}/plugin-{index}",
                "name": f"plugin-{index}",
            }
            for index in range(101)
        ]
        queue = discovery_queue({
            "snapshot_id": "large-benchmark",
            "fetched_at": "2026-09-13T18:00:00Z",
            "supplemental_entries": records,
        })
        ledger = {
            "schema": "dsh-forge.discovery-judgments/v3",
            "policy": POLICY_VERSION,
            "snapshot_id": queue["snapshot_id"],
            "judgments": [],
        }
        self.assertEqual(
            [item["cutoff"] for item in benchmark_queue(queue, ledger)["metrics"]],
            [10, 25, 100, 101],
        )

    def test_independent_judgment_ledgers_merge_without_losing_reviewers(self):
        record = plugin_record()
        queue = discovery_queue({
            "snapshot_id": "merge-study",
            "fetched_at": "2026-09-13T18:00:00Z",
            "supplemental_entries": [record],
        })
        identity = queue["candidates"][0]["artifact"]["artifact_id"]
        first = record_judgment(
            queue, None, artifact_id=identity, rating="promising",
            reviewer="Curator 1", reviewed_at="2026-09-13T18:00:00Z",
        )
        second = record_judgment(
            queue, None, artifact_id=identity, rating="exceptional",
            reviewer="Curator 2", reviewed_at="2026-09-13T18:01:00Z",
        )
        merged = merge_judgment_ledgers(queue, [first, second])
        self.assertEqual(len(merged["judgments"]), 2)
        self.assertEqual(benchmark_queue(queue, merged)["reviewer_count"], 2)

        conflict = record_judgment(
            queue, None, artifact_id=identity, rating="irrelevant",
            reviewer="Curator 1", reviewed_at="2026-09-13T18:00:00Z",
        )
        with self.assertRaisesRegex(ResearchError, "conflicting judgments"):
            merge_judgment_ledgers(queue, [first, conflict])

    def test_abstention_is_recorded_but_not_counted_as_a_relevance_judgment(self):
        queue = discovery_queue({
            "snapshot_id": "abstention-study",
            "fetched_at": "2026-09-13T18:00:00Z",
            "supplemental_entries": [plugin_record()],
        })
        identity = queue["candidates"][0]["artifact"]["artifact_id"]
        ledger = record_judgment(
            queue, None, artifact_id=identity, rating="abstain",
            reviewer="Curator 1", reviewed_at="2026-09-13T18:00:00Z",
            notes="Outside my area of expertise.",
        )
        benchmark = benchmark_queue(queue, ledger)
        self.assertEqual(benchmark["judgment_count"], 1)
        self.assertEqual(benchmark["judged_count"], 0)
        self.assertEqual(benchmark["judged_artifact_count"], 0)
        self.assertEqual(benchmark["abstention_count"], 1)
        self.assertEqual(benchmark["ratings"]["abstain"], 1)

        ballot, key = create_discovery_study({
            "snapshot_id": "abstention-confirmatory",
            "fetched_at": "2026-09-13T18:00:00Z",
            "supplemental_entries": [plugin_record()],
        }, per_arm=1, seed="abstention-seed")
        study_identity = ballot["candidates"][0]["artifact"]["artifact_id"]
        study_ledger = record_judgment(
            ballot, None, artifact_id=study_identity, rating="abstain",
            reviewer="Curator 1", reviewed_at="2026-09-13T18:00:00Z",
        )
        with self.assertRaisesRegex(ResearchError, "study is incomplete"):
            benchmark_discovery_study(
                ballot, key, study_ledger,
                min_reviews_per_artifact=1, bootstrap_samples=100,
            )

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
