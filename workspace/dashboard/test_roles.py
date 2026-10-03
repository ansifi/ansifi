"""Super admin vs tenant admin roles."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from os_auth import (
    authenticate,
    can_manage_account,
    delete_account,
    find_account,
    is_operator_admin,
    is_super_admin,
    is_tenant_admin,
    update_account,
    workspace_accounts,
)


class RoleTests(unittest.TestCase):
    def test_empever_is_super_admin(self):
        user = authenticate("empever", "ansif123$")
        self.assertTrue(user["is_super_admin"])
        self.assertTrue(user["is_admin"])
        self.assertTrue(is_super_admin("empever"))

    def test_ansif_is_super_admin(self):
        user = authenticate("ansif", "ansif123")
        self.assertTrue(user["is_super_admin"])
        self.assertTrue(user["is_admin"])

    def test_sevendyne_is_tenant_admin_not_super(self):
        user = authenticate("sevendyne", "7dyne123")
        self.assertFalse(user["is_super_admin"])
        self.assertTrue(user["is_admin"])
        self.assertTrue(is_tenant_admin("sevendyne"))
        self.assertTrue(is_operator_admin("sevendyne"))
        self.assertFalse(is_super_admin("sevendyne"))

    def test_dummy_is_tenant_admin_not_super(self):
        user = authenticate("dummy_client", "demo123$")
        self.assertFalse(user["is_super_admin"])
        self.assertTrue(user["is_admin"])
        self.assertEqual(user["home"], "/dummy_client/")
        alias = authenticate("dummy", "demo123$")
        self.assertEqual(alias["username"], "dummy_client")
        self.assertTrue(alias["is_admin"])

    def test_csr_is_not_admin(self):
        user = authenticate("csr", "csr123$")
        self.assertFalse(user["is_super_admin"])
        self.assertFalse(user["is_admin"])
        self.assertEqual(user["desk"], "client")

    def test_super_admin_does_not_see_tenant_credentials(self):
        from os_auth import workspace_accounts

        self.assertEqual(workspace_accounts("empever"), [])
        self.assertEqual(workspace_accounts("ansif"), [])
        self.assertFalse(can_manage_account("empever", "sevendyne"))
        self.assertFalse(can_manage_account("empever", "dummy_client"))

    def test_sevendyne_accounts_are_nested_clients(self):
        from tenants import nested_employers

        with patch("os_auth.active_nested_employers", side_effect=nested_employers):
            names = {row["username"] for row in workspace_accounts("sevendyne")}
        self.assertEqual(names, {"csr", "geoxyz", "quantyf", "ovt", "crossdock"})
        self.assertNotIn("dummy_client", names)
        self.assertNotIn("empever", names)
        self.assertNotIn("sd_csr_001", names)

    def test_dummy_admin_has_no_nested_accounts(self):
        self.assertEqual(workspace_accounts("dummy_client"), [])

    def test_archived_clients_hidden_from_workspace_accounts(self):
        with patch("os_auth.active_nested_employers") as active:
            active.return_value = [
                {"id": "csr", "name": "CSR Informatik"},
                {"id": "quantyf", "name": "QUANTYF"},
            ]
            names = {row["username"] for row in workspace_accounts("sevendyne")}
        self.assertEqual(names, {"csr", "quantyf"})
        self.assertNotIn("crossdock", names)


class AccountStoreTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.write(b'{"accounts": [], "deleted": []}\n')
        handle.close()
        self.path = Path(handle.name)
        self.patcher = patch("os_auth.ACCOUNT_STORE", self.path)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.path.unlink(missing_ok=True)

    def test_sevendyne_can_update_csr_password(self):
        row = update_account("sevendyne", "csr", password="newcsr$")
        self.assertEqual(row["password"], "newcsr$")
        self.assertIsNotNone(authenticate("csr", "newcsr$"))
        self.assertIsNone(authenticate("csr", "csr123$"))

    def test_sevendyne_can_delete_nested_not_tenant_admin(self):
        self.assertFalse(delete_account("sevendyne", "sevendyne"))
        self.assertFalse(can_manage_account("sevendyne", "dummy_client"))
        self.assertTrue(delete_account("sevendyne", "csr"))
        self.assertIsNone(find_account("csr"))

    def test_super_admin_cannot_edit_tenant_login(self):
        self.assertIsNone(update_account("empever", "sevendyne", name="Sevendyne LLP", password="7dyne123"))
        self.assertFalse(delete_account("empever", "sevendyne"))
        self.assertFalse(can_manage_account("empever", "sevendyne"))

    def test_workspace_home_is_folder_reports_not_operates(self):
        js = (Path(__file__).resolve().parent / "dashboard.js").read_text()
        html = (Path(__file__).resolve().parent / "index.html").read_text()
        self.assertIn("function operatesOnlyDesk()", js)
        self.assertIn('url: "/app/operate.html"', js)
        self.assertIn("function operatesOnlyDesk() {\n  return true;", js)
        self.assertIn("planned-tab", html)
        self.assertIn("Analysis", html)
        self.assertIn("Content", html)
        self.assertIn("Network", html)
        self.assertIn("planned for future use", html)
        css = (Path(__file__).resolve().parent / "dashboard.css").read_text()
        self.assertIn('"status chat"', css)
        self.assertIn("planned-grid", css)


if __name__ == "__main__":
    unittest.main()
