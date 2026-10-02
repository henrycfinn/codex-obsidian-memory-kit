import tempfile
import unittest
from pathlib import Path
from unittest import mock

from librarian_core.integrations import _spawn_args, filesystem_duplicate_candidates, qmd_duplicate_candidates


class IntegrationTests(unittest.TestCase):
    @mock.patch("librarian_core.integrations._qmd_command", return_value="qmd.cmd")
    @mock.patch("librarian_core.integrations._run", return_value=(0, "ready", ""))
    def test_qmd_status_uses_windows_command_wrapper(self, run, _):
        from librarian_core.integrations import qmd_status
        self.assertTrue(qmd_status()["ok"])
        self.assertEqual(run.call_args.args[0], ["qmd.cmd", "status"])

    def test_filesystem_duplicate_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "archive").mkdir()
            (root / "archive/dgx-spark.md").write_text("# DGX Spark\n")
            candidates = filesystem_duplicate_candidates(root, Path("notes/dgx_spark.md"))
            self.assertIn("archive/dgx-spark.md", candidates)

    @mock.patch("librarian_core.integrations.qmd_available", return_value=False)
    def test_qmd_absence_is_graceful(self, _):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(qmd_duplicate_candidates(root, Path("note.md"), "Note"), [])

    @mock.patch("librarian_core.integrations.os.name", "nt")
    @mock.patch("librarian_core.integrations.shutil.which", return_value=r"C:\\Users\\Henry\\AppData\\Roaming\\npm\\qmd.cmd")
    def test_windows_batch_shim_uses_cmd(self, _which):
        command = _spawn_args(["qmd", "status"])
        self.assertTrue(command[0].lower().endswith("cmd.exe"))
        self.assertEqual(command[1:4], ["/d", "/s", "/c"])
        self.assertIn("qmd.cmd", command[4])


if __name__ == "__main__":
    unittest.main()
