import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowPolicyTests(unittest.TestCase):
    def test_node_setup_action_uses_node24_runtime(self):
        revision = "actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0"
        for name in ("checks.yml", "release.yml"):
            workflow = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn(revision, workflow)

    def test_ci_covers_integration_and_release_branches(self):
        workflow = (ROOT / ".github/workflows/checks.yml").read_text(encoding="utf-8")
        self.assertRegex(workflow, r"pull_request:\s*\n\s*branches: \[development, main\]")
        self.assertRegex(workflow, r"push:\s*\n\s*branches: \[development, main\]")
        self.assertIn("python3 -m compileall", workflow)
        self.assertIn("node --test tests/catalog.test.cjs", workflow)
        self.assertIn("python3 -m unittest discover", workflow)

    def test_release_is_tagged_tested_and_main_only(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        self.assertRegex(workflow, r"tags:\s*\n\s*- 'v\*'")
        self.assertIn('test "$(git rev-list -n 1 "$GITHUB_SHA")" = "$(git rev-parse origin/main)"', workflow)
        self.assertNotIn('git merge-base --is-ancestor "$GITHUB_SHA" origin/main', workflow)
        self.assertIn("gh release create", workflow)
        self.assertRegex(workflow, r"permissions:\s*\n\s*contents: write")

    def test_pull_request_template_targets_main(self):
        template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
        self.assertIn("targets the protected `main` branch", template)
        self.assertNotIn("`development` to `main`", template)

    def test_catalog_research_indexes_plugins_and_forks_before_ranking(self):
        workflow = (ROOT / ".github/workflows/catalog-research.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/index_registry.py", workflow)
        self.assertIn("scripts/analyze_registry.py", workflow)
        self.assertIn("scripts/build_catalog_feed.py", workflow)
        self.assertIn("--snapshot dist/registry-raw.json", workflow)
        self.assertIn("--snapshot dist/registry.json", workflow)
        self.assertIn("GITHUB_TOKEN: ${{ github.token }}", workflow)
        self.assertIn("dist/registry.json", workflow)
        self.assertIn("github.ref == 'refs/heads/main'", workflow)
        self.assertIn("gh release upload catalog-latest", workflow)
        self.assertIn("actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1", workflow)
        self.assertRegex(workflow, r"permissions:\s*\n\s*contents: read")
        self.assertRegex(workflow, r"permissions:\s*\n\s*contents: write")


if __name__ == "__main__":
    unittest.main()
