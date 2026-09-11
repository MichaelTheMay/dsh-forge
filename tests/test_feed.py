import io
import json
from pathlib import Path
import tempfile
import unittest

from dsh_forge.catalog import FEED_SCHEMA as PACKAGE_FEED_SCHEMA
from dsh_forge.feed import REGISTRY_FEED_SCHEMA, FeedError, build_feed_assets, fetch_catalog_feed
from dsh_forge.packages import write_json


class Response(io.BytesIO):
    def __init__(self, payload, url):
        super().__init__(payload)
        self._url = url
        self.headers = {"Content-Length": str(len(payload))}

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class SequenceOpener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.urls = []

    def __call__(self, request, **_kwargs):
        self.urls.append(request.full_url)
        payload, final_url = next(self.responses)
        return Response(payload, final_url)


def registry():
    return {
        "schema_version": 1,
        "snapshot_id": "registry-feed-test",
        "fetched_at": "2026-09-11T18:00:00Z",
        "completed_at": "2026-09-11T18:01:00Z",
        "provenance": {"method": "test"},
        "coverage": [{"source": "test", "status": "complete"}],
        "entries": [{"artifact_id": "github:1", "artifact_type": "fork"}],
        "supplemental_entries": [{"artifact_id": "github:2", "artifact_type": "plugin"}],
        "package_entries": [],
    }


def queue():
    return {
        "schema": "dsh-forge.discovery-queue/v2",
        "policy": "dsh-forge.hidden-gems/v2",
        "snapshot_id": "registry-feed-test",
        "candidate_count": 1,
        "candidates": [{}],
        "quality": {"selection_policy": "dsh-forge.discovery-diversity/v1"},
    }


class FeedTests(unittest.TestCase):
    def test_registry_transport_does_not_reuse_the_package_feed_schema(self):
        self.assertEqual(REGISTRY_FEED_SCHEMA, "dsh-forge.registry-feed/v1")
        self.assertNotEqual(REGISTRY_FEED_SCHEMA, PACKAGE_FEED_SCHEMA)

    def build(self, root):
        root = Path(root)
        registry_path = root / "registry.json"
        queue_path = root / "hidden-gems.json"
        write_json(registry_path, registry(), compact=True)
        write_json(queue_path, queue(), compact=True)
        return build_feed_assets(
            registry_path,
            queue_path,
            root / "feed",
            base_url="https://github.com/MichaelTheMay/dsh-forge/releases/download/catalog-latest",
        )

    def test_feed_assets_are_deterministic_bounded_and_checksum_verified(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.build(root)
            feed_path = Path(first["paths"]["feed"])
            registry_gzip = Path(first["paths"]["registry"]).read_bytes()
            feed_bytes = feed_path.read_bytes()
            feed = first["feed"]
            self.assertEqual(feed["counts"], {"plugins": 1, "forks": 1, "packages": 0, "candidates": 1})
            self.assertFalse(feed["claims"]["signed"])
            self.assertFalse(feed["claims"]["executed"])

            opener = SequenceOpener([
                (feed_bytes, "https://objects.githubusercontent.com/feed"),
                (registry_gzip, "https://release-assets.githubusercontent.com/registry"),
            ])
            snapshot = fetch_catalog_feed(opener=opener)
            self.assertEqual(snapshot["snapshot_id"], "registry-feed-test")
            self.assertEqual(snapshot["provenance"]["feed"]["signature_status"], "unsigned_checksum_verified")
            self.assertEqual(opener.urls[1], feed["assets"]["registry"]["url"])

            second_root = Path(root) / "second"
            second_root.mkdir()
            second = self.build(second_root)
            self.assertEqual(
                Path(second["paths"]["registry"]).read_bytes(),
                registry_gzip,
            )

    def test_feed_rejects_tampered_registry_before_json_import(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.build(root)
            feed_bytes = Path(result["paths"]["feed"]).read_bytes()
            compressed = bytearray(Path(result["paths"]["registry"]).read_bytes())
            compressed[-1] ^= 1
            opener = SequenceOpener([
                (feed_bytes, "https://objects.githubusercontent.com/feed"),
                (bytes(compressed), "https://release-assets.githubusercontent.com/registry"),
            ])
            with self.assertRaisesRegex(FeedError, "compressed checksum"):
                fetch_catalog_feed(opener=opener)

    def test_feed_rejects_cross_snapshot_publication(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            registry_path = root / "registry.json"
            queue_path = root / "hidden-gems.json"
            write_json(registry_path, registry(), compact=True)
            value = queue()
            value["snapshot_id"] = "wrong"
            write_json(queue_path, value, compact=True)
            with self.assertRaisesRegex(FeedError, "snapshot IDs differ"):
                build_feed_assets(
                    registry_path,
                    queue_path,
                    root / "feed",
                    base_url="https://example.com/catalog",
                )


if __name__ == "__main__":
    unittest.main()
