"""Bounded GitHub evidence: planning, batching, budgets, compaction, and size limits."""

import datetime as dt
import io
import json
import unittest

from dsh_forge import enrichment
from dsh_forge.enrichment import (
    EVIDENCE_SCHEMA,
    GITHUB_GRAPHQL,
    EnrichmentError,
    apply_evidence,
    compact,
    eligible,
    fetch_evidence,
    has_own_commits,
    normalize,
    plan_targets,
    previous_evidence,
    trim_evidence,
)


NOW = dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc)


def iso(days_ago):
    return (NOW - dt.timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def node(stars=3, **changes):
    value = {
        "nameWithOwner": "octo/dsh-plugin",
        "createdAt": iso(300),
        "pushedAt": iso(4),
        "isArchived": False,
        "stargazerCount": stars,
        "forkCount": 1,
        "watchers": {"totalCount": 2},
        "openIssues": {"totalCount": 1},
        "closedIssues": {"totalCount": 7},
        "mergedPullRequests": {"totalCount": 5},
        "releases": {"totalCount": 3},
        "mentionableUsers": {"totalCount": 4},
        "licenseInfo": {"spdxId": "MIT"},
        "owner": {"login": "octo", "__typename": "User", "followers": {"totalCount": 12}},
        "defaultBranchRef": {"target": {"history": {"totalCount": 210}, "recent": {"totalCount": 18}}},
        "root": {"entries": [
            {"name": "README.md", "type": "blob", "object": {"byteSize": 5400}},
            {"name": "tests", "type": "tree", "object": {}},
            {"name": "docs", "type": "tree", "object": {}},
            {"name": "CHANGELOG.md", "type": "blob", "object": {"byteSize": 900}},
        ]},
        "workflows": {"entries": [{"name": "ci.yml"}, {"name": "notes.txt"}]},
        "stargazers": {"edges": [
            {"starredAt": iso(3), "node": {"login": "harness-dev"}},
            {"starredAt": iso(50), "node": {"login": "stranger"}},
            {"starredAt": iso(2), "node": {"login": "octo"}},
        ]},
    }
    value.update(changes)
    return value


def record(index, *, kind="plugin", stars=0, pushed=10, created=300, **changes):
    value = {
        "artifact_id": f"github:{index}",
        "artifact_type": kind,
        "full_name": f"owner{index}/repo{index}",
        "owner": f"owner{index}",
        "description": "A plugin with a description long enough to count",
        "github_stars": stars,
        "pushed_at": iso(pushed),
        "created_at": iso(created),
        "license": {"spdx": "MIT"},
    }
    value.update(changes)
    return value


class FakeResponse(io.BytesIO):
    def __init__(self, payload, url=GITHUB_GRAPHQL):
        super().__init__(json.dumps(payload).encode())
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class NormalizeTests(unittest.TestCase):
    def test_reads_engineering_activity_and_community_facts(self):
        evidence = normalize(node(), NOW)
        self.assertEqual(evidence["schema"], EVIDENCE_SCHEMA)
        self.assertEqual(evidence["readme_bytes"], 5400)
        self.assertTrue(evidence["has_tests"])
        self.assertTrue(evidence["has_docs"])
        self.assertTrue(evidence["has_changelog"])
        self.assertEqual(evidence["ci_workflows"], 1)
        self.assertEqual(evidence["commits_recent"], 18)
        self.assertEqual(evidence["merged_pull_requests"], 5)
        self.assertEqual(evidence["license"], "MIT")
        self.assertEqual(len(evidence["recent_stargazers"]), 3)

    def test_compact_resolves_endorsements_without_keeping_identities(self):
        raw = normalize(node(), NOW)
        value = compact(raw, owner="octo", credible_accounts={"harness-dev", "octo"}, observed_at=NOW)
        self.assertNotIn("recent_stargazers", value)
        # The owner starring their own project is not an endorsement.
        self.assertEqual(value["endorsed_by"], ["harness-dev"])
        self.assertEqual(value["stars_last_30d"], 2)
        self.assertNotIn("archived", value)  # false values are dropped to keep the registry small


class PlanningTests(unittest.TestCase):
    def test_untouched_forks_are_not_worth_a_query(self):
        untouched = record(1, kind="fork", pushed=300, created=300)
        self.assertIs(has_own_commits(untouched), False)
        # A push half an hour after forking is still the fork's own work.
        quick = record(5, kind="fork", created=300, pushed_at=(NOW - dt.timedelta(days=300) + dt.timedelta(minutes=30)).isoformat())
        self.assertIs(has_own_commits(quick), True)
        self.assertFalse(eligible(untouched))
        self.assertTrue(eligible(record(2, kind="fork", pushed=3, created=300)))
        self.assertTrue(eligible(record(3, kind="fork", stars=2, pushed=300, created=300)))
        self.assertFalse(eligible(record(4, archived=True)))

    def test_fresh_evidence_is_reused_and_the_rest_is_ordered_by_promise(self):
        records = [record(1, stars=0, pushed=600), record(2, stars=30), record(3)]
        previous_registry = {"entries": [], "supplemental_entries": [
            {**records[2], "evidence": {"schema": EVIDENCE_SCHEMA, "observed_at": iso(2), "pushed_at": records[2]["pushed_at"]}},
        ]}
        snapshot = {"entries": [], "supplemental_entries": records}
        targets, reused = plan_targets(snapshot, previous_evidence(previous_registry), observed_at=NOW)
        self.assertEqual(list(reused), ["owner3/repo3"])
        self.assertEqual(targets, ["owner2/repo2", "owner1/repo1"])
        # Evidence from before the latest push is stale.
        stale = {"owner3/repo3": {"schema": EVIDENCE_SCHEMA, "observed_at": iso(2), "pushed_at": iso(40)}}
        targets, reused = plan_targets(snapshot, stale, observed_at=NOW)
        self.assertEqual(reused, {})
        self.assertIn("owner3/repo3", targets)


class FetchTests(unittest.TestCase):
    def test_batches_spend_points_and_stop_near_the_rate_limit(self):
        calls = []

        def opener(request, timeout):
            query = json.loads(request.data)["query"]
            calls.append(query)
            self.assertEqual(request.full_url, GITHUB_GRAPHQL)
            self.assertTrue(request.get_header("Authorization").startswith("Bearer "))
            count = query.count(": repository(")
            remaining = 100 if len(calls) == 1 else 5
            data = {f"r{index}": node(stars=index) for index in range(count)}
            data["rateLimit"] = {"cost": 2, "remaining": remaining}
            return FakeResponse({"data": data})

        slugs = [f"owner{index}/repo{index}" for index in range(5)]
        evidence, coverage = fetch_evidence(
            slugs, token="t", observed_at=NOW, opener=opener, batch_size=2, pause=lambda _: None,
        )
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(evidence), 4)
        self.assertEqual(coverage["status"], "incomplete")
        self.assertEqual(coverage["stopped"], "GitHub rate limit nearly exhausted")
        self.assertEqual(coverage["points_spent"], 4)

    def test_a_failing_batch_is_split_and_a_bad_repository_is_isolated(self):
        def opener(request, timeout):
            query = json.loads(request.data)["query"]
            if "owner1" in query:
                raise OSError("timeout")
            count = query.count(": repository(")
            return FakeResponse({"data": {f"r{index}": node() for index in range(count)}})

        slugs = [f"owner{index}/repo{index}" for index in range(4)]
        evidence, coverage = fetch_evidence(
            slugs, token="t", observed_at=NOW, opener=opener, batch_size=4, pause=lambda _: None,
        )
        self.assertEqual(sorted(evidence), ["owner0/repo0", "owner2/repo2", "owner3/repo3"])
        self.assertEqual(coverage["failures"], ["owner1/repo1: OSError"])

    def test_a_graphql_timeout_is_a_failure_and_a_secondary_rate_limit_stops_the_run(self):
        from urllib.error import HTTPError

        calls = []

        def timed_out(request, timeout):
            calls.append(1)
            return FakeResponse({"data": None, "errors": [{"message": "Something went wrong while executing your query"}]})

        evidence, coverage = fetch_evidence(
            ["owner0/repo0", "owner1/repo1"], token="t", observed_at=NOW, opener=timed_out, pause=lambda _: None,
        )
        self.assertEqual(evidence, {})
        self.assertEqual(coverage["status"], "incomplete")
        self.assertEqual(len(coverage["failures"]), 2)
        self.assertEqual(len(calls), 3)  # the pair, then each half

        def limited(request, timeout):
            calls.append(1)
            raise HTTPError(request.full_url, 403, "secondary rate limit", {}, None)

        calls.clear()
        _, coverage = fetch_evidence(
            [f"owner{index}/repo{index}" for index in range(60)], token="t", observed_at=NOW, opener=limited,
            pause=lambda _: None,
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(coverage["stopped"], "GitHub rate limit reached")

    def test_budget_redirects_and_unsafe_names_are_refused(self):
        def redirected(request, timeout):
            return FakeResponse({"data": {}}, url="https://example.com/graphql")

        evidence, coverage = fetch_evidence(
            ['bad"name/x', "owner/repo"], token="t", observed_at=NOW, opener=redirected, pause=lambda _: None,
        )
        self.assertEqual(coverage["requested_count"], 1)  # the quoted name never reaches a query
        self.assertEqual(evidence, {})
        self.assertTrue(coverage["failures"])
        _, coverage = fetch_evidence(["owner/repo"], token="t", observed_at=NOW, opener=redirected, max_points=0)
        self.assertEqual(coverage["stopped"], "point budget reached")
        with self.assertRaises(EnrichmentError):
            fetch_evidence(["owner/repo"], token="", observed_at=NOW)


class ApplyTests(unittest.TestCase):
    def test_evidence_lands_on_records_and_registry_size_is_capped(self):
        records = [record(index, stars=index) for index in range(1, 30)]
        snapshot = {"entries": [], "supplemental_entries": records, "coverage": []}
        evidence = {item["full_name"].casefold(): normalize(node(), NOW) for item in records}
        applied = apply_evidence(snapshot, evidence, credible_accounts=["harness-dev"], coverage={
            "source": enrichment.COVERAGE_SOURCE, "status": "complete", "observed_at": iso(0),
        })
        self.assertEqual(applied, len(records))
        self.assertEqual(snapshot["discovery_context"], {"credible_account_count": 1})
        self.assertEqual(records[0]["evidence"]["endorsed_by"], ["harness-dev"])
        size = len(json.dumps(snapshot, separators=(",", ":")).encode())
        dropped = trim_evidence(snapshot, observed_at=NOW, max_bytes=size - 1500)
        self.assertGreater(dropped, 0)
        self.assertLessEqual(len(json.dumps(snapshot, separators=(",", ":")).encode()), size - 1500)
        # The least promising records lose their evidence first.
        self.assertNotIn("evidence", records[0])
        self.assertIn("evidence", records[-1])
        self.assertEqual(trim_evidence(snapshot, observed_at=NOW, max_bytes=10**9), 0)


if __name__ == "__main__":
    unittest.main()
