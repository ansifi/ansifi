"""Notes into 02_Content and network signal lists."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import works_ops


class WorksOpsTests(unittest.TestCase):
    def test_save_note_writes_markdown(self):
        tmp = Path(tempfile.mkdtemp())
        old = works_ops.NOTES
        works_ops.NOTES = tmp
        try:
            out = works_ops.save_note("Busy lists", "A map of pagination.", work="RoR AI")
            self.assertTrue(out["ok"])
            path = tmp / out["name"]
            self.assertTrue(path.is_file())
            text = path.read_text(encoding="utf-8")
            self.assertIn("# Busy lists", text)
            self.assertIn("pagination", text)
            self.assertIn("RoR AI", text)
            self.assertNotIn("@gmail", text)
        finally:
            works_ops.NOTES = old

    def test_note_carries_work_for_content_filter(self):
        tmp = Path(tempfile.mkdtemp())
        old = works_ops.NOTES
        works_ops.NOTES = tmp
        try:
            out = works_ops.save_note("Busy lists", "A map of pagination.", work="RoR AI")
            item = works_ops._md_item(tmp / out["name"], "note")
            self.assertEqual(item["work"], "RoR AI")
        finally:
            works_ops.NOTES = old

    def test_empty_note_rejected(self):
        self.assertFalse(works_ops.save_note("x", "  ")["ok"])

    def test_contents_lists_drafts(self):
        data = works_ops.list_contents()
        names = [d["name"] for d in data["drafts"]]
        self.assertTrue(any("members-pagination" in n for n in names))
        ids = [p["id"] for p in data["publish"]]
        self.assertIn("devto", ids)
        self.assertIn("medium", ids)

    def test_network_has_signal_urls(self):
        data = works_ops.network_board()
        self.assertTrue(data["ok"])
        urls = [s.get("url") for s in data["signals"]]
        self.assertTrue(any(u and u.startswith("http") for u in urls))
        labels = [s["label"] for s in data["sources"]]
        self.assertTrue(any("Redmine" in x for x in labels))


if __name__ == "__main__":
    unittest.main()
