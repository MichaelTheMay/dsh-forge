import base64
import io
import json
import unittest

from dsh_forge.analysis import enrich_github_forks, select_fork_leads
from dsh_forge.registry import _fork
from dsh_forge.research import evaluate_artifact
from tests.test_registry import fork


BASE = "a" * 40
MERGE_BASE = "b" * 40
HEAD = "c" * 40


class Response(io.BytesIO):
    def __init__(self, value, url):
        payload = json.dumps(value).encode()
        super().__init__(payload)
        self._url = url
        self.headers = {
            "Content-Length": str(len(payload)),
            "Date": "Fri, 11 Sep 2026 12:00:00 GMT",
        }

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class SequenceOpener:
    def __init__(self, values):
        self.values = iter(values)
        self.urls = []

    def __call__(self, request, **_kwargs):
        self.urls.append(request.full_url)
        return Response(next(self.values), request.full_url)


def snapshot():
    record = _fork(fork(1, "review-gem"), "deepseek-ai/deepseek-harness", source_branch="main")
    return {
        "schema_version": 1,
        "snapshot_id": "registry-test",
        "fetched_at": "2026-09-11T12:00:00Z",
        "provenance": {"method": "test"},
        "coverage": [],
        "entries": [record],
        "supplemental_entries": [],
        "package_entries": [],
    }


def compare(status="diverged"):
    return {
        "status": status,
        "ahead_by": 2,
        "behind_by": 1,
        "total_commits": 2,
        "base_commit": {"sha": BASE},
        "merge_base_commit": {"sha": MERGE_BASE},
        "commits": [{"sha": "d" * 40}, {"sha": HEAD}],
        "files": [
            {"filename": "package.json", "additions": 4, "deletions": 1},
            {"filename": "plugins/review/index.ts", "additions": 20, "deletions": 2},
            {"filename": ".github/workflows/review.yml", "additions": 8, "deletions": 0},
        ],
    }


class AnalysisTests(unittest.TestCase):
    def test_enrichment_pins_exact_commits_and_extracts_inert_signals(self):
        manifest = base64.b64encode(json.dumps({
            "name": "@example/dsh-review",
            "version": "1.2.3",
            "engines": {"node": ">=22"},
            "dependencies": {"@deepseek-ai/deepseek-harness": "^0.2.0"},
            "scripts": {"prepare": "build"},
        }).encode()).decode()
        opener = SequenceOpener([
            {"sha": BASE},
            {"sha": HEAD},
            compare(),
            {"encoding": "base64", "content": manifest},
        ])
        result = enrich_github_forks(snapshot(), opener=opener)
        record = result["entries"][0]
        self.assertEqual(record["head_sha"], HEAD)
        self.assertEqual(record["divergence"]["base_sha"], BASE)
        self.assertEqual(record["divergence"]["ahead_by"], 2)
        self.assertFalse(record["divergence"]["files_truncated"])
        self.assertEqual(record["compatibility"]["node_range"], ">=22")
        self.assertIn("plugin runtime", record["compatibility"]["changed_surfaces"])
        self.assertIn("changes automation workflows", record["risk_signals"])
        self.assertIn("declares package lifecycle scripts", record["risk_signals"])
        self.assertRegex(record["analysis_evidence"]["digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertFalse(record["verification"]["executed"])
        self.assertTrue(evaluate_artifact(record, result["fetched_at"])["candidate"])
        self.assertIn(f"deepseek-ai:{BASE}...example:{HEAD}", opener.urls[2])
        self.assertEqual(result["coverage"][-1]["analyzed_count"], 1)

    def test_compare_failure_keeps_the_useful_revision_pin_without_claiming_analysis(self):
        opener = SequenceOpener([
            {"sha": BASE},
            {"sha": HEAD},
            compare(status="unexpected"),
        ])
        result = enrich_github_forks(snapshot(), opener=opener)
        record = result["entries"][0]
        self.assertEqual(record["head_sha"], HEAD)
        self.assertEqual(record["analysis_status"], "revision_pinned_compare_failed")
        self.assertNotIn("divergence", record)
        self.assertEqual(result["coverage"][-1]["failed_count"], 1)
        self.assertEqual(result["coverage"][-1]["status"], "incomplete")

    def test_selection_is_deterministic_and_does_not_promote_a_lead(self):
        value = snapshot()
        self.assertEqual(select_fork_leads(value), ["github:1"])
        self.assertFalse(evaluate_artifact(value["entries"][0], value["fetched_at"])["candidate"])


if __name__ == "__main__":
    unittest.main()
