import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("embed", ROOT / "scripts/embed_catalog.py")
embed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(embed)


class SnapshotValidation(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads((ROOT / "data/public-repos.seed.json").read_text())

    def test_real_snapshot(self):
        embed.validate(self.snapshot)

    def test_wrong_upstream(self):
        self.snapshot["entries"][0]["source_repository"] = "other/repository"
        self.snapshot["entries"][0]["parent_repository"] = "other/repository"
        with self.assertRaises(ValueError):
            embed.validate(self.snapshot)

    def test_untrusted_url_is_rejected(self):
        self.snapshot["entries"][0]["repository_url"] = "javascript:alert(1)"
        with self.assertRaises(ValueError):
            embed.validate(self.snapshot)

    def test_duplicate_identity(self):
        self.snapshot["entries"][1] = copy.deepcopy(self.snapshot["entries"][0])
        with self.assertRaises(ValueError):
            embed.validate(self.snapshot)

    def test_no_false_security_claim(self):
        self.snapshot["entries"][0]["verification"]["security_verified"] = True
        with self.assertRaises(ValueError):
            embed.validate(self.snapshot)

    def test_signed_snapshot_is_not_accepted_without_a_verifier(self):
        self.snapshot["provenance"]["signature_status"] = "verified"
        with self.assertRaises(ValueError):
            embed.validate(self.snapshot)

    def test_script_delimiter_is_escaped_without_altering_text(self):
        text = '</script><script>alert("repository text")</script>\u2028'
        self.snapshot["entries"][0]["description"] = text
        encoded = embed.encode(self.snapshot)
        self.assertNotIn("</script>", encoded)
        self.assertEqual(json.loads(encoded)["entries"][0]["description"], text)


if __name__ == "__main__":
    unittest.main()
