import importlib.util
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "codex_librarian.py"
SPEC = importlib.util.spec_from_file_location("codex_librarian", SCRIPT)
assert SPEC and SPEC.loader
codex_librarian = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(codex_librarian)


class CodexLibrarianCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "wiki"
        self.root.mkdir()
        self.runtime = self.base / "hermes-home"
        self.previous_home = os.environ.get("HERMES_HOME")

    def tearDown(self):
        if self.previous_home is None:
            os.environ.pop("HERMES_HOME", None)
        else:
            os.environ["HERMES_HOME"] = self.previous_home
        self.temp.cleanup()

    def call(self, *args):
        output = StringIO()
        with redirect_stdout(output):
            code = codex_librarian.main(["--knowledge-root", str(self.root), "--runtime-home", str(self.runtime), *args])
        return code, json.loads(output.getvalue())

    def test_change_uses_shared_core_and_writes_receipt(self):
        request = self.base / "request.json"
        request.write_text(json.dumps({"summary": "Add governed note", "changes": [{"path": "notes/example.md", "action": "write", "content": "# Example\n"}]}), encoding="utf-8")
        code, result = self.call("change", "--request", str(request))
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "applied")
        self.assertEqual((self.root / "notes/example.md").read_text(encoding="utf-8"), "# Example\n")
        self.assertTrue(list((self.runtime / "plugin-data/agentic-librarian/receipts").rglob("tx-*.json")))

    def test_apply_requires_explicit_approval_flag(self):
        target = self.root / "note.md"
        target.write_text("old\n", encoding="utf-8")
        request = self.base / "request.json"
        request.write_text(json.dumps({"risk_flags": ["decision"], "changes": [{"path": "note.md", "action": "write", "content": "new\n"}]}), encoding="utf-8")
        _, staged = self.call("change", "--request", str(request))
        code, rejected = self.call("apply", "--proposal-id", staged["proposal_id"])
        self.assertEqual(code, 2)
        self.assertIn("--approve", rejected["error"])
        self.assertEqual(target.read_text(encoding="utf-8"), "old\n")


if __name__ == "__main__":
    unittest.main()
