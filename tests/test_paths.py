import os
import tempfile
import unittest
from pathlib import Path

from librarian_core.paths import resolve_inside


class PathTests(unittest.TestCase):
    def test_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "kb"
            root.mkdir()
            with self.assertRaises(ValueError):
                resolve_inside(root, "../outside.md")

    def test_absolute_outside_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "kb"
            root.mkdir()
            outside = Path(td) / "outside.md"
            with self.assertRaises(ValueError):
                resolve_inside(root, outside)

    @unittest.skipIf(os.name == "nt", "symlink creation can require Windows developer/admin mode")
    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root = base / "kb"
            outside = base / "outside"
            root.mkdir(); outside.mkdir()
            (root / "link").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                resolve_inside(root, "link/secret.md")


if __name__ == "__main__":
    unittest.main()
