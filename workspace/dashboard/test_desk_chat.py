"""Hub desk chat — status answers, no send/publish."""
from __future__ import annotations

import unittest

from desk_chat import detect_desk, is_job_request, reply, status_answer


class DeskChatTests(unittest.TestCase):
    def test_status_mentions_geoxyz(self):
        text = status_answer("what is going on with geoxyz", "analysis")
        self.assertIn("GEO.XYZ", text)

    def test_geoxyz_reply_is_short(self):
        out = reply("What's going on with GEO.XYZ?")
        self.assertIn("GEO.XYZ", out["text"])
        self.assertNotIn("portable solar", out["text"].lower())
        self.assertLess(len(out["text"]), 420)

    def test_ready_to_post_does_not_dump_operate(self):
        out = reply("What's ready to post?")
        self.assertIn("pagination", out["text"].lower())
        self.assertNotIn("Axxxx", out["text"])
        self.assertLess(len(out["text"]), 420)

    def test_followup_skips_what_was_already_said(self):
        hist = [
            {"role": "user", "text": "What's going on with GEO.XYZ?"},
            {
                "role": "bot",
                "text": "GEO.XYZ (Jan / Redmine) is ongoing. Paid client project in technicals/geoxyz/.",
            },
        ]
        out = reply("what else", "", hist)
        self.assertNotIn("GEO.XYZ", out["text"])
        self.assertTrue("KDE" in out["text"] or "RoR" in out["text"])

    def test_compound_stays_one_short_reply(self):
        out = reply("What's going on with GEO.XYZ? What's ready to post?")
        self.assertIn("GEO.XYZ", out["text"])
        self.assertRegex(out["text"].lower(), r"ready|pagination|draft")
        self.assertLess(len(out["text"]), 520)

    def test_detect_content(self):
        self.assertEqual(detect_desk("what is ready to post"), "content")

    def test_job_is_deferred(self):
        self.assertTrue(is_job_request("run job on content"))
        out = reply("run job on content")
        self.assertTrue(out.get("deferred"))
        self.assertFalse(out.get("started"))
        self.assertIn("does not publish", out["text"].lower())

    def test_empty(self):
        out = reply("  ")
        self.assertFalse(out["ok"])

    def test_payroll_question_is_not_a_job(self):
        self.assertFalse(is_job_request("how are sevendyne payroll desks"))
        out = reply("how are sevendyne payroll desks")
        self.assertIn("Sevendyne", out["text"])
        self.assertNotIn("Axxxx", out["text"])
        self.assertFalse(out.get("deferred"))

    def test_system_lists_works_root(self):
        out = reply("what is in my system")
        self.assertEqual(out.get("source"), "disk")
        self.assertIn("01_Build", out["text"])
        self.assertIn("04_Operate", out["text"])
        self.assertIn("On disk", out["text"])

    def test_system_digs_into_named_folder(self):
        out = reply("what's in 01_Build")
        self.assertEqual(out.get("source"), "disk")
        self.assertIn("technicals", out["text"].lower())
        self.assertIn("studies", out["text"].lower())

    def test_system_followup_goes_deeper(self):
        first = reply("what is in my system")
        hist = [
            {"role": "user", "text": "what is in my system"},
            {"role": "bot", "text": first["text"]},
        ]
        out = reply("dig deeper", "", hist)
        self.assertEqual(out.get("source"), "disk")
        self.assertIn("On disk", out["text"])
        self.assertNotEqual(out["text"], first["text"])

    def test_what_is_sevendyne_is_lookup_not_status_dump(self):
        out = reply("what is sevendyne")
        self.assertEqual(out.get("source"), "web")
        self.assertRegex(out["text"].lower(), r"sevendyne|engineering|consultancy|kochi")
        self.assertNotIn("Axxxx", out["text"])
        self.assertLess(len(out["text"]), 900)


if __name__ == "__main__":
    unittest.main()
