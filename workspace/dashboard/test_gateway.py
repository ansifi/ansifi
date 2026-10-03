"""Hub reverse-proxy path map — no network."""
from __future__ import annotations

import unittest

from gateway import match_upstream


class GatewayTests(unittest.TestCase):
    def test_django_mount_strips_to_payrolls(self):
        host, port, path = match_upstream("/django/portal/admin/compliance/?payroll_db=sevendyne")
        self.assertEqual((host, port), ("127.0.0.1", 8008))
        self.assertEqual(path, "/portal/admin/compliance/?payroll_db=sevendyne")

    def test_public_hr_django_mount_strips_to_payrolls(self):
        host, port, path = match_upstream("/hr/django/portal/admin/invoices/?payroll_db=sevendyne")
        self.assertEqual((host, port), ("127.0.0.1", 8008))
        self.assertEqual(path, "/portal/admin/invoices/?payroll_db=sevendyne")

    def test_portal_without_django_prefix(self):
        host, port, path = match_upstream("/portal/admin/bank-ledger/")
        self.assertEqual((host, port, path), ("127.0.0.1", 8008, "/portal/admin/bank-ledger/"))

    def test_hrms_stays_on_next(self):
        host, port, path = match_upstream("/hrms?m=compliance")
        self.assertEqual((host, port), ("127.0.0.1", 3001))
        self.assertEqual(path, "/hrms?m=compliance")

    def test_hr_prefix_strips_to_next(self):
        host, port, path = match_upstream("/hr/hrms?m=clients")
        self.assertEqual((host, port), ("127.0.0.1", 3001))
        self.assertEqual(path, "/hrms?m=clients")

    def test_workspace_apps_are_local(self):
        self.assertIsNone(match_upstream("/apps/analysis/"))
        self.assertIsNone(match_upstream("/apps/content/"))
        self.assertIsNone(match_upstream("/apps/network/"))
        self.assertIsNone(match_upstream("/apps/automate/"))
        self.assertIsNone(match_upstream("/apps/operate/"))

    def test_old_app_paths_redirect_into_works_screens(self):
        from serve import works_app_location

        self.assertEqual(works_app_location("/apps/analysis/"), "/app/analysis.html")
        self.assertEqual(works_app_location("/apps/content/?work=RoR"), "/app/content.html?work=RoR")
        self.assertEqual(works_app_location("/apps/automate/"), "/app/")

    def test_desk_notes_keeps_vite_base(self):
        host, port, path = match_upstream("/apps/desk/notes")
        self.assertEqual((host, port), ("127.0.0.1", 6175))
        self.assertEqual(path, "/apps/desk/notes")

    def test_desk_email_keeps_vite_base(self):
        host, port, path = match_upstream("/apps/desk/email")
        self.assertEqual((host, port), ("127.0.0.1", 6175))
        self.assertEqual(path, "/apps/desk/email")


class SuperAdminOperatesScopeTests(unittest.TestCase):
    def test_hrms_and_invoice_admin_are_confidential(self):
        from serve import confidential_operates_path, platform_operates_url

        self.assertTrue(confidential_operates_path("/hrms?m=compliance&payroll_db=sevendyne"))
        self.assertTrue(confidential_operates_path("/django/portal/admin/invoices/?payroll_db=sevendyne"))
        self.assertTrue(confidential_operates_path("/portal/admin/bank-ledger/"))
        self.assertFalse(confidential_operates_path("/django/dashboard/admin/?portal_username=empever"))
        self.assertFalse(confidential_operates_path("/analyse/"))
        self.assertEqual(
            platform_operates_url("empever"),
            "/django/dashboard/admin/?portal_username=empever&dyne_embed=1",
        )


class WorkspaceDeskAppTests(unittest.TestCase):
    def test_home_apps_are_analysis_content_network(self):
        from pathlib import Path

        js = (Path(__file__).resolve().parent / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn('url: "/app/operate.html"', js)
        self.assertIn("/api/desk-chat", js)
        self.assertIn("/api/desk-mail", (Path(__file__).resolve().parent / "serve.py").read_text(encoding="utf-8"))
        inbox = (
            Path(__file__).resolve().parent.parent
            / "leads"
            / "channel"
            / "frontend"
            / "src"
            / "pages"
            / "InboxSignals.jsx"
        )
        self.assertIn("/api/desk-mail", inbox.read_text(encoding="utf-8"))
        self.assertNotIn('"/hrms?m=compliance&payroll_db="', js)


if __name__ == "__main__":
    unittest.main()
