import io
import json
import unittest

from dsh_forge.marketplace import normalize_catalog
from dsh_forge.registry import RegistryError, _fork, fetch_github_fork_network, merge_registry_snapshots
from dsh_forge.research import evaluate_artifact
from tests.test_marketplace import sample_catalog


def root(count=2):
    return {"id": 100, "full_name": "deepseek-ai/deepseek-harness", "network_count": count}


def fork(identity, name, *, stars=1):
    return {
        "id": identity,
        "node_id": f"node-{identity}",
        "full_name": f"example/{name}",
        "name": name,
        "owner": {"login": "example"},
        "private": False,
        "fork": True,
        "description": "A low-visibility security review workflow for agentic development tools.",
        "topics": ["security", "review"],
        "language": "Python",
        "stargazers_count": stars,
        "forks_count": 0,
        "pushed_at": "2026-09-10T00:00:00Z",
        "archived": False,
        "default_branch": "main",
        "license": {"spdx_id": "MIT"},
    }


class Response(io.BytesIO):
    def __init__(self, value, url, *, link=None):
        payload = json.dumps(value).encode()
        super().__init__(payload)
        self._url = url
        self.headers = {
            "Content-Length": str(len(payload)),
            "Date": "Fri, 11 Sep 2026 12:00:00 GMT",
            "ETag": '"test"',
        }
        if link:
            self.headers["Link"] = link

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class SequenceOpener:
    def __init__(self, responses):
        self.responses = iter(responses)

    def __call__(self, request, **_kwargs):
        value, url, link = next(self.responses)
        return Response(value, url, link=link)


class RegistryTests(unittest.TestCase):
    def test_full_pagination_only_claims_complete_after_count_reconciliation(self):
        first = "https://api.github.com/repos/deepseek-ai/deepseek-harness/forks?sort=oldest&per_page=100&page=1"
        second = "https://api.github.com/repositories/100/forks?sort=oldest&per_page=100&page=2"
        opener = SequenceOpener([
            (root(), "https://api.github.com/repos/deepseek-ai/deepseek-harness", None),
            ([fork(1, "one")], first, f'<{second}>; rel="next"'),
            ([fork(2, "two")], second, None),
            (root(), "https://api.github.com/repos/deepseek-ai/deepseek-harness", None),
        ])
        snapshot = fetch_github_fork_network(opener=opener)
        self.assertEqual(snapshot["coverage"][0]["status"], "complete")
        self.assertEqual(snapshot["coverage"][0]["discovered_count"], 2)
        self.assertEqual(len(snapshot["entries"]), 2)
        self.assertTrue(all(item["head_sha"] is None for item in snapshot["entries"]))

    def test_changed_count_and_page_budget_are_reported_as_incomplete(self):
        first = "https://api.github.com/repos/deepseek-ai/deepseek-harness/forks?sort=oldest&per_page=100&page=1"
        second = "https://api.github.com/repositories/100/forks?page=2"
        opener = SequenceOpener([
            (root(2), "https://api.github.com/repos/deepseek-ai/deepseek-harness", None),
            ([fork(1, "one")], first, f'<{second}>; rel="next"'),
            (root(3), "https://api.github.com/repos/deepseek-ai/deepseek-harness", None),
        ])
        coverage = fetch_github_fork_network(opener=opener, max_pages=1)["coverage"][0]
        self.assertEqual(coverage["status"], "incomplete")
        self.assertTrue(coverage["truncated"])
        self.assertIn("fork-network count changed", " ".join(coverage["incomplete_reasons"]))

    def test_recurses_only_into_forks_that_report_children(self):
        first = "https://api.github.com/repos/deepseek-ai/deepseek-harness/forks?sort=oldest&per_page=100&page=1"
        child_url = "https://api.github.com/repos/example/one/forks?sort=oldest&per_page=100&page=1"
        parent = fork(1, "one")
        parent["forks_count"] = 1
        opener = SequenceOpener([
            (root(2), "https://api.github.com/repos/deepseek-ai/deepseek-harness", None),
            ([parent, fork(2, "two")], first, None),
            ([fork(3, "three")], child_url, None),
            (root(2), "https://api.github.com/repos/deepseek-ai/deepseek-harness", None),
        ])
        snapshot = fetch_github_fork_network(opener=opener)
        coverage = snapshot["coverage"][0]
        self.assertEqual(coverage["status"], "complete")
        self.assertEqual(coverage["direct_discovered_count"], 2)
        self.assertEqual(coverage["descendant_count"], 1)
        self.assertEqual(coverage["expanded_parents"], 1)
        child = next(item for item in snapshot["entries"] if item["github_id"] == 3)
        self.assertEqual(child["parent_repository"], "example/one")

    def test_rejects_pagination_to_another_host(self):
        first = "https://api.github.com/repos/deepseek-ai/deepseek-harness/forks?sort=oldest&per_page=100&page=1"
        opener = SequenceOpener([
            (root(1), "https://api.github.com/repos/deepseek-ai/deepseek-harness", None),
            ([fork(1, "one")], first, '<https://evil.example/page/2>; rel="next"'),
        ])
        with self.assertRaisesRegex(RegistryError, "left the public API"):
            fetch_github_fork_network(opener=opener)

    def test_rejects_unsafe_token_before_opening_a_request(self):
        with self.assertRaisesRegex(RegistryError, "HTTP credential"):
            fetch_github_fork_network(token="secret\nheader", opener=lambda *_args, **_kwargs: None)

    def test_merge_keeps_one_repository_and_preserves_both_classifications(self):
        marketplace = sample_catalog()
        marketplace["entries"][0]["repositoryId"] = "1"
        from dsh_forge.marketplace import catalog_digest
        marketplace["integrity"]["digest"] = catalog_digest(marketplace)
        plugins = normalize_catalog(marketplace, "https://catalog.example/plugins.json")
        forks = {
            "schema_version": 1,
            "snapshot_id": "forks",
            "fetched_at": "2026-09-11T12:00:00Z",
            "source_url": "https://api.github.com/repos/deepseek-ai/deepseek-harness/forks",
            "provenance": {"method": "test"},
            "coverage": [],
            "entries": [_fork(fork(1, "dsh-memory"), "deepseek-ai/deepseek-harness")],
            "supplemental_entries": [],
            "package_entries": [],
        }
        merged = merge_registry_snapshots(plugins, forks)
        self.assertEqual(len(merged["supplemental_entries"]), 1)
        record = merged["supplemental_entries"][0]
        self.assertEqual(record["artifact_type"], "plugin")
        self.assertEqual(set(record["classifications"]), {"plugin", "fork"})

    def test_fork_can_enter_metadata_research_without_being_installable(self):
        record = _fork(fork(1, "review-gem"), "deepseek-ai/deepseek-harness")
        report = evaluate_artifact(record, "2026-09-11T12:00:00Z")
        self.assertTrue(report["candidate"])
        self.assertFalse(report["security_verified"])
        self.assertIn("no immutable source revision", report["gaps"])
        self.assertIn("fork divergence not analyzed", report["gaps"])

    def test_capability_terms_do_not_match_inside_unrelated_words(self):
        value = fork(2, "generic")
        value["description"] = "DeepSeek Harness developer preview source with ordinary upstream behavior."
        value["topics"] = []
        record = _fork(value, "deepseek-ai/deepseek-harness")
        report = evaluate_artifact(record, "2026-09-11T12:00:00Z")
        self.assertNotIn("review", report["capabilities"])
        self.assertFalse(report["candidate"])


if __name__ == "__main__":
    unittest.main()
