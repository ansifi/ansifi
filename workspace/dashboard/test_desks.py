"""Work-status reports for Analysis / Content / Network / Operate."""
from __future__ import annotations

import unittest

from desks import all_reports, one_report, works_board
from mail_status import classify_signals, is_client_mail


class DeskReportTests(unittest.TestCase):
    def test_operate_desk_only(self):
        rows = all_reports()
        ids = [r["id"] for r in rows]
        self.assertEqual(ids, ["operate"])
        self.assertTrue(rows[0]["exists"])
        self.assertIn("GEO.XYZ", rows[0]["summary"])

    def test_operate_status(self):
        row = one_report("operate")
        self.assertEqual(row["href"], "/app/operate.html")
        self.assertEqual(row["dashboard"], "/app/operate.html")
        titles = " ".join(i["title"] + i["status"] + i["detail"] for i in row["items"])
        self.assertIn("GEO.XYZ", titles)
        self.assertIn("Sevendyne payroll", titles)
        self.assertIn("Ansif personal", titles)
        self.assertNotIn("/hrms", row["href"])

    def test_works_board_is_operate_only(self):
        board = works_board()
        ids = [s["id"] for s in board["sections"]]
        self.assertEqual(ids, ["business"])
        biz = board["sections"][0]
        active_titles = " ".join(i["title"] for i in biz["active"])
        self.assertIn("GEO.XYZ", active_titles)
        self.assertIn("Ansif personal", active_titles)

    def test_unknown_app(self):
        self.assertIsNone(one_report("payroll"))

    def test_dashboard_urls(self):
        self.assertEqual(one_report("operate")["dashboard"], "/app/operate.html")


class MailFilterTests(unittest.TestCase):
    def test_client_hints(self):
        self.assertTrue(is_client_mail("GEO.XYZ payroll question", "hr@example.com"))
        self.assertTrue(is_client_mail("Redmine plugin", "dev@kde.org"))
        self.assertFalse(is_client_mail("Your Netflix bill", "info@netflix.com"))

    def test_project_need_not_claude_promo(self):
        chips = classify_signals(
            "Following up — Head of Product Development at DYNAMON",
            "Sevendyne Contact <contact@sevendyne.com>",
        )
        ids = [c["id"] for c in chips]
        self.assertIn("project_need", ids)
        self.assertFalse(
            is_client_mail(
                "Start a project to give each idea a home",
                "Claude Team <no-reply@email.claude.com>",
            )
        )
        self.assertFalse(is_client_mail("Security alert", "googlecommunityteam-noreply@google.com"))

    def test_plain_snippet_strips_mime(self):
        from mail_status import _plain_snippet

        raw = (
            b"--00000000000098b191065b6de57b\r\n"
            b'Content-Type: text/plain; charset="UTF-8"\r\n'
            b"Content-Transfer-Encoding: quoted-printable\r\n\r\n"
            b"Hello DYNAMON, we are following up.\r\n"
            b"--00000000000098b191065b6de57b\r\n"
        )
        out = _plain_snippet(raw)
        self.assertIn("Hello DYNAMON", out)
        self.assertNotIn("Content-Type", out)


if __name__ == "__main__":
    unittest.main()
