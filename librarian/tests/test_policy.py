import unittest
from pathlib import Path

from librarian_core.config import LibrarianConfig
from librarian_core.policy import assess_change


class PolicyTests(unittest.TestCase):
    def cfg(self, mode="balanced"):
        return LibrarianConfig(knowledge_root=Path("/tmp/kb"), policy_mode=mode)

    def test_new_page_is_autonomous(self):
        a = assess_change(relative=Path("notes/new.md"), action="write", old_content=None,
                          new_content="# New\nKnowledge\n", config=self.cfg())
        self.assertEqual(a.decision, "auto")
        self.assertIn("new_page", a.reasons)

    def test_additive_update_is_autonomous(self):
        a = assess_change(relative=Path("notes/a.md"), action="write", old_content="# A\none\n",
                          new_content="# A\none\ntwo\n", config=self.cfg())
        self.assertEqual(a.decision, "auto")
        self.assertTrue(a.additive_only)

    def test_delete_requires_review(self):
        a = assess_change(relative=Path("notes/a.md"), action="delete", old_content="x", new_content=None,
                          config=self.cfg())
        self.assertEqual(a.decision, "review")
        self.assertIn("delete", a.reasons)

    def test_human_controlled_requires_review(self):
        a = assess_change(relative=Path("SCHEMA.md"), action="write", old_content="old\n", new_content="new\n",
                          config=self.cfg())
        self.assertEqual(a.decision, "review")
        self.assertIn("human_controlled_path", a.reasons)

    def test_raw_existing_mutation_requires_review(self):
        a = assess_change(relative=Path("raw/source.md"), action="write", old_content="old", new_content="new",
                          config=self.cfg())
        self.assertEqual(a.decision, "review")
        self.assertIn("raw_source_mutation", a.reasons)

    def test_risk_flag_can_escalate(self):
        a = assess_change(relative=Path("notes/a.md"), action="write", old_content="# A\n", new_content="# A\nmore\n",
                          config=self.cfg(), risk_flags=["conflict"])
        self.assertEqual(a.decision, "review")
        self.assertIn("agent_flag:conflict", a.reasons)

    def test_duplicate_review_in_balanced_but_not_autonomous(self):
        balanced = assess_change(relative=Path("notes/widget.md"), action="write", old_content=None,
                                 new_content="# Widget", config=self.cfg(), possible_duplicates=["old/widget.md"])
        autonomous = assess_change(relative=Path("notes/widget.md"), action="write", old_content=None,
                                   new_content="# Widget", config=self.cfg("autonomous"), possible_duplicates=["old/widget.md"])
        self.assertEqual(balanced.decision, "review")
        self.assertEqual(autonomous.decision, "auto")

    def test_strict_non_additive_update_requires_review(self):
        cfg = LibrarianConfig(knowledge_root=Path("/tmp/kb"), policy_mode="strict",
                              major_rewrite_ratio=1.0, removal_review_ratio=1.0)
        a = assess_change(relative=Path("notes/a.md"), action="write", old_content="a\nb\nc\nd\n",
                          new_content="a\nb\nX\nd\n", config=cfg)
        self.assertEqual(a.decision, "review")
        self.assertIn("strict_mode_update", a.reasons)


if __name__ == "__main__":
    unittest.main()
