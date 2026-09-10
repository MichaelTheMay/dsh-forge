import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

from dsh_forge.installation import InstallationError
from dsh_forge.launcher import Launcher, LauncherError
from dsh_forge.packages import compose, create_trust_root, sign
from tests.helpers import FakeCellSandbox
from tests.test_packages import package_spec


class PackageInstallTransactionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.managed = self.root / "versions"
        self.managed.mkdir()
        self.environment = mock.patch.dict(os.environ, {"DSH_FORGE_VERSIONS_DIR": str(self.managed)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.tree = self.managed / "dsh"
        self.tree.mkdir()
        (self.tree / "package.json").write_text(
            json.dumps({"name": "@deepseek-ai/dsh", "version": "0.1.2-rc.1"}),
            encoding="utf-8",
        )
        executable = self.tree / "dsh"
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o700)
        self.state = self.root / "state"
        self.launcher = Launcher([self.tree], state_root=self.state, sandbox=FakeCellSandbox())
        self.launcher.add_scan_roots([str(self.tree)])
        self.version_id = self.launcher.status()["saved_versions"][0]["id"]

        self.private = self.root / "private.pem"
        self.public = self.root / "public.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "Ed25519", "-out", self.private],
            check=True,
            capture_output=True,
        )
        self.private.chmod(0o600)
        subprocess.run(
            ["openssl", "pkey", "-in", self.private, "-pubout", "-out", self.public],
            check=True,
            capture_output=True,
        )
        spec = package_spec()
        spec["package"]["id"] = "agent-teams-builder"
        self.envelope = sign(compose(spec), self.private)
        self.trust_root = create_trust_root(
            self.public,
            "transaction.tests",
            "2099-01-01T00:00:00Z",
        )

    def tearDown(self):
        self.launcher.shutdown()
        self.temp.cleanup()

    def test_successful_transaction_is_persistent_and_ready(self):
        with mock.patch("dsh_forge.acquisition.acquire", return_value={"receipt": str(self.root / "receipt.json")}), mock.patch(
            "dsh_forge.installation.install_in_sandbox"
        ) as installer:
            installer.side_effect = lambda *_args, **kwargs: {
                "receipt": str(self.root / "install-receipt.json"),
                "home": str(self.root / "promoted-home"),
                "rollback_install_id": None,
                "install_id": kwargs["transaction_id"],
            }
            result = self.launcher.install_package(
                version_id=self.version_id,
                envelope=self.envelope,
                trust_root=self.trust_root,
            )
        self.assertEqual(result["state"], "ready")
        self.assertTrue(result["rollback_preserved"])
        recovered = Launcher([self.tree], state_root=self.state, sandbox=FakeCellSandbox())
        try:
            self.assertEqual(recovered.status()["package_installations"][-1]["id"], result["id"])
        finally:
            recovered.shutdown()

    def test_failed_transaction_records_readable_error_and_rollback(self):
        with mock.patch("dsh_forge.acquisition.acquire", return_value={"receipt": str(self.root / "receipt.json")}), mock.patch(
            "dsh_forge.installation.install_in_sandbox",
            side_effect=InstallationError("unsafe archive entry", "unsafe_archive"),
        ):
            with self.assertRaisesRegex(LauncherError, "unsafe archive"):
                self.launcher.install_package(
                    version_id=self.version_id,
                    envelope=self.envelope,
                    trust_root=self.trust_root,
                )
        record = self.launcher.status()["package_installations"][-1]
        self.assertEqual(record["state"], "failed")
        self.assertEqual(record["error"]["code"], "unsafe_archive")
        self.assertTrue(record["rollback_preserved"])

    def test_unsaved_version_cannot_start_a_transaction(self):
        with self.assertRaisesRegex(LauncherError, "not found"):
            self.launcher.install_package(
                version_id="version_000000000000",
                envelope=self.envelope,
                trust_root=self.trust_root,
            )
        self.assertEqual(self.launcher.status()["package_installations"], [])

    def test_catalog_recipe_resolves_only_fixed_local_inputs_and_matching_identity(self):
        recipe = self.launcher.trusted_package_recipes_root / "agent-teams-builder"
        recipe.mkdir()
        (recipe / "envelope.json").write_text(json.dumps(self.envelope), encoding="utf-8")
        (recipe / "trust-root.json").write_text(json.dumps(self.trust_root), encoding="utf-8")
        with mock.patch.object(self.launcher, "install_package", return_value={"state": "ready"}) as install:
            result = self.launcher.install_trusted_catalog_package(
                package_slug="agent-teams-builder",
                version_id=self.version_id,
            )
        self.assertEqual(result["state"], "ready")
        self.assertEqual(install.call_args.kwargs["version_id"], self.version_id)
        self.assertEqual(self.launcher.trusted_package_recipes(), [
            {"slug": "agent-teams-builder", "configured": True, "verified_at_install": True}
        ])


if __name__ == "__main__":
    unittest.main()
