import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

from dsh_forge import recommendations, sessions
from dsh_forge.recommendations import SessionIndex, capability_needs, recommend

NOW = 1_800_000_000
DAY = 86400


_projects = iter(range(10**6))


def summary(days_ago=1, project=None, subagent=False, retries=0, delegations=0, **signals):
    project = project or f"project-{next(_projects)}"
    base = {name: 0 for name in sessions.SIGNALS}
    base.update(signals)
    return {"created_at": NOW - days_ago * DAY, "project": project, "is_subagent": subagent,
            "steps": 10, "tool_calls": 20, "retries": retries, "delegations": delegations, "signals": base}


def plugin(identity, name, description="", topics=(), package=None, **extra):
    return {"artifact_id": identity, "artifact_type": "plugin", "name": name, "description": description,
            "topics": list(topics), "package": {"name": package or name}, **extra}


class NeedsTests(unittest.TestCase):
    def test_ranks_capabilities_by_share_of_recent_sessions(self):
        needs = capability_needs([
            summary(testing=9), summary(testing=5), summary(testing=3), summary(testing=1),
            summary(review=4), summary(review=3), summary(review=3),
            summary(search=1), summary(search=1),
        ], now=NOW)
        self.assertEqual([need["capability"] for need in needs], ["testing", "review"])
        testing = needs[0]
        self.assertEqual((testing["sessions"], testing["count"]), (4, 18))
        self.assertEqual(testing["evidence"], "You ran tests 18 times across 4 sessions.")
        # Search appeared in only two sessions, below the minimum.
        self.assertNotIn("search", [need["capability"] for need in needs])

    def test_one_huge_session_counts_once(self):
        steady = [summary(review=3), summary(review=3), summary(review=3)]
        spiky = [summary(testing=500), summary(testing=1), summary(testing=1)]
        needs = {need["capability"]: need["share"] for need in capability_needs(steady + spiky, now=NOW)}
        self.assertGreater(needs["review"], needs["testing"])

    def test_old_sessions_fade_and_very_old_ones_are_ignored(self):
        recent = [summary(days_ago=1, review=3) for _ in range(3)]
        older = [summary(days_ago=14, testing=3) for _ in range(3)]
        ancient = [summary(days_ago=90, security=5) for _ in range(5)]
        needs = {need["capability"]: need["share"] for need in capability_needs(recent + older + ancient, now=NOW)}
        self.assertGreater(needs["review"], needs["testing"])
        self.assertNotIn("security", needs)

    def test_after_a_break_the_window_ends_at_the_last_session(self):
        before_break = [summary(days_ago=60, testing=3) for _ in range(3)] + [summary(days_ago=120, review=3) for _ in range(3)]
        needs = [need["capability"] for need in capability_needs(before_break, now=NOW)]
        self.assertEqual(needs, ["testing"])

    def test_agent_started_sessions_are_left_out(self):
        children = [summary(subagent=True, testing=9) for _ in range(10)]
        self.assertEqual(capability_needs(children, now=NOW), [])

    def test_returning_to_one_project_and_delegating_and_retrying_count(self):
        self.assertEqual(capability_needs([summary(project="same") for _ in range(7)], now=NOW), [])
        returning = [summary(project="same") for _ in range(8)]
        needs = {need["capability"]: need for need in capability_needs(returning, now=NOW)}
        self.assertEqual(needs["memory"]["evidence"], "You kept returning to the same projects and notes: 8 sessions did.")
        self.assertEqual(needs["memory"]["share"], 0.5)
        busy = [summary(project=f"p{index}", delegations=4, retries=3) for index in range(3)]
        needs = {need["capability"]: need for need in capability_needs(busy, now=NOW)}
        self.assertEqual(needs["orchestration"]["count"], 12)
        self.assertEqual(needs["observability"]["evidence"], "Your sessions had to retry the model 9 times across 3 sessions.")

    def test_evidence_is_singular_when_it_should_be(self):
        self.assertEqual(recommendations._EVIDENCE["testing"](1, 1), "You ran tests 1 time across 1 session.")

    def test_tolerates_damaged_summaries(self):
        self.assertEqual(capability_needs([{}, {"created_at": "x"}, {"created_at": NOW, "signals": "bad"}], now=NOW), [])


class RecommendTests(unittest.TestCase):
    NEEDS = [
        {"capability": "testing", "evidence": "You ran tests 18 times across 4 sessions."},
        {"capability": "memory", "evidence": "memory evidence"},
        {"capability": "review", "evidence": "review evidence"},
        {"capability": "search", "evidence": "search evidence"},
    ]
    PLUGINS = [
        plugin("1", "dsh-test-runner", "Runs tests"),
        plugin("2", "dsh-memory", "Remember things"),
        plugin("3", "dsh-e2e-testing", topics=["testing"]),
        plugin("4", "dsh-playwright-test", "tests"),
        plugin("5", "dsh-code-review", "review"),
        plugin("6", "helper", "Mentions a test once"),
        plugin("7", "dsh-web-search", "search"),
        plugin("8", "dsh-test-archived", archived=True),
    ]

    def test_suggests_the_best_ranked_plugins_for_the_top_needs(self):
        items = recommend(self.NEEDS, self.PLUGINS, installed=[])
        self.assertEqual([(item["artifact"]["artifact_id"], item["capability"]) for item in items],
                         [("1", "testing"), ("3", "testing"), ("2", "memory"), ("5", "review")])
        self.assertEqual(items[0]["evidence"], "You ran tests 18 times across 4 sessions.")

    def test_skips_a_need_the_user_already_has_a_plugin_for(self):
        items = recommend(self.NEEDS, self.PLUGINS, installed=["DSH-Memory"])
        self.assertEqual([item["capability"] for item in items], ["testing", "testing", "review", "search"])
        self.assertNotIn("2", [item["artifact"]["artifact_id"] for item in items])

    def test_never_suggests_the_same_plugin_twice_or_an_archived_one(self):
        both = plugin("9", "dsh-test-review", "test and code review")
        items = recommend(self.NEEDS[:1] + self.NEEDS[2:3], [both], installed=[])
        self.assertEqual([item["artifact"]["artifact_id"] for item in items], ["9"])
        self.assertEqual(recommend(self.NEEDS[:1], [self.PLUGINS[7]], installed=[]), [])

    def test_a_plugin_is_suggested_only_for_what_it_is_mainly_about(self):
        memory = plugin("9", "dsh-agent-memory", "Long-term memory with logging, metrics and tracing of recalls")
        needs = [{"capability": "observability", "evidence": "e"}, {"capability": "memory", "evidence": "m"}]
        items = recommend(needs, [memory], installed=[])
        self.assertEqual([(item["artifact"]["artifact_id"], item["capability"]) for item in items], [("9", "memory")])

    def test_no_needs_or_no_matching_plugins_means_no_suggestions(self):
        self.assertEqual(recommend([], self.PLUGINS, installed=[]), [])
        self.assertEqual(recommend([{"capability": "security", "evidence": "e"}], self.PLUGINS, installed=[]), [])


class SessionIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.index = SessionIndex(self.root / "state")

    def log(self, name, command="pytest", cwd="/home/someone/private-project"):
        folder = self.home / "sessions" / "--home-someone-private-project--" / name
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "session.jsonl"
        records = [
            {"type": "session", "createdAt": NOW * 1000, "cwd": cwd},
            {"type": "tool/call", "data": {"name": "bash", "arguments": json.dumps({"command": command})}},
        ]
        path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
        return path

    def test_reads_each_log_once_and_rereads_only_what_changed(self):
        first = self.log("one")
        self.log("two")
        self.assertEqual(self.index.refresh([self.home]), {"read": 2, "waiting": 0, "sessions": 2})
        with mock.patch.object(sessions, "summarize_session", wraps=sessions.summarize_session) as spy:
            self.assertEqual(self.index.refresh([self.home])["read"], 0)
            spy.assert_not_called()
            first.write_text(first.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            self.assertEqual(self.index.refresh([self.home])["read"], 1)
            self.assertEqual(spy.call_count, 1)
        self.assertEqual(len(self.index.summaries()), 2)

    def test_stops_at_its_time_budget_and_reports_what_is_waiting(self):
        for name in ("one", "two", "three"):
            self.log(name)
        result = self.index.refresh([self.home], budget_seconds=-1)
        self.assertEqual(result, {"read": 0, "waiting": 3, "sessions": 0})
        self.assertEqual(self.index.refresh([self.home])["read"], 3)

    def test_forgets_logs_that_no_longer_exist(self):
        gone = self.log("one")
        self.log("two")
        self.index.refresh([self.home])
        gone.unlink()
        self.assertEqual(self.index.refresh([self.home])["sessions"], 1)
        self.assertEqual(len(self.index.summaries()), 1)

    def test_the_cache_is_private_and_holds_no_session_text_or_paths(self):
        self.log("one", command="pytest /home/someone/private-project/SECRET_test.py")
        self.index.refresh([self.home])
        raw = self.index.path.read_text(encoding="utf-8")
        for private in ("someone", "private-project", "SECRET", "pytest", "/home"):
            self.assertNotIn(private, raw)
        self.assertEqual(os.stat(self.index.path).st_mode & 0o777, 0o600)

    def test_clear_deletes_the_cache_and_a_damaged_cache_is_rebuilt(self):
        self.log("one")
        self.index.refresh([self.home])
        self.index.clear()
        self.assertFalse(self.index.path.exists())
        self.assertEqual(self.index.summaries(), [])
        self.index.path.parent.mkdir(parents=True, exist_ok=True)
        self.index.path.write_text("{broken", encoding="utf-8")
        self.assertEqual(self.index.refresh([self.home])["read"], 1)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "home"
        self.catalog = [plugin("1", "dsh-test-runner", "Runs tests"), plugin("2", "dsh-memory", "Remember things")]
        self.installed = []
        self.service = recommendations.RecommendationService(
            self.root / "state", lambda: [self.home], lambda: self.catalog, lambda: self.installed,
        )

    def sessions_with_tests(self, count=4):
        created = int(time.time()) - 3600
        for index in range(count):
            folder = self.home / "sessions" / f"project-{index}" / "s"
            folder.mkdir(parents=True, exist_ok=True)
            records = [{"type": "session", "createdAt": created * 1000, "cwd": f"/work/private-{index}"}]
            records += [{"type": "tool/call", "data": {"name": "bash", "arguments": json.dumps({"command": "pytest -q"})}}] * 4
            (folder / "session.jsonl").write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

    def test_reads_nothing_until_the_user_says_yes(self):
        self.sessions_with_tests()
        status = self.service.status()
        self.assertEqual((status["consent"], status["state"], status["items"]), ("unasked", "off", []))
        self.assertFalse((self.root / "state" / recommendations.CACHE_NAME).exists())
        self.assertFalse(self.service.scanning())

    def test_yes_scans_in_the_background_and_then_suggests_plugins(self):
        self.sessions_with_tests()
        self.service.set_consent(True)
        self.service.wait()
        status = self.service.status()
        self.assertEqual((status["consent"], status["state"], status["sessions"]), ("on", "ready", 4))
        self.assertEqual([item["artifact"]["artifact_id"] for item in status["items"]], ["1"])
        self.assertEqual(status["items"][0]["evidence"], "You ran tests 16 times across 4 sessions.")
        self.assertEqual(status["needs"][0]["capability"], "testing")
        # A plugin the user already has is not suggested again.
        self.installed.append("dsh-test-runner")
        self.assertEqual(self.service.status()["items"], [])

    def test_no_turns_it_off_and_deletes_what_was_derived(self):
        self.sessions_with_tests()
        self.service.set_consent(True)
        self.service.wait()
        cache = self.root / "state" / recommendations.CACHE_NAME
        self.assertTrue(cache.exists())
        status = self.service.set_consent(False)
        self.assertEqual((status["consent"], status["state"], status["items"]), ("off", "off", []))
        self.assertFalse(cache.exists())
        # The answer survives a restart.
        again = recommendations.RecommendationService(self.root / "state", lambda: [self.home], lambda: self.catalog, lambda: [])
        self.assertEqual(again.consent(), "off")

    def test_says_plainly_when_history_cannot_be_read(self):
        self.service.set_consent(True)
        self.service.wait()
        with mock.patch.object(sessions, "zstd_decoder", return_value=None):
            status = self.service.status()
        self.assertEqual(status["state"], "unavailable")
        self.assertIn("zstd", status["reason"])

    def test_rejects_a_consent_value_that_is_not_yes_or_no(self):
        with self.assertRaises(ValueError):
            self.service.set_consent("yes")
        self.assertEqual(self.service.consent(), "unasked")


if __name__ == "__main__":
    unittest.main()
