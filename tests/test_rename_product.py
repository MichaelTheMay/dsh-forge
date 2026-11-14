"""The rename tool reports by default, refuses bad names, and leaves identifiers alone."""

import contextlib
import importlib.util
import io
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rename_product", ROOT / "scripts" / "rename_product.py")
rename_product = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rename_product)


class RenameProductTests(unittest.TestCase):
    def run_main(self, *arguments):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rename_product.main(list(arguments))
        return code, out.getvalue(), err.getvalue()

    def test_reports_without_changing_anything(self):
        before = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        code, out, _ = self.run_main("Some New Name")
        self.assertEqual(code, 0)
        self.assertIn("Nothing changed.", out)
        self.assertIn("web/index.html", out)
        self.assertEqual((ROOT / "web" / "index.html").read_text(encoding="utf-8"), before)

    def test_leaves_identifiers_history_and_installer_identity_alone(self):
        listed = {str(path.relative_to(ROOT)) for path, _count in rename_product.plan("Some New Name")}
        for untouched in ("docs/decisions.md", "docs/PROBLEM.md", "packaging/windows/DSHForge.iss", "tests/test_workflow.py"):
            self.assertNotIn(untouched, listed)
        self.assertFalse(any(name.startswith(("data/", "web/vendor/", "gems/reviews/")) for name in listed))
        # Only the display name is matched: the package, command and variable names are different strings.
        for identifier in ("dsh_forge", "dsh-forge", "DSH_FORGE"):
            self.assertNotIn(rename_product.CURRENT, identifier)

    def test_refuses_names_that_would_break_pages_or_change_nothing(self):
        for bad in ("", "x", "DSH Forge", "Has <b>markup</b>", 'Quote"d', " padded ", "y" * 41, "line\nbreak"):
            with self.subTest(bad=bad):
                code, _out, err = self.run_main(bad)
                self.assertEqual(code, 2)
                self.assertIn("Choose a different name", err)


if __name__ == "__main__":
    unittest.main()
