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
        self.assertIn("packaging/windows/build.ps1", workflow)
        self.assertIn("WINDOWS_SIGNING_CERTIFICATE_BASE64", workflow)
        self.assertIn("-CertificateThumbprint", workflow)
        self.assertIn("packaging/windows/smoke.ps1", workflow)
        self.assertIn("1.3.6.1.5.5.7.3.3", workflow)
        self.assertIn("actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1", workflow)
        self.assertIn("actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c # v8.0.1", workflow)
        self.assertRegex(workflow, r"permissions:\s*\n\s*contents: write")

    def test_windows_package_has_stable_upgrade_identity_and_no_electron(self):
        installer = (ROOT / "packaging/windows/DSHForge.iss").read_text(encoding="utf-8")
        spec = (ROOT / "packaging/windows/DSHForge.spec").read_text(encoding="utf-8")
        build = (ROOT / "packaging/windows/build.ps1").read_text(encoding="utf-8")
        smoke = (ROOT / "packaging/windows/smoke.ps1").read_text(encoding="utf-8")
        self.assertIn("AppId={{D70F4E6D-1B17-4BD5-964A-A2267F68B85F}", installer)
        self.assertIn("DefaultDirName={localappdata}\\Programs\\DSH Forge", installer)
        self.assertIn("AppUpdatesURL=https://github.com/MichaelTheMay/dsh-forge/releases/latest", installer)
        self.assertIn('name="DSH Forge"', spec)
        self.assertIn('icon=str(icon)', spec)
        self.assertIn("web", spec)
        self.assertIn("data", spec)
        self.assertIn("signtool", build.lower())
        self.assertIn("New-ForgeIcon", build)
        self.assertNotIn("electron", spec.lower())
        self.assertIn("Invoke-RestMethod", smoke)
        self.assertIn("unins000.exe", smoke)

    def test_macos_release_is_dual_architecture_signed_notarized_and_smoke_tested(self):
        workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
        build = (ROOT / "packaging/macos/build.sh").read_text(encoding="utf-8")
        smoke = (ROOT / "packaging/macos/smoke.sh").read_text(encoding="utf-8")
        entitlements = (ROOT / "packaging/macos/entitlements.plist").read_text(encoding="utf-8")
        self.assertIn("macos-15", workflow)
        self.assertIn("macos-15-intel", workflow)
        self.assertIn("arch: arm64", workflow)
        self.assertIn("arch: x86_64", workflow)
        self.assertIn("MACOS_SIGNING_CERTIFICATE_BASE64", workflow)
        self.assertIn("MACOS_NOTARY_PASSWORD", workflow)
        self.assertIn("needs: [test, windows, macos]", workflow)
        self.assertIn("Developer ID Application", build)
        self.assertIn("--options runtime", build)
        self.assertIn("xcrun notarytool submit", build)
        self.assertIn("xcrun stapler validate", build)
        self.assertIn("CFBundleShortVersionString", build)
        self.assertIn("lipo -archs", build)
        self.assertIn("DSH Forge.app", smoke)
        self.assertIn("live-local-sidecar", smoke)
        self.assertIn("spctl --assess", smoke)
        self.assertNotIn("get-task-allow", entitlements)

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
