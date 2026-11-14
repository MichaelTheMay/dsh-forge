import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from dsh_forge import sessions


def call(name, **arguments):
    return {"type": "tool/call", "seq": 1, "time": 1, "data": {"turn": 1, "step": 1, "callId": "c", "name": name,
                                                             "arguments": json.dumps(arguments)}}


def log_records():
    return [
        {"type": "session", "version": 1, "id": "s1", "createdAt": 1_790_000_000_000, "cwd": "/home/someone/secret-project",
         "parentSession": "", "origin": "user", "delegationDepth": 0, "agentPreset": "default"},
        {"type": "user/message", "data": {"content": [{"text": "PRIVATE PROMPT about tool/call and pytest"}]}},
        {"type": "step/start", "data": {"turn": 1, "step": 1}},
        call("bash", command="cd /home/someone/secret-project && pytest -q tests/", description="run tests"),
        call("bash", command="npm run test -- --watch=false"),
        call("bash", command="git diff HEAD~1 -- src/PRIVATE_FILE.py"),
        call("bash", command="rg 'needle' src/"),
        call("bash", command="npm audit --production"),
        call("bash", command="ls -la"),
        call("grep", pattern="PRIVATE_PATTERN", include="*.py"),
        call("glob", pattern="**/*.ts", path="."),
        call("read", file_path="/home/someone/secret-project/NOTES.md", limit=10),
        call("read", file_path="/home/someone/secret-project/src/app.py"),
        call("web_search", query="PRIVATE QUERY"),
        call("report", output="PRIVATE REPORT"),
        {"type": "tool/result", "data": {"turn": 1, "step": 1, "message": {"isError": True, "content": "PRIVATE OUTPUT"}}},
        {"type": "tool/result", "data": {"turn": 1, "step": 1, "message": {"content": "fine"}}},
        {"type": "llm/retry", "data": {"retry": 1}},
        {"type": "llm/retry-started", "data": {"retry": 1}},
        {"type": "agent/inbox/spliced", "data": {"target": "x"}},
        {"type": "web/deepseek-search-llm-request", "data": {}},
        {"type": "text-chunks", "data": {"texts": ["PRIVATE ANSWER " * 50]}},
        {"type": "step/start", "data": {"turn": 1, "step": 2}},
    ]


def write_plain(folder, records=None, name="session.jsonl", extra=b""):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    body = b"".join(json.dumps(record).encode() + b"\n" for record in (records or log_records()))
    path.write_bytes(body + extra)
    return path


class SummarizeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_counts_what_kind_of_work_a_session_did(self):
        summary = sessions.summarize_session(write_plain(self.root / "a"))
        self.assertEqual(summary["signals"], {
            "testing": 2, "search": 2, "code_search": 3, "review": 1, "security": 1, "memory": 1, "orchestration": 1,
        })
        self.assertEqual((summary["steps"], summary["tool_calls"]), (2, 12))
        self.assertEqual((summary["retries"], summary["delegations"]), (1, 1))
        self.assertEqual(summary["created_at"], 1_790_000_000)
        self.assertFalse(summary["is_subagent"])

    def test_the_summary_carries_no_text_from_the_session(self):
        summary = json.dumps(sessions.summarize_session(write_plain(self.root / "a")))
        for private in ("PRIVATE", "secret-project", "someone", "pytest", "needle", "NOTES.md", "/home"):
            self.assertNotIn(private, summary)
        # The project is a one-way hash: stable, so sessions group, but not the path.
        again = sessions.summarize_session(write_plain(self.root / "b"))
        self.assertEqual(json.loads(summary)["project"], again["project"])
        self.assertEqual(len(again["project"]), 12)

    def test_marks_sessions_started_by_another_agent(self):
        records = log_records()
        records[0] = {**records[0], "parentSession": "parent-id", "delegationDepth": 1}
        self.assertTrue(sessions.summarize_session(write_plain(self.root / "a", records))["is_subagent"])

    def test_survives_damaged_lines_and_strange_shapes(self):
        records = [
            {"type": "tool/call", "data": {"name": "bash", "arguments": "{not json"}},
            {"type": "tool/call", "data": {"name": 7}},
            {"type": "tool/call", "data": "nope"},
            {"type": "tool/call", "data": {"name": "bash", "arguments": {"command": "pytest"}}},
            {"type": "session", "createdAt": "yesterday", "cwd": 5},
        ]
        path = write_plain(self.root / "a", records, extra=b'{"type":"tool/call" broken\n\xff\xfe\n[1,2]\n')
        summary = sessions.summarize_session(path)
        self.assertEqual(summary["signals"]["testing"], 1)
        self.assertEqual(summary["tool_calls"], 4)
        self.assertIsNone(summary["created_at"])
        self.assertEqual(summary["project"], "")

    def test_stops_at_its_time_limit(self):
        path = write_plain(self.root / "a", [call("bash", command="pytest")] * 200)
        with mock.patch.object(sessions.time, "monotonic", side_effect=[0.0] + [100.0] * 500):
            summary = sessions.summarize_session(path, max_seconds=1.0)
        self.assertEqual(summary["tool_calls"], 0)


class FilesTests(unittest.TestCase):
    def test_finds_logs_under_each_home_newest_first(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root) / "home"
            old = write_plain(home / "sessions" / "proj" / "one")
            new = write_plain(home / "sessions" / "proj" / "two", name="session.jsonl.zstd")
            write_plain(home / "elsewhere" / "x")
            os.utime(old, (time.time() - 500, time.time() - 500))
            self.assertEqual(sessions.session_files([home, Path(root) / "missing"]), [new, old])


class DecoderTests(unittest.TestCase):
    def test_prefers_the_zstd_program_then_node_then_gives_up(self):
        with mock.patch.dict("sys.modules", {"compression": None}):
            with mock.patch.object(sessions.shutil, "which", side_effect=lambda name: "/usr/bin/zstd" if name == "zstd" else None):
                self.assertEqual(sessions.zstd_decoder()[0], "zstd")
            with mock.patch.object(sessions.shutil, "which", side_effect=lambda name: "/usr/bin/node" if name == "node" else None), \
                    mock.patch.object(sessions, "_node_can_decompress", return_value=True):
                self.assertEqual(sessions.zstd_decoder()[0], "node")
            with mock.patch.object(sessions.shutil, "which", side_effect=lambda name: "/usr/bin/node" if name == "node" else None), \
                    mock.patch.object(sessions, "_node_can_decompress", return_value=False):
                self.assertIsNone(sessions.zstd_decoder())
            with mock.patch.object(sessions.shutil, "which", return_value=None):
                self.assertIsNone(sessions.zstd_decoder())
                with tempfile.TemporaryDirectory() as root:
                    path = Path(root) / "session.jsonl.zstd"
                    path.write_bytes(b"x")
                    with self.assertRaises(sessions.SessionReadError):
                        list(sessions.iter_records(path))

    @unittest.skipUnless(shutil.which("zstd"), "the zstd program is needed to build a compressed fixture")
    def test_reads_a_real_compressed_log_with_each_available_decoder(self):
        with tempfile.TemporaryDirectory() as root:
            plain = write_plain(Path(root) / "a")
            packed = Path(root) / "a" / "session.jsonl.zstd"
            subprocess.run(["zstd", "-q", "-o", str(packed), str(plain)], check=True)
            expected = sessions.summarize_session(plain)
            self.assertEqual(sessions.summarize_session(packed), expected)
            node = shutil.which("node")
            if node and sessions._node_can_decompress(node):
                with mock.patch.dict("sys.modules", {"compression": None}), \
                        mock.patch.object(sessions.shutil, "which", side_effect=lambda name: node if name == "node" else None):
                    self.assertEqual(sessions.zstd_decoder()[0], "node")
                    self.assertEqual(sessions.summarize_session(packed), expected)


if __name__ == "__main__":
    unittest.main()
