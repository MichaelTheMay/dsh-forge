import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkflowPolicyTests(unittest.TestCase):
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
        self.assertIn('git merge-base --is-ancestor "$GITHUB_SHA" origin/main', workflow)
        self.assertIn("gh release create", workflow)
        self.assertRegex(workflow, r"permissions:\s*\n\s*contents: write")

    def test_pull_request_template_prefers_development(self):
        template = (ROOT / ".github/pull_request_template.md").read_text(encoding="utf-8")
        self.assertIn("targets `development`", template)
        self.assertIn("`development` to `main`", template)


if __name__ == "__main__":
    unittest.main()
