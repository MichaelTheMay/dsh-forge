import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from dsh_forge.catalog import (
    CatalogError,
    build_feed,
    directory_leads,
    validate_feed,
    validate_sources,
)


ROOT = Path(__file__).resolve().parents[1]


class PackageCatalogTests(unittest.TestCase):
    def setUp(self):
        self.sources = json.loads((ROOT / "data/package-catalog.sources.json").read_text(encoding="utf-8"))
        self.plugins = json.loads((ROOT / "data/public-repos.seed.json").read_text(encoding="utf-8"))
        self.feed = json.loads((ROOT / "data/package-catalog.seed.json").read_text(encoding="utf-8"))

    def test_committed_feed_is_deterministic(self):
        self.assertEqual(build_feed(self.sources, self.plugins), self.feed)
        validate_feed(self.feed)

    def test_ingester_check_mode_accepts_committed_output(self):
        result = subprocess.run(
            [sys.executable, "scripts/ingest_package_catalog.py", "--check"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No network or code execution", result.stdout)

    def test_every_package_has_a_stable_dedicated_route(self):
        self.assertEqual(
            [item["page"]["route"] for item in self.feed["packages"]],
            ["#packages/agent-teams-builder", "#packages/code-review-lab", "#packages/auditable-memory-lab"],
        )

    def test_catalog_cannot_claim_install_or_execution(self):
        changed = copy.deepcopy(self.feed)
        changed["packages"][0]["verification"]["installed"] = True
        with self.assertRaisesRegex(CatalogError, "cannot claim"):
            validate_feed(changed)

    def test_catalog_acquisition_requires_signed_dsse(self):
        changed = copy.deepcopy(self.feed)
        changed["packages"][0]["acquisition"]["enabled"] = True
        with self.assertRaisesRegex(CatalogError, "fail-closed"):
            validate_feed(changed)

    def test_feed_rejects_unknown_nested_fields(self):
        changed = copy.deepcopy(self.feed)
        changed["packages"][0]["acquisition"]["install_url"] = "https://example.test/install"
        with self.assertRaisesRegex(CatalogError, "fields disagree"):
            validate_feed(changed)

    def test_feed_rejects_floating_host_compatibility(self):
        changed = copy.deepcopy(self.feed)
        changed["packages"][0]["compatibility"]["harness_versions"] = ["latest"]
        with self.assertRaisesRegex(CatalogError, "exact semantic versions"):
            validate_feed(changed)

    def test_directory_claim_cannot_be_promoted_to_verification(self):
        changed = copy.deepcopy(self.feed)
        changed["packages"][0]["provenance"]["claims_verified"] = True
        with self.assertRaisesRegex(CatalogError, "not verification"):
            validate_feed(changed)

    def test_unknown_component_is_rejected(self):
        changed = copy.deepcopy(self.sources)
        changed["recipes"][0]["components"][0]["artifact_id"] = "github:999999999999"
        with self.assertRaisesRegex(CatalogError, "Unknown package component"):
            build_feed(changed, self.plugins)

    def test_floating_or_unpinned_component_is_rejected(self):
        changed = copy.deepcopy(self.plugins)
        changed["supplemental_entries"][0]["package"]["version"] = "latest"
        with self.assertRaisesRegex(CatalogError, "exact version"):
            build_feed(self.sources, changed)
        changed = copy.deepcopy(self.plugins)
        changed["supplemental_entries"][0]["head_sha"] = "main"
        with self.assertRaisesRegex(CatalogError, "immutable repository commit"):
            build_feed(self.sources, changed)

    def test_directory_adapter_is_bounded_and_drops_install_commands(self):
        payload = {
            "plugins": [
                {
                    "url": "https://github.com/NanmiCoder/dsh-agent-teams",
                    "npm": "@nanmicoder/dsh-agent-teams",
                    "install": "dsh plugin --profile web add @nanmicoder/dsh-agent-teams",
                    "verification": "verified",
                },
                {"url": "javascript:alert(1)", "npm": "bad"},
            ]
        }
        self.assertEqual(directory_leads(payload, source_id="dsh-get"), [{
            "source_id": "dsh-get",
            "repository": "NanmiCoder/dsh-agent-teams",
            "package_name": "@nanmicoder/dsh-agent-teams",
        }])
        with self.assertRaisesRegex(CatalogError, "at most 1"):
            directory_leads(payload, source_id="dsh-get", max_entries=1)

    def test_sources_reject_unknown_fields_and_unbounded_rank_gaps(self):
        changed = copy.deepcopy(self.sources)
        changed["unexpected"] = True
        with self.assertRaisesRegex(CatalogError, "fields disagree"):
            validate_sources(changed)
        changed = copy.deepcopy(self.sources)
        changed["recipes"][2]["rank"] = 9
        with self.assertRaisesRegex(CatalogError, "contiguous"):
            validate_sources(changed)


if __name__ == "__main__":
    unittest.main()
