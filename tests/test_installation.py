import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

from dsh_forge.acquisition import acquire
from dsh_forge.installation import InstallationError, inspect_acquisition, install_in_sandbox
from dsh_forge.packages import compose, create_trust_root, sign
from dsh_forge.sandbox import ApptainerSandbox, SandboxConfig
from tests.test_packages import package_spec


def npm_tgz(
    name: str,
    version: str,
    *,
    symlink: bool = False,
    traversal: bool = False,
    lifecycle: bool = False,
    runtime_dependency: bool = False,
    binary: bool = False,
) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        package_json = json.dumps({
            "name": name,
            "version": version,
            "dependencies": {"kleur": "4.1.5"} if runtime_dependency else {},
            "peerDependencies": {"@deepseek-ai/dsh": "0.1.2-rc.1"},
            "scripts": {"postinstall": "node install.js"} if lifecycle else {"verify": "node verify.js"},
        }).encode()
        info = tarfile.TarInfo("package/package.json")
        info.size = len(package_json)
        archive.addfile(info, io.BytesIO(package_json))
        body = b"module.exports = {}\n"
        source_name = "../escape" if traversal else "package/index.js"
        source = tarfile.TarInfo(source_name)
        source.size = len(body)
        archive.addfile(source, io.BytesIO(body))
        if symlink:
            link = tarfile.TarInfo("package/link")
            link.type = tarfile.SYMTYPE
            link.linkname = "/etc/passwd"
            archive.addfile(link)
        if binary:
            native = tarfile.TarInfo("package/native.node")
            native.size = 4
            archive.addfile(native, io.BytesIO(b"ELF!"))
    return output.getvalue()


class RecordingProbeRunner:
    def __call__(self, command, **_options):
        return subprocess.CompletedProcess(command, 0, stdout="v22.19.0\n")


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
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
        spec["plugins"] = [spec["plugins"][0]]
        spec["load_order"] = [spec["plugins"][0]["id"]]
        plugin = spec["plugins"][0]
        self.payload = npm_tgz(plugin["source"]["name"], plugin["source"]["version"])
        plugin["source"]["integrity"] = "sha512-" + base64.b64encode(hashlib.sha512(self.payload).digest()).decode()
        self.manifest = compose(spec)
        self.envelope = sign(self.manifest, self.private)
        self.trust_root = create_trust_root(self.public, "test.release", "2099-01-01T00:00:00Z")
        self.quarantine = self.root / "quarantine"
        self.acquisition = acquire(
            self.envelope,
            self.trust_root,
            self.quarantine,
            downloader=self._downloader,
        )

    def tearDown(self):
        self.temp.cleanup()

    def _downloader(self, plugin, handle):
        handle.write(self.payload)
        return {
            "bytes": len(self.payload),
            "content_sha256": "sha256:" + hashlib.sha256(self.payload).hexdigest(),
            "original_url": plugin["source"]["url"],
            "final_url": plugin["source"]["url"],
            "redirect_chain": [],
        }

    @property
    def receipt(self):
        return self.acquisition["receipt"]

    def sandbox_and_tree(self):
        image = self.root / "node.sif"
        image.write_bytes(b"image")
        image.chmod(0o400)
        binary = self.root / "apptainer"
        binary.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        binary.chmod(0o700)
        sandbox = ApptainerSandbox(
            SandboxConfig.from_values(
                image=image,
                image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                binary=str(binary),
                cell_timeout_seconds=1200,
            ),
            self.root / "sandbox",
            runner=RecordingProbeRunner(),
        )
        tree = self.root / "dsh"
        tree.mkdir(exist_ok=True)
        executable = tree / "dsh.js"
        executable.write_text("#!/usr/bin/env node\n", encoding="utf-8")
        return sandbox, {
            "id": "tree_" + "a" * 12,
            "real_path": str(tree),
            "real_exe": str(executable),
            "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        }

    def test_reverification_and_bounded_archive_inspection_authorize_only_sandbox_install(self):
        result = inspect_acquisition(self.envelope, self.trust_root, self.receipt)
        self.assertTrue(result["sandbox_installation_authorized"])
        self.assertFalse(result["host_installation_authorized"])
        self.assertFalse(result["execution_authorized"])
        self.assertFalse(result["archives_extracted_on_host"])
        artifact = result["artifacts"][0]
        self.assertEqual(artifact["package_name"], "dsh-vet")
        self.assertEqual(artifact["lifecycle_scripts_declared"], [])
        self.assertFalse(artifact["lifecycle_scripts_allowed"])

    def test_receipt_or_content_address_tampering_fails_closed(self):
        receipt = json.loads(Path(self.receipt).read_text())
        receipt["payload_digest"] = "sha256:" + "0" * 64
        tampered_receipt = self.root / "tampered-receipt.json"
        tampered_receipt.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(InstallationError, "payload digest"):
            inspect_acquisition(self.envelope, self.trust_root, tampered_receipt)

        object_path = self.quarantine / self.acquisition["artifacts"][0]["object"]
        object_path.chmod(0o600)
        with self.assertRaisesRegex(InstallationError, "writable"):
            inspect_acquisition(self.envelope, self.trust_root, self.receipt)

    def test_traversal_symlink_and_identity_mismatch_are_rejected(self):
        for payload, pattern in (
            (npm_tgz("dsh-vet", "0.3.0", traversal=True), "confined"),
            (npm_tgz("dsh-vet", "0.3.0", symlink=True), "special entry"),
            (npm_tgz("other-package", "0.3.0"), "name/version"),
        ):
            spec = package_spec()
            spec["plugins"] = [spec["plugins"][0]]
            spec["load_order"] = [spec["plugins"][0]["id"]]
            spec["plugins"][0]["source"]["integrity"] = "sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode()
            envelope = sign(compose(spec), self.private)

            def downloader(plugin, handle, exact=payload):
                handle.write(exact)
                return {
                    "bytes": len(exact),
                    "content_sha256": "sha256:" + hashlib.sha256(exact).hexdigest(),
                    "original_url": plugin["source"]["url"],
                    "final_url": plugin["source"]["url"],
                    "redirect_chain": [],
                }

            quarantine = self.root / ("case-" + hashlib.sha256(payload).hexdigest()[:8])
            acquired = acquire(envelope, self.trust_root, quarantine, downloader=downloader)
            with self.assertRaisesRegex(InstallationError, pattern):
                inspect_acquisition(envelope, self.trust_root, acquired["receipt"])

    def test_lifecycle_runtime_dependency_and_binary_archives_are_rejected(self):
        for payload, pattern in (
            (npm_tgz("dsh-vet", "0.3.0", lifecycle=True), "lifecycle scripts"),
            (npm_tgz("dsh-vet", "0.3.0", runtime_dependency=True), "closed top-level"),
            (npm_tgz("dsh-vet", "0.3.0", binary=True), "binary artifact"),
        ):
            spec = package_spec()
            spec["plugins"] = [spec["plugins"][0]]
            spec["load_order"] = [spec["plugins"][0]["id"]]
            spec["plugins"][0]["source"]["integrity"] = "sha512-" + base64.b64encode(
                hashlib.sha512(payload).digest()
            ).decode()
            envelope = sign(compose(spec), self.private)

            def downloader(plugin, handle, exact=payload):
                handle.write(exact)
                return {
                    "bytes": len(exact),
                    "content_sha256": "sha256:" + hashlib.sha256(exact).hexdigest(),
                    "original_url": plugin["source"]["url"],
                    "final_url": plugin["source"]["url"],
                    "redirect_chain": [],
                }

            acquired = acquire(envelope, self.trust_root, self.root / ("reject-" + pattern.split()[0]), downloader=downloader)
            with self.assertRaisesRegex(InstallationError, pattern):
                inspect_acquisition(envelope, self.trust_root, acquired["receipt"])

    def test_disposable_install_uses_read_only_artifact_and_disables_scripts(self):
        sandbox, tree = self.sandbox_and_tree()
        calls = []

        def runner(command, **options):
            calls.append((command, options))
            if "--dump-config" in command:
                output = "dsh-vet@0.3.0\n"
            elif "web" in command:
                output = "dsh web: http://127.0.0.1:3189/?token=redacted\n"
            else:
                output = "installed\n"
            return subprocess.CompletedProcess(command, 0, stdout=output)

        result = install_in_sandbox(
            self.envelope,
            self.trust_root,
            self.receipt,
            tree=tree,
            sandbox=sandbox,
            install_root=self.root / "installs",
            runner=runner,
        )
        self.assertTrue(result["sandbox_installed"])
        self.assertTrue(result["composition_probe_passed"])
        self.assertTrue(result["web_smoke_passed"])
        self.assertTrue(result["atomically_promoted"])
        self.assertFalse(result["host_profile_modified"])
        self.assertFalse(result["dependency_resolution"]["runtime_dependencies_allowed"])
        install_command, install_options = calls[1]
        rendered = " ".join(install_command)
        self.assertIn("--ignore-scripts", rendered)
        self.assertIn("--offline", rendered)
        self.assertIn("dst=/quarantine/000-dsh-vet.tgz,ro", rendered)
        self.assertNotIn(str(Path.home()), rendered)
        self.assertNotIn("GH_TOKEN", install_options["env"])
        self.assertIn("--network none", " ".join(calls[1][0]))
        self.assertTrue(Path(result["receipt"]).is_file())
        current_path = self.root / "installs" / "profiles" / ("tree_" + "a" * 12) / "web" / "current.json"
        current = json.loads(current_path.read_text())
        self.assertEqual(current["install_id"], result["install_id"])

    def test_failed_replacement_preserves_current_profile_and_retains_evidence(self):
        sandbox, tree = self.sandbox_and_tree()

        def passing(command, **_options):
            if "--dump-config" in command:
                output = "dsh-vet@0.3.0\n"
            elif "web" in command:
                output = "dsh web: http://127.0.0.1:3189/?token=redacted\n"
            else:
                output = "installed\n"
            return subprocess.CompletedProcess(command, 0, stdout=output)

        install_root = self.root / "installs"
        first = install_in_sandbox(
            self.envelope, self.trust_root, self.receipt,
            tree=tree, sandbox=sandbox, install_root=install_root, runner=passing,
        )
        current_path = install_root / "profiles" / tree["id"] / "web" / "current.json"
        before = current_path.read_bytes()

        def failing(command, **_options):
            if "plugin" in command:
                return subprocess.CompletedProcess(command, 7, stdout="offline install failed\n")
            return subprocess.CompletedProcess(command, 0, stdout="dsh-vet@0.3.0\n")

        with self.assertRaisesRegex(InstallationError, "Offline sandbox installation failed"):
            install_in_sandbox(
                self.envelope, self.trust_root, self.receipt,
                tree=tree, sandbox=sandbox, install_root=install_root, runner=failing,
            )
        self.assertEqual(current_path.read_bytes(), before)
        self.assertTrue(Path(first["home"]).is_dir())
        self.assertEqual(len(list((install_root / "failed").iterdir())), 1)

    def test_progress_callback_reports_ordered_transaction_boundary(self):
        sandbox, tree = self.sandbox_and_tree()
        steps = []

        def runner(command, **_options):
            output = (
                "dsh-vet@0.3.0\n"
                if "--dump-config" in command
                else ("dsh web: http://127.0.0.1:3189/\n" if "web" in command else "installed\n")
            )
            return subprocess.CompletedProcess(command, 0, stdout=output)

        install_in_sandbox(
            self.envelope, self.trust_root, self.receipt,
            tree=tree, sandbox=sandbox, install_root=self.root / "progress",
            runner=runner, progress=lambda step, _detail: steps.append(step),
        )
        self.assertEqual(steps, ["verify", "profile", "install", "probe", "promote", "complete"])

    def test_symlinked_install_root_fails_closed(self):
        sandbox, tree = self.sandbox_and_tree()
        target = self.root / "real-installs"
        target.mkdir()
        linked = self.root / "linked-installs"
        linked.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(InstallationError, "symlink"):
            install_in_sandbox(
                self.envelope, self.trust_root, self.receipt,
                tree=tree, sandbox=sandbox, install_root=linked,
            )


if __name__ == "__main__":
    unittest.main()
