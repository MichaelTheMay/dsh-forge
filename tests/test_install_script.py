"""The Linux installer: what it checks, what it writes, and that a dry run writes nothing."""

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install.sh"

# A stand-in Apptainer: reports a version and "pulls" by writing a small file.
FAKE_APPTAINER = """#!/bin/sh
if [ "$1" = "--version" ]; then echo "apptainer version 1.3.4"; exit 0; fi
if [ "$1" = "pull" ]; then printf 'container-bytes' > "$2"; exit 0; fi
exit 1
"""


@unittest.skipUnless(shutil.which("sh") and shutil.which("sha256sum"), "needs a POSIX shell and sha256sum")
class InstallScriptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "home"
        self.home.mkdir()
        self.tools = Path(self.temp.name) / "tools"
        self.tools.mkdir()
        # Only the tools the script needs, so a real Apptainer on this machine is not seen.
        for name in ("python3", "sh", "sed", "dirname", "mkdir", "chmod", "mv", "cut", "sha256sum", "printf", "pwd"):
            found = shutil.which(name)
            if found:
                os.symlink(found, self.tools / name)

    def run_script(self, *arguments, apptainer=False):
        if apptainer:
            fake = self.tools / "apptainer"
            fake.write_text(FAKE_APPTAINER, encoding="utf-8")
            fake.chmod(0o755)
        environment = {"HOME": str(self.home), "PATH": str(self.tools)}
        return subprocess.run(
            ["sh", str(SCRIPT), *arguments], env=environment, capture_output=True, text=True, timeout=60,
        )

    def launcher(self):
        return self.home / ".local" / "bin" / "dsh-forge"

    def test_a_dry_run_explains_and_writes_nothing(self):
        result = self.run_script("--dry-run", apptainer=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("would run: apptainer pull", result.stdout)
        self.assertIn("would write:", result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_without_apptainer_it_sets_up_browsing_and_says_how_to_get_the_rest(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Apptainer: not installed", result.stdout)
        self.assertIn("set up to browse.", result.stdout)
        text = self.launcher().read_text(encoding="utf-8")
        self.assertIn(f'exec python3 "{ROOT}/scripts/serve.py" --desktop --sync-catalog "$@"', text)
        self.assertNotIn("DSH_FORGE_SANDBOX_IMAGE", text)
        self.assertTrue(self.launcher().stat().st_mode & stat.S_IXUSR)
        entry = (self.home / ".local/share/applications/dsh-forge.desktop").read_text(encoding="utf-8")
        self.assertIn(f"Exec={self.launcher()}", entry)

    def test_with_apptainer_it_downloads_the_image_once_and_pins_its_checksum(self):
        result = self.run_script(apptainer=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        image = self.home / ".local/share/dsh-forge/images/node-22-bookworm.sif"
        self.assertEqual(image.read_text(encoding="utf-8"), "container-bytes")
        self.assertEqual(image.stat().st_mode & 0o777, 0o400)
        expected = subprocess.run(["sha256sum", str(image)], capture_output=True, text=True, check=True).stdout.split()[0]
        text = self.launcher().read_text(encoding="utf-8")
        self.assertIn(f'export DSH_FORGE_SANDBOX_IMAGE="{image}"', text)
        self.assertIn(f'export DSH_FORGE_SANDBOX_IMAGE_SHA256="{expected}"', text)
        self.assertIn("set up to browse, install and run.", result.stdout)
        # Running it again reuses the image instead of downloading it again.
        again = self.run_script(apptainer=True)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("Already downloaded", again.stdout)

    def test_browse_only_skips_the_container_even_when_apptainer_exists(self):
        result = self.run_script("--browse-only", apptainer=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.home / ".local/share/dsh-forge").exists())
        self.assertNotIn("DSH_FORGE_SANDBOX_IMAGE", self.launcher().read_text(encoding="utf-8"))

    def test_unknown_options_and_help(self):
        self.assertEqual(self.run_script("--nope").returncode, 2)
        helped = self.run_script("--help")
        self.assertEqual(helped.returncode, 0)
        self.assertIn("--dry-run", helped.stdout)


if __name__ == "__main__":
    unittest.main()
