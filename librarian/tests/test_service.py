import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from librarian_core.config import LibrarianConfig
from librarian_core import service


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "knowledge"
        self.root.mkdir()
        self.hermes = self.base / "hermes-home"
        self.env = mock.patch.dict(os.environ, {"HERMES_HOME": str(self.hermes)}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def cfg(self, **kwargs):
        values = dict(knowledge_root=self.root, qmd_duplicate_check=False, qmd_sync="off", git_checkpoint=False)
        values.update(kwargs)
        return LibrarianConfig(**values)

    def parse(self, value):
        return json.loads(value)

    def test_safe_new_file_auto_applies_and_receipts_exist(self):
        result = self.parse(service.change(self.cfg(), {
            "summary": "Add note",
            "changes": [{"path": "notes/a.md", "action": "write", "content": "# A\nhello\n"}],
        }))
        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["decision"], "auto")
        self.assertEqual((self.root / "notes/a.md").read_text(), "# A\nhello\n")
        receipts = list((self.hermes / "plugin-data/agentic-librarian/receipts").rglob("tx-*.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text())
        self.assertNotIn("content", json.dumps(receipt))

    def test_risky_change_is_staged_without_canonical_write(self):
        target = self.root / "notes/a.md"
        target.parent.mkdir(); target.write_text("# A\nkeep me\n")
        result = self.parse(service.change(self.cfg(), {
            "summary": "Delete note",
            "changes": [{"path": "notes/a.md", "action": "delete"}],
        }))
        self.assertEqual(result["status"], "review_required")
        self.assertTrue(target.exists())
        proposal = self.hermes / "plugin-data/agentic-librarian/proposals/pending" / f'{result["proposal_id"]}.json'
        self.assertTrue(proposal.exists())
        card = result["review_card"]
        self.assertEqual(card["status"], "review_needed")
        self.assertEqual(card["change_count"], 1)
        self.assertEqual(card["files"][0]["path"], "notes/a.md")
        self.assertEqual(card["files"][0]["removed_lines"], 2)
        self.assertEqual(card["files"][0]["content_label"], "Current content to be deleted")
        self.assertEqual(card["files"][0]["content_preview"], "# A\nkeep me")
        self.assertEqual(card["files"][0]["change_summary"], "Deletes this article (2 lines).")
        self.assertEqual(card["files"][0]["markdown_path"], str(target))
        self.assertEqual(card["decisions"]["approve"], "Yes — delete these 1 file.")
        self.assertNotIn(result["proposal_id"], card["decisions"]["approve"])
        review_page = Path(card["review_page"])
        self.assertTrue(review_page.exists())
        rendered = review_page.read_text(encoding="utf-8")
        self.assertIn('class="removed"', rendered)
        self.assertIn('<p class="meta">notes/a.md</p>', rendered)
        file_review_page = Path(card["files"][0]["review_page"])
        self.assertTrue(file_review_page.exists())
        self.assertIn('class="removed"', file_review_page.read_text(encoding="utf-8"))
        self.assertEqual(file_review_page.name, "01-A-proposed-vs-current.html")
        current_page = Path(card["files"][0]["current_page"])
        self.assertTrue(current_page.exists())
        self.assertIn("Current article: A", current_page.read_text(encoding="utf-8"))
        self.assertEqual(current_page.name, "01-A-current-article.html")

    def test_proposal_lookup_repeats_compact_review_card(self):
        target = self.root / "notes/a.md"
        target.parent.mkdir(); target.write_text("# A\nold\n")
        staged = self.parse(service.change(self.cfg(), {
            "risk_flags": ["decision"],
            "changes": [{"path": "notes/a.md", "action": "write", "content": "# A\nnew\nextra\n"}],
        }))
        reviewed = self.parse(service.get_proposal_tool(self.cfg(), {"proposal_id": staged["proposal_id"]}))
        card = reviewed["review_card"]
        self.assertEqual(card["proposal_id"], staged["proposal_id"])
        self.assertEqual(card["files"][0]["added_lines"], 3)
        self.assertEqual(card["files"][0]["removed_lines"], 2)
        self.assertEqual(card["files"][0]["content_label"], "Proposed content")
        self.assertEqual(card["files"][0]["content_preview"], "# A\nnew\nextra\n")
        self.assertEqual(card["files"][0]["change_summary"], "Updates the article with: new extra")
        self.assertNotIn("content", reviewed["proposal"]["changes"][0])

    def test_tampered_proposal_is_refused(self):
        target = self.root / "notes/a.md"
        target.parent.mkdir(); target.write_text("# A\nold\n")
        staged = self.parse(service.change(self.cfg(), {
            "risk_flags": ["decision"],
            "changes": [{"path": "notes/a.md", "action": "write", "content": "# A\nproposed\n"}],
        }))
        proposal = self.hermes / "plugin-data/agentic-librarian/proposals/pending" / f'{staged["proposal_id"]}.json'
        data = json.loads(proposal.read_text())
        data["changes"][0]["content"] = "# A\ntampered\n"
        proposal.write_text(json.dumps(data))
        result = self.parse(service.apply_proposal(self.cfg(), {"proposal_id": staged["proposal_id"]}))
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(target.read_text(), "# A\nold\n")
    def test_stale_proposal_refuses_apply(self):
        target = self.root / "notes/a.md"
        target.parent.mkdir(); target.write_text("# A\nold\n")
        staged = self.parse(service.change(self.cfg(), {
            "summary": "Replace with disputed fact",
            "risk_flags": ["conflict"],
            "changes": [{"path": "notes/a.md", "action": "write", "content": "# A\nproposed\n"}],
        }))
        self.assertEqual(staged["status"], "review_required")
        target.write_text("# A\nchanged elsewhere\n")
        applied = self.parse(service.apply_proposal(self.cfg(), {"proposal_id": staged["proposal_id"]}))
        self.assertEqual(applied["status"], "stale")
        self.assertEqual(target.read_text(), "# A\nchanged elsewhere\n")
        stale_path = self.hermes / "plugin-data/agentic-librarian/proposals/stale" / f'{staged["proposal_id"]}.json'
        self.assertTrue(stale_path.exists())

    def test_approved_proposal_applies_exact_content(self):
        target = self.root / "notes/a.md"
        target.parent.mkdir(); target.write_text("# A\nold\n")
        staged = self.parse(service.change(self.cfg(), {
            "risk_flags": ["decision"],
            "changes": [{"path": "notes/a.md", "action": "write", "content": "# A\napproved\n"}],
        }))
        applied = self.parse(service.apply_proposal(self.cfg(), {"proposal_id": staged["proposal_id"]}))
        self.assertEqual(applied["status"], "applied")
        self.assertEqual(applied["decision"], "human_approved")
        self.assertEqual(target.read_text(), "# A\napproved\n")

    def test_proposal_is_bound_to_knowledge_root(self):
        target = self.root / "notes/a.md"
        target.parent.mkdir(); target.write_text("old")
        staged = self.parse(service.change(self.cfg(), {
            "risk_flags": ["decision"],
            "changes": [{"path": "notes/a.md", "action": "write", "content": "new"}],
        }))
        other = self.base / "other"
        (other / "notes").mkdir(parents=True)
        (other / "notes/a.md").write_text("old")
        result = self.parse(service.apply_proposal(LibrarianConfig(knowledge_root=other, qmd_duplicate_check=False),
                                                   {"proposal_id": staged["proposal_id"]}))
        self.assertEqual(result["status"], "blocked")
        self.assertEqual((other / "notes/a.md").read_text(), "old")

    def test_partial_write_failure_rolls_back_prior_members(self):
        first = self.root / "first.md"
        second = self.root / "second.md"
        first.write_text("old first\n")
        second.write_text("old second\n")
        real_atomic = service.atomic_write_text
        calls = {"n": 0}

        def flaky(path, content):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("synthetic write failure")
            return real_atomic(path, content)

        with mock.patch.object(service, "atomic_write_text", side_effect=flaky):
            result = self.parse(service.change(self.cfg(major_rewrite_ratio=1.0, removal_review_ratio=1.0), {
                "changes": [
                    {"path": "first.md", "action": "write", "content": "old first\nadded\n"},
                    {"path": "second.md", "action": "write", "content": "old second\nadded\n"},
                ]
            }))
        self.assertIn("error", result)
        self.assertEqual(first.read_text(), "old first\n")
        self.assertEqual(second.read_text(), "old second\n")

    def test_duplicate_target_in_transaction_is_rejected(self):
        result = self.parse(service.change(self.cfg(), {
            "changes": [
                {"path": "a.md", "action": "write", "content": "# A\n"},
                {"path": "a.md", "action": "write", "content": "# A2\n"},
            ]
        }))
        self.assertIn("error", result)
        self.assertFalse((self.root / "a.md").exists())

    def test_large_batch_is_staged(self):
        result = self.parse(service.change(self.cfg(max_auto_changes=1), {
            "changes": [
                {"path": "a.md", "action": "write", "content": "# A\n"},
                {"path": "b.md", "action": "write", "content": "# B\n"},
            ]
        }))
        self.assertEqual(result["status"], "review_required")
        self.assertFalse((self.root / "a.md").exists())
        self.assertFalse((self.root / "b.md").exists())


if __name__ == "__main__":
    unittest.main()
