"""Local catalog store.

The embedded snapshot cannot grow to the size of the real fork network, so a
connected sidecar reads from an imported SQLite store instead. These tests
cover the store's contract: it indexes without executing anything, it never
upgrades the trust of what it imported, it survives free-text input, and it
stays bounded at fork-network scale.
"""

import base64
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import unittest

from dsh_forge import cli
from dsh_forge.catalog_store import (
    CATALOG_PAYLOAD_TYPE,
    MAX_OFFSET,
    MAX_PAGE_SIZE,
    STORE_SCHEMA_VERSION,
    CatalogStore,
    CatalogStoreError,
    build,
    canonical_snapshot_bytes,
    sign_snapshot,
    verify_snapshot,
)
from dsh_forge.launcher import Launcher, LauncherError
from dsh_forge.packages import create_trust_root
from tests.helpers import FakeCellSandbox


ROOT = Path(__file__).resolve().parents[1]


def seed_snapshot():
    snapshot = json.loads((ROOT / "data/public-repos.seed.json").read_text(encoding="utf-8"))
    feed = json.loads((ROOT / "data/package-catalog.seed.json").read_text(encoding="utf-8"))
    snapshot["package_entries"] = feed["packages"]
    return snapshot


def synthetic(count, *, start=0):
    """Bounded synthetic fork records for scale and paging assertions."""
    entries = []
    for index in range(start, start + count):
        owner = "owner%05d" % index
        entries.append({
            "artifact_id": "github:%d" % (1_000_000 + index),
            "artifact_type": "fork",
            "full_name": owner + "/harness-fork",
            "owner": owner,
            "name": "harness-fork",
            "description": "synthetic record %d" % index,
            "topics": ["deepseek", "harness"],
            "github_stars": index % 500,
            "pushed_at": "2026-09-%02dT00:00:00Z" % ((index % 28) + 1),
            "license": {"spdx": "MIT"},
            "archived": index % 10 == 0,
            "language": "TypeScript",
            "head_sha": "a" * 40,
            "seed_rank": None,
        })
    return entries


class CatalogStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # Registered first so it runs last: every store connection is closed
        # before the directory is removed, which Windows requires.
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "catalog.sqlite3"

    def store(self, snapshot=None, **options):
        build(self.path, snapshot if snapshot is not None else seed_snapshot(), **options)
        store = CatalogStore(self.path)
        self.addCleanup(store.close)
        return store

    def test_seed_import_indexes_every_artifact_type(self):
        store = self.store()
        meta = store.meta()
        self.assertEqual(meta["counts"], {"package": 3, "plugin": 7, "fork": 10})
        self.assertEqual(meta["artifact_count"], 20)
        self.assertEqual(meta["schema_version"], STORE_SCHEMA_VERSION)
        self.assertEqual(meta["snapshot_id"], seed_snapshot()["snapshot_id"])
        self.assertEqual(meta["coverage"], [])

    def test_records_are_returned_verbatim_so_one_mapping_serves_both_paths(self):
        snapshot = seed_snapshot()
        store = self.store(snapshot)
        expected = snapshot["entries"][0]
        found = store.get(expected["artifact_id"])
        self.assertEqual(found, expected)

    def test_free_text_search_matches_across_names_topics_and_packages(self):
        store = self.store()
        found = store.search(query="agent teams")
        slugs = {item.get("full_name") or item.get("slug") for item in found["artifacts"]}
        self.assertIn("NanmiCoder/dsh-agent-teams", slugs)
        self.assertIn("agent-teams-builder", slugs)

    def test_punctuated_and_hostile_queries_are_matched_literally(self):
        store = self.store()
        # A scoped npm name must match the plugin that declares it.
        found = store.search(query="@nanmicoder/dsh-agent-teams")
        self.assertTrue(found["total"] >= 1)
        # FTS5 operator syntax in user input is data, not query structure.
        for hostile in ['"', 'NEAR(a b)', 'a OR b', '*', 'a AND (b', '^x', 'a NOT b', '""""']:
            with self.subTest(query=hostile):
                result = store.search(query=hostile)
                self.assertIsInstance(result["total"], int)

    def test_empty_and_whitespace_queries_browse_instead_of_failing(self):
        store = self.store()
        for value in ["", "   ", "!!!", "@@@"]:
            with self.subTest(query=value):
                self.assertEqual(store.search(query=value)["total"], 20)

    def test_type_filter_keeps_repository_rows_in_the_plugin_browser(self):
        snapshot = seed_snapshot()
        snapshot["supplemental_entries"] = [
            {**snapshot["supplemental_entries"][0], "artifact_type": "repository",
             "artifact_id": "github:999999", "github_id": 999999}
        ]
        store = self.store(snapshot)
        self.assertEqual(store.search(types=["plugin"])["total"], 1)
        self.assertEqual(store.search(types=["fork"])["total"], 10)
        self.assertEqual(store.search(types=["package"])["total"], 3)
        self.assertEqual(store.search(types=["fork", "package"])["total"], 13)

    def test_filters_narrow_without_changing_the_record_shape(self):
        store = self.store()
        everything = store.search()["total"]
        self.assertLessEqual(store.search(featured_only=True)["total"], everything)
        self.assertLessEqual(store.search(include_archived=False)["total"], everything)
        self.assertLessEqual(store.search(licensed_only=True)["total"], everything)

    def test_sorts_are_total_and_deterministic(self):
        store = self.store()
        stars = [item.get("github_stars") or 0 for item in store.search(types=["fork"], sort="stars")["artifacts"]]
        self.assertEqual(stars, sorted(stars, reverse=True))
        recent = [item["pushed_at"] for item in store.search(types=["fork"], sort="recent")["artifacts"]]
        self.assertEqual(recent, sorted(recent, reverse=True))
        names = [item["name"].casefold() for item in store.search(types=["fork"], sort="name")["artifacts"]]
        self.assertEqual(names, sorted(names))
        # Same query twice must return the same order.
        self.assertEqual(store.search(sort="rank")["artifacts"], store.search(sort="rank")["artifacts"])
        with self.assertRaises(CatalogStoreError):
            store.search(sort="stars; DROP TABLE artifacts")

    def test_paging_covers_every_record_exactly_once(self):
        store = self.store({"entries": synthetic(450), "snapshot_id": "s", "fetched_at": "2026-09-10T00:00:00Z"})
        seen, cursor, pages = [], "", 0
        while True:
            page = store.search(sort="name", limit=100, cursor=cursor)
            seen.extend(item["artifact_id"] for item in page["artifacts"])
            pages += 1
            cursor = page["next_cursor"]
            if not cursor:
                break
        self.assertEqual(pages, 5)
        self.assertEqual(len(seen), 450)
        self.assertEqual(len(set(seen)), 450, "paging must not repeat or drop a record")

    def test_cursor_is_rejected_after_a_reimport(self):
        store = self.store({"entries": synthetic(200), "snapshot_id": "s", "fetched_at": "2026-09-10T00:00:00Z"})
        cursor = store.search(limit=10)["next_cursor"]
        self.assertTrue(cursor)
        store.close()
        rebuilt = self.store({"entries": synthetic(200), "snapshot_id": "s2", "fetched_at": "2026-09-10T00:00:01Z"})
        with self.assertRaises(CatalogStoreError):
            rebuilt.search(cursor=cursor)
        for invalid in ["nonsense", "1.2.3", "-1.0", "9" * 40]:
            with self.subTest(cursor=invalid):
                with self.assertRaises(CatalogStoreError):
                    rebuilt.search(cursor=invalid)

    def test_limits_and_deep_paging_stay_bounded(self):
        store = self.store()
        for invalid in [0, -1, MAX_PAGE_SIZE + 1, "many", None]:
            with self.subTest(limit=invalid):
                with self.assertRaises(CatalogStoreError):
                    store.search(limit=invalid)
        generation = store.meta()["generation"]
        with self.assertRaises(CatalogStoreError):
            store.search(cursor=f"{generation}.{MAX_OFFSET + 1}")

    def test_provenance_is_carried_through_and_never_upgraded(self):
        snapshot = seed_snapshot()
        store = self.store(snapshot)
        provenance = store.meta()["provenance"]
        self.assertEqual(provenance, snapshot["provenance"])
        self.assertEqual(provenance["signature_status"], "unsigned_development_seed")
        # Every search answer repeats the provenance it was built from.
        self.assertEqual(store.search()["provenance"], snapshot["provenance"])

    def test_import_is_atomic_and_leaves_the_previous_store_intact(self):
        self.store()
        before = self.path.read_bytes()

        class Exploding(dict):
            def get(self, key, default=None):
                if key == "package_entries":
                    raise RuntimeError("snapshot read failed")
                return super().get(key, default)

        with self.assertRaises(RuntimeError):
            build(self.path, Exploding({"entries": synthetic(5)}))
        self.assertEqual(self.path.read_bytes(), before, "a failed import must not damage the current store")
        self.assertEqual(len(list(self.path.parent.glob(".catalog-*"))), 0, "no temporary store may be left behind")

    def test_store_is_opened_read_only(self):
        store = self.store()
        store.search()
        connection = store._open()
        with self.assertRaises(sqlite3.OperationalError):
            connection.execute("DELETE FROM artifacts")

    def test_missing_or_foreign_store_reports_a_reason_instead_of_crashing(self):
        absent = CatalogStore(self.root / "nothing.sqlite3")
        self.assertFalse(absent.available)
        self.assertFalse(absent.status()["available"])
        self.assertIn("embedded snapshot", absent.status()["reason"])
        with self.assertRaises(CatalogStoreError):
            absent.search()

        foreign = self.root / "foreign.sqlite3"
        connection = sqlite3.connect(str(foreign))
        connection.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        connection.execute("INSERT INTO meta VALUES ('schema_version', '99')")
        connection.commit()
        connection.close()
        store = CatalogStore(foreign)
        self.addCleanup(store.close)
        self.assertFalse(store.status()["available"])
        self.assertIn("re-import", store.status()["reason"])

    def test_connections_from_other_threads_are_released_so_reimport_can_replace_the_file(self):
        """The sidecar serves on a thread pool; a leaked handle blocks re-import."""
        store = self.store()
        failures = []

        def read():
            try:
                store.search(query="agent")
            except Exception as error:  # noqa: BLE001 - recorded and asserted below
                failures.append(error)

        threads = [threading.Thread(target=read) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(failures, [], "each thread must read on its own connection")
        self.assertGreater(len(store._connections), 1)

        store.close()
        self.assertEqual(store._connections, [])
        # The real assertion: with every handle released the store file can be
        # atomically replaced, which is what a re-import does.
        build(self.path, {"entries": synthetic(3), "snapshot_id": "again", "fetched_at": "2026-09-10T00:00:00Z"})
        reopened = CatalogStore(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.meta()["snapshot_id"], "again")

    def test_scale_stays_bounded_at_fork_network_size(self):
        entries = synthetic(12_000)
        result = build(self.path, {"entries": entries, "snapshot_id": "scale", "fetched_at": "2026-09-10T00:00:00Z"})
        self.assertEqual(result["artifact_count"], 12_000)
        store = CatalogStore(self.path)
        self.addCleanup(store.close)

        browsed = store.search(sort="stars", limit=MAX_PAGE_SIZE)
        self.assertEqual(browsed["total"], 12_000)
        self.assertEqual(len(browsed["artifacts"]), MAX_PAGE_SIZE)
        searched = store.search(query="synthetic", limit=10)
        self.assertEqual(searched["total"], 12_000)
        self.assertEqual(len(searched["artifacts"]), 10)
        # A page stays small regardless of corpus size, so responses stay bounded.
        self.assertLess(len(json.dumps(searched["artifacts"])), 200_000)


@unittest.skipUnless(shutil.which("openssl"), "openssl is required to sign catalog snapshots")
class SignedSnapshotTests(unittest.TestCase):
    """A signed envelope is the only thing that may raise recorded trust."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.private = self.root / "private.pem"
        self.public = self.root / "public.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", self.private],
                       check=True, capture_output=True)
        self.private.chmod(0o600)
        subprocess.run(["openssl", "pkey", "-in", self.private, "-pubout", "-out", self.public],
                       check=True, capture_output=True)
        self.trust_root = create_trust_root(self.public, "registry-root", "2099-01-01T00:00:00Z")
        self.snapshot = {"entries": synthetic(4), "snapshot_id": "signed", "fetched_at": "2026-09-10T00:00:00Z"}
        self.launcher = Launcher(state_root=self.root / "state", sandbox=FakeCellSandbox())
        self.addCleanup(self.launcher.shutdown)

    def other_root(self):
        private = self.root / "other.pem"
        public = self.root / "other-public.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519", "-out", private],
                       check=True, capture_output=True)
        private.chmod(0o600)
        subprocess.run(["openssl", "pkey", "-in", private, "-pubout", "-out", public],
                       check=True, capture_output=True)
        return create_trust_root(public, "other-root", "2099-01-01T00:00:00Z")

    def test_signed_snapshot_round_trips_and_records_its_signers(self):
        envelope = sign_snapshot(self.snapshot, self.private)
        self.assertEqual(envelope["payloadType"], CATALOG_PAYLOAD_TYPE)

        result = self.launcher.import_catalog(envelope=envelope, trust_root=self.trust_root)
        signature = result["signature"]
        self.assertTrue(signature["verified"])
        self.assertEqual(signature["threshold"], 1)
        self.assertEqual(len(signature["valid_signers"]), 1)
        self.assertTrue(signature["payload_digest"].startswith("sha256:"))
        # Every search answer repeats how the corpus it read was trusted.
        self.assertEqual(self.launcher.catalog_search()["signature"]["verified"], True)

    def test_an_unsigned_import_is_recorded_as_unverified_rather_than_trusted(self):
        result = self.launcher.import_catalog(self.snapshot)
        self.assertEqual(result["signature"], {"verified": False})
        self.assertFalse(self.launcher.catalog_search()["signature"]["verified"])

    def test_tampering_with_a_signed_payload_is_refused(self):
        envelope = sign_snapshot(self.snapshot, self.private)
        payload = json.loads(base64.b64decode(envelope["payload"]))
        payload["entries"][0]["github_stars"] = 999_999
        tampered = {**envelope, "payload": base64.b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).decode()}
        with self.assertRaises(LauncherError):
            self.launcher.import_catalog(envelope=tampered, trust_root=self.trust_root)
        # A refused import must not leave a store behind.
        self.assertFalse(self.launcher.catalog_store.available)

    def test_an_untrusted_signer_expired_root_or_wrong_payload_type_is_refused(self):
        envelope = sign_snapshot(self.snapshot, self.private)
        with self.assertRaises(CatalogStoreError):
            verify_snapshot(envelope, self.other_root())

        expired = create_trust_root(self.public, "expired-root", "2000-01-01T00:00:00Z")
        with self.assertRaises(CatalogStoreError):
            verify_snapshot(envelope, expired)

        # A package envelope must not be accepted as a catalog snapshot.
        with self.assertRaises(CatalogStoreError):
            verify_snapshot({**envelope, "payloadType": "application/vnd.dsh-forge.package.v1+json"}, self.trust_root)

    def test_a_trust_root_is_required_and_only_applies_to_an_envelope(self):
        envelope = sign_snapshot(self.snapshot, self.private)
        with self.assertRaises(LauncherError):
            self.launcher.import_catalog(envelope=envelope)
        with self.assertRaises(LauncherError):
            self.launcher.import_catalog(self.snapshot, trust_root=self.trust_root)
        with self.assertRaises(LauncherError):
            self.launcher.import_catalog()

    def test_canonical_form_is_stable_and_rejects_ambiguous_numbers(self):
        # Key order must not change the signed bytes.
        self.assertEqual(
            canonical_snapshot_bytes({"a": 1, "b": [2, 3]}),
            canonical_snapshot_bytes({"b": [2, 3], "a": 1}),
        )
        # Integers are allowed because they have one spelling; floats do not.
        canonical_snapshot_bytes({"stars": 142, "archived": False, "name": None})
        with self.assertRaises(CatalogStoreError):
            canonical_snapshot_bytes({"score": 1.5})
        with self.assertRaises(CatalogStoreError):
            canonical_snapshot_bytes({"nested": {"deep": [1, 2.5]}})

    def test_a_noncanonical_but_correctly_signed_payload_is_refused(self):
        # Signed over bytes that are valid JSON but not the canonical spelling.
        from dsh_forge.packages import sign_payload

        noncanonical = json.dumps(self.snapshot, indent=2).encode()
        envelope = sign_payload(noncanonical, self.private, payload_type=CATALOG_PAYLOAD_TYPE)
        with self.assertRaises(CatalogStoreError) as context:
            verify_snapshot(envelope, self.trust_root)
        self.assertIn("canonical", str(context.exception))


class CatalogCliTests(unittest.TestCase):
    """The catalog is reachable from the terminal, not only the browser."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.launcher = Launcher(state_root=self.root / "state", sandbox=FakeCellSandbox())
        self.addCleanup(self.launcher.shutdown)

    def invoke(self, *arguments):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = cli.run(["--json", *arguments], launcher_factory=lambda **_options: self.launcher)
        payload = json.loads(stdout.getvalue() or stderr.getvalue())
        return code, payload.get("data", payload)

    def test_status_import_and_search_round_trip_through_the_cli(self):
        code, status = self.invoke("catalog", "status")
        self.assertEqual(code, 0)
        self.assertFalse(status["available"])

        snapshot = ROOT / "data/public-repos.seed.json"
        feed = ROOT / "data/package-catalog.seed.json"
        code, imported = self.invoke("catalog", "import", str(snapshot), "--package-feed", str(feed))
        self.assertEqual(code, 0)
        self.assertEqual(imported["artifact_count"], 20)
        # Importing reports the trust it was given, never an upgraded one.
        self.assertEqual(imported["provenance"]["signature_status"], "unsigned_development_seed")

        code, found = self.invoke("catalog", "search", "agent teams", "--limit", "3")
        self.assertEqual(code, 0)
        slugs = {item.get("full_name") or item.get("slug") for item in found["artifacts"]}
        self.assertIn("NanmiCoder/dsh-agent-teams", slugs)

        code, gems = self.invoke("research", "gems", "memory", "--limit", "3")
        self.assertEqual(code, 0)
        self.assertEqual(gems["policy"], "dsh-forge.hidden-gems/v1")
        self.assertTrue(gems["candidates"])
        self.assertTrue(all(item["hidden_gem"]["candidate"] for item in gems["candidates"]))

        code, forks = self.invoke("catalog", "search", "--type", "fork", "--sort", "stars", "--limit", "2")
        self.assertEqual(code, 0)
        self.assertEqual(len(forks["artifacts"]), 2)
        self.assertTrue(forks["next_cursor"])

        code, page = self.invoke(
            "catalog", "search", "--type", "fork", "--sort", "stars", "--limit", "2",
            "--cursor", forks["next_cursor"],
        )
        self.assertEqual(code, 0)
        first = {item["artifact_id"] for item in forks["artifacts"]}
        self.assertFalse(first & {item["artifact_id"] for item in page["artifacts"]})

    def test_searching_without_an_imported_store_fails_closed(self):
        code, payload = self.invoke("catalog", "search", "anything")
        self.assertNotEqual(code, 0)
        self.assertIn("catalog store", json.dumps(payload).lower())


if __name__ == "__main__":
    unittest.main()
