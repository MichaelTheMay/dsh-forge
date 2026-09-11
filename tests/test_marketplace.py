import io
import json
from pathlib import Path
import tempfile
import unittest

from dsh_forge.catalog_store import CatalogStore, build
from dsh_forge.marketplace import MarketplaceError, catalog_digest, fetch_catalog, normalize_catalog


def sample_catalog():
    catalog = {
        "schemaVersion": 1,
        "generatedAt": "2026-09-10T08:07:32.097Z",
        "scannerVersion": "1.2.3",
        "topic": "dsh-plugin",
        "integrity": {"algorithm": "sha256", "digest": ""},
        "summary": {"entryCount": 1, "invalidEntryCount": 0, "packCount": 0},
        "entries": [{
            "repositoryId": "1339316901",
            "repository": {
                "fullName": "example/dsh-memory",
                "url": "https://github.com/example/dsh-memory",
                "defaultBranch": "main",
                "commitSha": "38fd7649bb44d500ce1760db8707ebe2ec4ad848",
                "archived": False,
            },
            "package": {
                "name": "@example/dsh-memory",
                "version": "0.5.2",
                "description": "Persistent project memory with cited retrieval.",
                "author": "example",
                "license": "MIT",
            },
            "topics": ["dsh-plugin", "memory"],
            "keywords": ["retrieval"],
            "stars": 2,
            "repositoryCreatedAt": "2026-08-19T08:40:32Z",
            "lastCodePushAt": "2026-09-09T14:56:15Z",
            "firstSeenAt": "2026-08-20T03:58:38.838Z",
            "indexedAt": "2026-09-10T08:07:32.097Z",
            "source": {
                "kind": "git",
                "ref": "git+https://github.com/example/dsh-memory.git#38fd7649bb44d500ce1760db8707ebe2ec4ad848",
                "packageJsonPath": "package.json",
                "patchPath": "cordis.patch.yml",
            },
            "validation": {"status": "valid", "code": "valid-bundle", "message": None},
            "compatibility": "unknown",
            "installability": "one-click-eligible",
            "riskSignals": ["git-source"],
        }],
        "packs": [],
        "ratings": None,
    }
    catalog["integrity"]["digest"] = catalog_digest(catalog)
    return catalog


class Response(io.BytesIO):
    def __init__(self, payload, url="https://catalog.example/plugins.json", content_length=None):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload)) if content_length is None else content_length}
        self._url = url

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class MarketplaceTests(unittest.TestCase):
    def test_normalizes_verified_catalog_into_searchable_plugin_rows(self):
        snapshot = normalize_catalog(sample_catalog(), "https://catalog.example/plugins.json")
        plugin = snapshot["supplemental_entries"][0]
        self.assertEqual(plugin["artifact_id"], "github:1339316901")
        self.assertEqual(plugin["artifact_type"], "plugin")
        self.assertEqual(plugin["installability"], "one-click-eligible")
        self.assertFalse(plugin["verification"]["security_verified"])
        self.assertEqual(snapshot["provenance"]["signature_status"], "unsigned_external_catalog")

        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "catalog.sqlite3"
            build(path, snapshot)
            store = CatalogStore(path)
            result = store.search(query="persistent memory", types=["plugin"])
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["artifacts"][0]["full_name"], "example/dsh-memory")
            store.close()

    def test_rejects_tampering_after_upstream_digest(self):
        catalog = sample_catalog()
        catalog["entries"][0]["package"]["description"] = "tampered"
        with self.assertRaisesRegex(MarketplaceError, "integrity digest"):
            normalize_catalog(catalog, "https://catalog.example/plugins.json")

    def test_fetch_requires_https_and_rechecks_redirect(self):
        with self.assertRaisesRegex(MarketplaceError, "credential-free HTTPS"):
            fetch_catalog("http://catalog.example/plugins.json")

        payload = json.dumps(sample_catalog(), ensure_ascii=False, separators=(",", ":")).encode()
        with self.assertRaisesRegex(MarketplaceError, "redirect"):
            fetch_catalog(
                "https://catalog.example/plugins.json",
                opener=lambda *_args, **_kwargs: Response(payload, "http://catalog.example/plugins.json"),
            )

    def test_fetch_returns_normalized_catalog(self):
        payload = json.dumps(sample_catalog(), ensure_ascii=False, separators=(",", ":")).encode()
        snapshot = fetch_catalog(
            "https://catalog.example/plugins.json",
            opener=lambda *_args, **_kwargs: Response(payload),
        )
        self.assertEqual(len(snapshot["supplemental_entries"]), 1)

    def test_fetch_rejects_invalid_content_length(self):
        with self.assertRaisesRegex(MarketplaceError, "Content-Length"):
            fetch_catalog(
                "https://catalog.example/plugins.json",
                opener=lambda *_args, **_kwargs: Response(b"{}", content_length="many"),
            )


if __name__ == "__main__":
    unittest.main()
