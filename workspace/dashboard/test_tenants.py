"""Host-tenant resolution — no Django, no network."""
from __future__ import annotations

import unittest

from tenants import find_by_domain, public_brand, resolve, split_path


class ResolveTests(unittest.TestCase):
    def test_localhost_defaults_to_sevendyne(self):
        row = resolve(host="127.0.0.1:4040", path="/")
        self.assertEqual(row["id"], "sevendyne")
        self.assertEqual(row["payroll_db"], "sevendyne")

    def test_path_csr_on_localhost(self):
        row = resolve(host="127.0.0.1:4040", path="/csr/django/dashboard/client/")
        self.assertEqual(row["id"], "csr")
        self.assertEqual(row["payroll_db"], "sevendyne")
        self.assertEqual(row["kind"], "employer")

    def test_app_sevendyne_host_is_white_label(self):
        row = resolve(host="app.sevendyne.com", path="/")
        self.assertEqual(row["id"], "sevendyne")
        chrome = public_brand("app.sevendyne.com", row)
        self.assertEqual(chrome["title"], "Sevendyne")
        self.assertTrue(chrome["hide_platform"])

    def test_csr_path_on_sevendyne_host(self):
        row = resolve(host="app.sevendyne.com", path="/csr/")
        self.assertEqual(row["id"], "csr")

    def test_dummy_subdomain_is_isolated_sqlite(self):
        row = resolve(host="dummy.empever.com", path="/")
        self.assertEqual(row["id"], "dummy_client")
        self.assertEqual(row["payroll_db"], "dummy_client")
        self.assertEqual(row["plan"], "standard")
        underscore = resolve(host="dummy_client.empever.com", path="/")
        self.assertEqual(underscore["id"], "dummy_client")

    def test_csr_path_on_dummy_host_is_rejected(self):
        row = resolve(host="dummy_client.empever.com", path="/csr/")
        self.assertIsNone(row)

    def test_employer_subdomain_is_not_a_saas_tenant(self):
        self.assertIsNone(find_by_domain("csr.empever.com"))
        self.assertIsNone(resolve(host="csr.empever.com", path="/"))

    def test_unknown_host_does_not_become_sevendyne(self):
        self.assertIsNone(resolve(host="evil.example.com", path="/"))

    def test_localhost_sevendyne_chrome_uses_sevendyne_name(self):
        row = resolve(host="127.0.0.1:4040", path="/")
        chrome = public_brand("127.0.0.1:4040", row)
        self.assertEqual(chrome["title"], "Sevendyne")
        self.assertEqual(chrome["mark"], "S")

    def test_csr_chrome_is_sevendyne_not_csr(self):
        row = resolve(host="127.0.0.1:4040", path="/csr/")
        chrome = public_brand("127.0.0.1:4040", row)
        self.assertEqual(chrome["title"], "Sevendyne")

    def test_dummy_chrome_is_client_name(self):
        row = resolve(host="dummy.empever.com", path="/")
        chrome = public_brand("dummy.empever.com", row)
        self.assertEqual(chrome["title"], "Dummy Client")
        self.assertEqual(chrome["mark"], "D")

    def test_app_empever_chrome_is_empever_not_sevendyne(self):
        row = resolve(host="app.empever.com", path="/")
        chrome = public_brand("app.empever.com", row)
        self.assertEqual(chrome["title"], "EMPEVER")
        self.assertEqual(chrome["mark"], "E")

    def test_csr_on_sevendyne_host_chrome_stays_sevendyne(self):
        row = resolve(host="app.sevendyne.com", path="/csr/")
        chrome = public_brand("app.sevendyne.com", row)
        self.assertEqual(chrome["title"], "Sevendyne")

    def test_split_path_strips_slug(self):
        slug, inner = split_path("/csr/auth/?x=1")
        self.assertEqual(slug, "csr")
        self.assertEqual(inner, "/auth/?x=1")

    def test_phone_mdns_is_platform(self):
        row = resolve(host="ansif-workspace.local:4040", path="/")
        self.assertEqual(row["id"], "sevendyne")

    def test_phone_lan_ip_is_platform(self):
        row = resolve(host="192.168.29.222:4040", path="/")
        self.assertEqual(row["id"], "sevendyne")
        row = resolve(host="192.168.29.222:4040", path="/csr/")
        self.assertEqual(row["id"], "csr")


if __name__ == "__main__":
    unittest.main()
