"""AI review inbox: policy, bulk approve, tenant isolation, adapters."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai_review.adapters import DevtoAdapter, HashnodeAdapter
from ai_review.jobs import approve_all, digest_dispatch, daily_ai_run
from ai_review.policy import policy_scan
from ai_review.store import Store, _now


class AiReviewTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        handle.close()
        self.db = Path(handle.name)
        self.store = Store(self.db)

    def tearDown(self):
        try:
            os.unlink(self.db)
        except OSError:
            pass

    def _note(self, tenant: str, body: str, title: str = "Note") -> dict:
        nid = self.store.insert(
            "brand_notes",
            tenant_id=self.store.saas(tenant),
            title=title,
            body=body,
            created_at=_now(),
        )
        return self.store.create_job(
            tenant_id=tenant,
            jobable_type="brand_note",
            jobable_id=nid,
            scan=lambda jid: policy_scan(jid, self.store),
        )

    def _alert(self, tenant: str, kind: str) -> dict:
        aid = self.store.insert(
            "operates_alerts",
            tenant_id=self.store.saas(tenant),
            kind=kind,
            title=kind,
            body=f"{kind} suggestion only",
            amount_hint="",
            created_at=_now(),
        )
        return self.store.create_job(
            tenant_id=tenant,
            jobable_type="operates_alert",
            jobable_id=aid,
            scan=lambda jid: policy_scan(jid, self.store),
        )

    def test_policy_blocks_named_client_and_excludes_from_digest(self):
        job = self._note("sevendyne", "Follow up with Dummy client about the retainer.")
        self.assertEqual(job["status"], "blocked")
        self.assertEqual(job["policy_flag"], "named_client")
        digest = self.store.get_or_create_digest("sevendyne")
        self.store.attach_to_digest(job["id"], digest["id"])
        inbox = self.store.tenant_digest("sevendyne")
        ids = [j["id"] for group in inbox["jobs"].values() for j in group]
        self.assertNotIn(job["id"], ids)

    def test_policy_blocks_mailbox_and_hostname(self):
        mail = self._note("sevendyne", "Write to founder@otherfirm.example tonight.")
        self.assertEqual(mail["policy_flag"], "mailbox_leak")
        self.assertEqual(mail["status"], "blocked")
        host = self._note("sevendyne", "The cron runs on db.internal after midnight.")
        self.assertEqual(host["policy_flag"], "host_leak")
        self.assertEqual(host["status"], "blocked")

    def test_super_health_never_includes_jobable_content(self):
        self._note("sevendyne", "Secret draft about payroll amounts 99999")
        payload = self.store.super_health()
        blob = json.dumps(payload)
        self.assertNotIn("Secret draft", blob)
        self.assertNotIn("99999", blob)
        self.assertNotIn("jobable", blob.lower())
        self.assertIn("policy_blocks", payload)
        self.assertIn("tenants", payload)
        for block in payload["policy_blocks"]:
            self.assertIn("policy_flag", block)
            self.assertIn("count", block)
            self.assertNotIn("body", block)

    def test_approve_all_skips_payroll(self):
        digest = self.store.get_or_create_digest("sevendyne")
        invoice = self._alert("sevendyne", "invoice")
        payslip = self._alert("sevendyne", "payslip")
        self.store.attach_to_digest(invoice["id"], digest["id"])
        self.store.attach_to_digest(payslip["id"], digest["id"])
        result = approve_all(digest["id"], "sevendyne", "sevendyne", store=self.store)
        self.assertIn(invoice["id"], result["approved"])
        self.assertIn(payslip["id"], result["skipped_payroll"])
        self.assertEqual(self.store.get_job(payslip["id"], "sevendyne")["status"], "pending")
        self.assertEqual(self.store.get_job(invoice["id"], "sevendyne")["status"], "approved")

    def test_invoice_approve_creates_cancellable_draft_not_send(self):
        job = self._alert("sevendyne", "invoice")
        updated = digest_dispatch(job["id"], "sevendyne", store=self.store)
        self.assertEqual(updated["status"], "approved")
        row = self.store.fetchone("SELECT * FROM invoices WHERE ai_job_id = ?", (job["id"],))
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "draft_pending_send")
        self.assertIsNotNone(row["send_after"])
        self.assertIsNone(row["sent_at"])
        send_after = datetime.strptime(row["send_after"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        self.assertGreater(send_after, datetime.now(timezone.utc) + timedelta(hours=23))

    def test_tenant_isolation(self):
        a = self._note("sevendyne", "A sevendyne note about the desk.")
        b = self._note("dummy_client", "A dummy note about the desk.")
        self.assertIsNone(self.store.get_job(a["id"], "dummy_client"))
        self.assertIsNone(self.store.get_job(b["id"], "sevendyne"))
        self.assertEqual(self.store.get_job(a["id"], "sevendyne")["id"], a["id"])
        da = self.store.get_or_create_digest("sevendyne")
        db = self.store.get_or_create_digest("dummy_client")
        self.store.attach_to_digest(a["id"], da["id"])
        self.store.attach_to_digest(b["id"], db["id"])
        inbox_a = self.store.tenant_digest("sevendyne")
        inbox_b = self.store.tenant_digest("dummy_client")
        ids_a = [j["id"] for group in inbox_a["jobs"].values() for j in group]
        ids_b = [j["id"] for group in inbox_b["jobs"].values() for j in group]
        self.assertIn(a["id"], ids_a)
        self.assertNotIn(b["id"], ids_a)
        self.assertIn(b["id"], ids_b)
        self.assertNotIn(a["id"], ids_b)
        self.store.upsert_email_thread(
            tenant_id="sevendyne",
            thread={"external_thread_id": "t1", "sender": "a@x.test", "subject": "Hi", "body": ""},
            known=True,
        )
        other = self.store.fetchone(
            "SELECT id FROM email_threads WHERE tenant_id = ? AND external_thread_id = ?",
            ("dummy_client", "t1"),
        )
        self.assertIsNone(other)

    def test_daily_run_does_not_create_sendable_invoice(self):
        daily_ai_run("dummy_client", store=self.store)
        invoices = self.store.fetchall("SELECT * FROM invoices WHERE tenant_id = ?", ("dummy_client",))
        payslips = self.store.fetchall("SELECT * FROM payslips WHERE tenant_id = ?", ("dummy_client",))
        self.assertEqual(invoices, [])
        self.assertEqual(payslips, [])
        alerts = self.store.fetchall(
            "SELECT kind FROM operates_alerts WHERE tenant_id = ?",
            ("dummy_client",),
        )
        kinds = {row["kind"] for row in alerts}
        self.assertEqual(kinds, {"invoice", "payslip"})


class HomeDeskTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        handle.close()
        self.db = Path(handle.name)
        self.store = Store(self.db)
        from ai_review import operates_accounts

        self._payroll_db = operates_accounts.payroll_db
        operates_accounts.payroll_db = lambda tenant_id: None

    def tearDown(self):
        from ai_review import operates_accounts

        operates_accounts.payroll_db = self._payroll_db
        try:
            os.unlink(self.db)
        except OSError:
            pass

    def test_sevendyne_site_posts_from_public_copy(self):
        from ai_review.home import home_desk

        payload = home_desk("sevendyne", is_super=False, store=self.store)
        titles = {row["title"] for row in payload["posts"]}
        self.assertIn("Managed product engineering, not contractor placement", titles)
        self.assertGreaterEqual(payload["kpis"]["posts_created"], 5)
        bodies = " ".join(row.get("body") or "" for row in payload["posts"])
        self.assertNotIn("@sevendyne.com", bodies)
        self.assertNotIn("GEOxyz", bodies)
        again = home_desk("sevendyne", is_super=False, store=self.store)
        self.assertEqual(len(again["posts"]), len(payload["posts"]))

    def test_super_home_lists_admin_clients_without_post_bodies(self):
        from ai_review.home import home_desk

        payload = home_desk("sevendyne", is_super=True, store=self.store)
        ids = {row["id"] for row in payload["clients"]}
        self.assertIn("sevendyne", ids)
        self.assertIn("dummy_client", ids)
        sev = next(row for row in payload["clients"] if row["id"] == "sevendyne")
        self.assertGreaterEqual(sev["nested_count"], 5)
        self.assertIn("growth", sev)
        self.assertEqual(sev["revenue"]["amount_inr"], 220000)
        self.assertEqual(sev["revenue"]["amount_label"], "₹2.2L")
        self.assertEqual(sev["revenue"]["label"], "growing")
        dummy = next(row for row in payload["clients"] if row["id"] == "dummy_client")
        self.assertEqual(dummy["revenue"]["amount_inr"], 0)
        self.assertEqual(dummy["revenue"]["label"], "steady")
        self.assertEqual(payload["kpis"]["revenue_inr"], 220000)
        self.assertEqual(payload["kpis"]["revenue_trend"], "growing")
        blob = json.dumps(payload)
        self.assertNotIn("Philip", blob)
        self.assertNotIn("payslip", blob.lower())
        self.assertNotIn("@sevendyne.com", blob)
        for post in payload["posts"]:
            self.assertNotIn("body", post)

    def test_dummy_posts_stay_on_dummy(self):
        from ai_review.home import home_desk

        dummy = home_desk("dummy_client", is_super=False, store=self.store)
        sev = home_desk("sevendyne", is_super=False, store=self.store)
        dummy_ids = {row["id"] for row in dummy["posts"]}
        sev_ids = {row["id"] for row in sev["posts"]}
        self.assertTrue(dummy_ids.isdisjoint(sev_ids))
        self.assertEqual(dummy["kpis"]["revenue_inr"], 0)
        self.assertEqual(dummy["kpis"]["revenue_trend"], "steady")


class RevenueTests(unittest.TestCase):
    def test_format_and_pad_six_months(self):
        from ai_review.revenue import format_inr, pad_series

        self.assertEqual(format_inr(220000), "₹2.2L")
        self.assertEqual(format_inr(0), "₹0")
        series = pad_series([{"month": "2026-09", "amount_inr": 220000}])
        self.assertEqual(len(series), 6)
        self.assertEqual(series[-1], {"month": "2026-09", "amount_inr": 220000})
        self.assertEqual(series[-2], {"month": "2026-08", "amount_inr": 0})

    def test_pct_change_labels(self):
        from ai_review.revenue import format_pct, pct_change, revenue_from_months

        self.assertEqual(pct_change(73000, 124000), -41)
        self.assertEqual(pct_change(124000, 0), 100)
        self.assertIsNone(pct_change(0, 0))
        self.assertIsNone(pct_change(100, None))
        self.assertEqual(format_pct(-41), "-41%")
        self.assertEqual(format_pct(3), "+3%")
        self.assertEqual(format_pct(None), "—")
        view = revenue_from_months(
            [
                {"month": "2026-07", "amount_inr": 274416},
                {"month": "2026-08", "amount_inr": 124000},
            ]
        )
        self.assertEqual(view["pct_change"], -55)
        self.assertEqual(view["pct_label"], "-55%")
        self.assertEqual(view["months"][1]["pct_label"], "-55%")


class OperatesAccountsTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        handle.close()
        self.path = Path(handle.name)
        con = __import__("sqlite3").connect(self.path)
        con.executescript(
            """
            CREATE TABLE portal_client (id INTEGER PRIMARY KEY, company_name TEXT);
            CREATE TABLE portal_invoice (
              id INTEGER PRIMARY KEY, client_id INTEGER, issue_date TEXT, due_date TEXT,
              amount REAL, currency TEXT, description TEXT
            );
            INSERT INTO portal_client VALUES (1, 'CSR Informatik Gmbh');
            INSERT INTO portal_client VALUES (2, 'Oovattil Softwareentwicklung');
            INSERT INTO portal_invoice VALUES (1, 1, '2026-04-15', '2026-04-30', 660, 'EUR', 'secret Philip line');
            INSERT INTO portal_invoice VALUES (2, 2, '2026-04-25', '2026-05-01', 145000, 'INR', 'Invoice for April');
            INSERT INTO portal_invoice VALUES (3, 2, '2026-08-01', '2026-08-31', 10000, 'INR', 'Invoice for August');
            """
        )
        con.commit()
        con.close()

    def tearDown(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_april_invoices_totals_without_line_text(self):
        from ai_review.operates_accounts import accounts_for

        acc = accounts_for("sevendyne", sqlite_path=self.path)
        self.assertEqual(acc["invoice_count"], 3)
        blob = json.dumps(acc)
        self.assertNotIn("Philip", blob)
        names = {row["name"] for row in acc["nested"]}
        self.assertIn("CSR Informatik", names)
        self.assertIn("Oovattil", names)
        csr = next(row for row in acc["nested"] if row["id"] == "csr")
        self.assertEqual(csr["invoice_count"], 1)
        self.assertEqual(acc["revenue"]["source"], "operates_invoices")
        self.assertEqual(acc["revenue"]["amount_inr"], 10000)
        self.assertEqual(acc["revenue"]["label"], "growing")
        ovt = next(row for row in acc["nested"] if row["id"] == "ovt")
        self.assertEqual(ovt["invoice_count"], 2)
        self.assertEqual(ovt["amount_inr"], 10000)
        csr = next(row for row in acc["nested"] if row["id"] == "csr")
        self.assertEqual(csr["amount_inr"], 0)
        apr = next(row for row in acc["months"] if row["month"] == "2026-04")
        self.assertEqual(apr["amount_inr"], 218000)

    def test_amount_to_inr_booked_euro_rate(self):
        from ai_review.operates_accounts import amount_to_inr

        self.assertEqual(amount_to_inr(660, "EUR"), 73000)
        self.assertEqual(amount_to_inr(51000, "INR"), 51000)
        self.assertEqual(amount_to_inr(100, "USD"), 8800)

    def test_august_euro_plus_quantyf_is_rupees(self):
        from ai_review.operates_accounts import accounts_for

        handle = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        handle.close()
        path = Path(handle.name)
        con = __import__("sqlite3").connect(path)
        con.executescript(
            """
            CREATE TABLE portal_client (id INTEGER PRIMARY KEY, company_name TEXT);
            CREATE TABLE portal_invoice (
              id INTEGER PRIMARY KEY, client_id INTEGER, issue_date TEXT, due_date TEXT,
              amount REAL, currency TEXT, description TEXT
            );
            INSERT INTO portal_client VALUES (1, 'CSR Informatik Gmbh');
            INSERT INTO portal_client VALUES (2, 'QUANTYF LLC');
            INSERT INTO portal_invoice VALUES (1, 1, '2026-08-17', '2026-08-31', 660, 'EUR', 'CSR August');
            INSERT INTO portal_invoice VALUES (2, 2, '2026-08-28', '2026-08-31', 51000, 'INR', 'Quantyf August');
            """
        )
        con.commit()
        con.close()
        try:
            acc = accounts_for("sevendyne", sqlite_path=path)
            aug = next(row for row in acc["months"] if row["month"] == "2026-08")
            self.assertEqual(aug["amount_inr"], 124000)
            self.assertEqual(acc["revenue"]["amount_inr"], 124000)
            self.assertEqual(acc["revenue"]["amount_label"], "₹1.24L")
            self.assertEqual(acc["revenue"]["pct_label"], "+100%")
            csr = next(row for row in acc["nested"] if row["id"] == "csr")
            self.assertEqual(csr["amount_inr"], 73000)
            self.assertEqual(csr["amount_label"], "₹73,000")
            quantyf = next(row for row in acc["nested"] if row["id"] == "quantyf")
            self.assertEqual(quantyf["amount_inr"], 51000)
            blob = json.dumps(acc)
            self.assertNotIn("€", blob)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def test_archived_clients_drop_from_nested_desks(self):
        from ai_review.operates_accounts import (
            archived_employer_ids,
            active_nested_employers,
        )

        handle = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        handle.close()
        path = Path(handle.name)
        con = __import__("sqlite3").connect(path)
        con.executescript(
            """
            CREATE TABLE portal_client (
              id INTEGER PRIMARY KEY, company_name TEXT, name TEXT,
              is_archived INTEGER DEFAULT 0
            );
            INSERT INTO portal_client VALUES (1, 'CSR Informatik Gmbh', 'CSR', 0);
            INSERT INTO portal_client VALUES (2, 'CROSSDOCK INFORMATION AND SERVICES PRIVATE LIMITED', 'CROSSDOCK', 1);
            """
        )
        con.commit()
        con.close()
        try:
            self.assertEqual(archived_employer_ids("sevendyne", sqlite_path=path), {"crossdock"})
            ids = {row["id"] for row in active_nested_employers("sevendyne", sqlite_path=path)}
            self.assertNotIn("crossdock", ids)
            self.assertIn("csr", ids)
            self.assertIn("quantyf", ids)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


class AdapterTests(unittest.TestCase):
    def test_devto_publish_and_metrics(self):
        calls = []

        def http(method, url, headers, body):
            calls.append((method, url, headers, body))
            if method == "POST":
                return {"id": 42, "url": "https://dev.to/x/hello"}
            if "comments" in url:
                return [{"id_code": "c1", "user": {"username": "pat"}, "body_html": "nice", "url": "", "created_at": "2026-01-01"}]
            return {"page_views_count": 10, "public_reactions_count": 4, "comments_count": 2}

        adapter = DevtoAdapter({"api_key": "k"}, http=http)
        published = adapter.publish({"title": "Hello", "body": "Hi"})
        self.assertEqual(published, {"external_id": "42", "external_url": "https://dev.to/x/hello"})
        metrics = adapter.fetch_metrics("42")
        self.assertEqual(metrics, {"views": 10, "reactions": 4, "comments_count": 2})
        replies = adapter.fetch_replies("42")
        self.assertEqual(replies[0]["external_reply_id"], "c1")
        self.assertEqual(replies[0]["author"], "pat")
        self.assertEqual(calls[0][0], "POST")
        self.assertIn("dev.to/api/articles", calls[0][1])

    def test_hashnode_publish_and_metrics(self):
        def http(method, url, headers, body):
            payload = json.loads(body.decode())
            if "publishPost" in payload["query"]:
                return {"data": {"publishPost": {"post": {"id": "hn1", "url": "https://hashnode.com/hello"}}}}
            if "reactionCount" in payload["query"]:
                return {"data": {"post": {"views": 8, "reactionCount": 3, "responseCount": 1}}}
            return {"data": {"post": {"comments": {"edges": []}}}}

        adapter = HashnodeAdapter({"token": "t", "publication_id": "pub"}, http=http)
        published = adapter.publish({"title": "Hello", "body": "Hi"})
        self.assertEqual(published, {"external_id": "hn1", "external_url": "https://hashnode.com/hello"})
        metrics = adapter.fetch_metrics("hn1")
        self.assertEqual(metrics, {"views": 8, "reactions": 3, "comments_count": 1})


if __name__ == "__main__":
    unittest.main()
