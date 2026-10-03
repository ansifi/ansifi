"""Sqlite store for the AI review inbox. Stdlib sqlite3 — hub has no ORM."""
from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from ai_review.crypto import seal, unseal
from ai_review.scope import saas_tenant_id

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / ".run" / "ai_review.sqlite"

JOB_STATUSES = ("pending", "approved", "edited", "skipped", "sent", "blocked")
DIGEST_STATUSES = ("pending", "reviewed")
POLICY_FLAGS = ("none", "named_client", "mailbox_leak", "host_leak")
CREATED_BY = ("ai", "human")
APP_GROUPS = {
    "brand_note": "notes",
    "post_draft": "posts",
    "outreach_draft": "network",
    "operates_alert": "operates",
}

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS brand_notes (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS post_drafts (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  brand_note_id INTEGER,
  title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  FOREIGN KEY (brand_note_id) REFERENCES brand_notes(id)
);

CREATE TABLE IF NOT EXISTS outreach_drafts (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'email',
  target_type TEXT NOT NULL DEFAULT '',
  target_id INTEGER,
  body TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operates_alerts (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  amount_hint TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_digests (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL,
  UNIQUE (tenant_id, date)
);

CREATE TABLE IF NOT EXISTS ai_jobs (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  jobable_type TEXT NOT NULL,
  jobable_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  policy_flag TEXT NOT NULL DEFAULT 'none',
  created_by TEXT NOT NULL DEFAULT 'ai',
  approved_by_user_id TEXT,
  digest_id INTEGER,
  snooze_until TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (digest_id) REFERENCES daily_digests(id)
);

CREATE TABLE IF NOT EXISTS platforms (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  name TEXT NOT NULL,
  adapter_key TEXT NOT NULL,
  credentials TEXT NOT NULL DEFAULT '',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS platform_posts (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  post_draft_id INTEGER NOT NULL,
  platform_id INTEGER NOT NULL,
  external_id TEXT NOT NULL DEFAULT '',
  external_url TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (post_draft_id) REFERENCES post_drafts(id),
  FOREIGN KEY (platform_id) REFERENCES platforms(id)
);

CREATE TABLE IF NOT EXISTS platform_metrics (
  id INTEGER PRIMARY KEY,
  platform_post_id INTEGER NOT NULL,
  views INTEGER NOT NULL DEFAULT 0,
  reactions INTEGER NOT NULL DEFAULT 0,
  comments_count INTEGER NOT NULL DEFAULT 0,
  polled_at TEXT NOT NULL,
  FOREIGN KEY (platform_post_id) REFERENCES platform_posts(id)
);

CREATE TABLE IF NOT EXISTS post_replies (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  platform_post_id INTEGER NOT NULL,
  external_reply_id TEXT NOT NULL,
  author TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  url TEXT NOT NULL DEFAULT '',
  posted_at TEXT NOT NULL DEFAULT '',
  needs_action INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'new',
  UNIQUE (tenant_id, platform_post_id, external_reply_id),
  FOREIGN KEY (platform_post_id) REFERENCES platform_posts(id)
);

CREATE TABLE IF NOT EXISTS email_threads (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  external_thread_id TEXT NOT NULL,
  sender TEXT NOT NULL DEFAULT '',
  subject TEXT NOT NULL DEFAULT '',
  body TEXT NOT NULL DEFAULT '',
  needs_action INTEGER NOT NULL DEFAULT 1,
  status TEXT NOT NULL DEFAULT 'new',
  is_known_contact INTEGER NOT NULL DEFAULT 0,
  UNIQUE (tenant_id, external_thread_id)
);

CREATE TABLE IF NOT EXISTS known_contacts (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  email TEXT NOT NULL,
  name TEXT NOT NULL DEFAULT '',
  UNIQUE (tenant_id, email)
);

CREATE TABLE IF NOT EXISTS invoices (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  operates_alert_id INTEGER NOT NULL,
  ai_job_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'draft_pending_send',
  send_after TEXT,
  sent_at TEXT,
  cancelled_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payslips (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  operates_alert_id INTEGER NOT NULL,
  ai_job_id INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'created',
  sent_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_runs (
  tenant_id TEXT NOT NULL,
  run_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ok',
  finished_at TEXT NOT NULL,
  error TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (tenant_id, run_date)
);

CREATE TABLE IF NOT EXISTS adapter_health (
  adapter_key TEXT PRIMARY KEY,
  last_ok_at TEXT,
  last_error TEXT NOT NULL DEFAULT '',
  error_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_ai_jobs_tenant ON ai_jobs(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_digest_tenant ON daily_digests(tenant_id, date);
CREATE INDEX IF NOT EXISTS idx_email_tenant ON email_threads(tenant_id);
CREATE INDEX IF NOT EXISTS idx_posts_tenant ON platform_posts(tenant_id);

CREATE TABLE IF NOT EXISTS client_snapshots (
  tenant_id TEXT NOT NULL,
  captured_on TEXT NOT NULL,
  nested_count INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (tenant_id, captured_on)
);

CREATE TABLE IF NOT EXISTS revenue_snapshots (
  tenant_id TEXT NOT NULL,
  month TEXT NOT NULL,
  amount_inr INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (tenant_id, month)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return date.today().isoformat()


class Store:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else DEFAULT_DB
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path))
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        return con

    def _init(self) -> None:
        with self.connect() as con:
            con.executescript(SCHEMA)
            cols = [r[1] for r in con.execute("PRAGMA table_info(post_drafts)")]
            if "source" not in cols:
                con.execute("ALTER TABLE post_drafts ADD COLUMN source TEXT NOT NULL DEFAULT ''")
            if "source_url" not in cols:
                con.execute("ALTER TABLE post_drafts ADD COLUMN source_url TEXT NOT NULL DEFAULT ''")

    def saas(self, tenant_id: str) -> str:
        return saas_tenant_id(tenant_id)

    def insert(self, table: str, **fields: Any) -> int:
        keys = list(fields)
        placeholders = ", ".join("?" for _ in keys)
        sql = f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})"
        with self.connect() as con:
            cur = con.execute(sql, [fields[k] for k in keys])
            return int(cur.lastrowid)

    def fetchone(self, sql: str, args: Iterable[Any] = ()) -> dict | None:
        with self.connect() as con:
            row = con.execute(sql, list(args)).fetchone()
        return dict(row) if row else None

    def fetchall(self, sql: str, args: Iterable[Any] = ()) -> list[dict]:
        with self.connect() as con:
            rows = con.execute(sql, list(args)).fetchall()
        return [dict(r) for r in rows]

    def execute(self, sql: str, args: Iterable[Any] = ()) -> None:
        with self.connect() as con:
            con.execute(sql, list(args))

    def jobable(self, jobable_type: str, jobable_id: int) -> dict | None:
        table = {
            "brand_note": "brand_notes",
            "post_draft": "post_drafts",
            "outreach_draft": "outreach_drafts",
            "operates_alert": "operates_alerts",
        }.get(jobable_type)
        if not table:
            return None
        return self.fetchone(f"SELECT * FROM {table} WHERE id = ?", (jobable_id,))

    def jobable_text(self, jobable_type: str, jobable_id: int) -> str:
        row = self.jobable(jobable_type, jobable_id) or {}
        parts = [str(row.get("title") or ""), str(row.get("body") or ""), str(row.get("subject") or "")]
        return "\n".join(p for p in parts if p)

    def update_jobable_body(self, jobable_type: str, jobable_id: int, body: str) -> None:
        table = {
            "brand_note": "brand_notes",
            "post_draft": "post_drafts",
            "outreach_draft": "outreach_drafts",
            "operates_alert": "operates_alerts",
        }.get(jobable_type)
        if not table:
            return
        self.execute(f"UPDATE {table} SET body = ? WHERE id = ?", (body, jobable_id))

    def create_job(
        self,
        *,
        tenant_id: str,
        jobable_type: str,
        jobable_id: int,
        created_by: str = "ai",
        digest_id: int | None = None,
        scan=None,
    ) -> dict:
        now = _now()
        sid = self.saas(tenant_id)
        job_id = self.insert(
            "ai_jobs",
            tenant_id=sid,
            jobable_type=jobable_type,
            jobable_id=jobable_id,
            status="pending",
            policy_flag="none",
            created_by=created_by if created_by in CREATED_BY else "ai",
            digest_id=digest_id,
            created_at=now,
            updated_at=now,
        )
        job = self.get_job(job_id, sid)
        if scan:
            scan(job_id)
            job = self.get_job(job_id, sid)
        return job or {"id": job_id, "tenant_id": sid}

    def get_job(self, job_id: int, tenant_id: str | None = None) -> dict | None:
        if tenant_id:
            return self.fetchone(
                "SELECT * FROM ai_jobs WHERE id = ? AND tenant_id = ?",
                (job_id, self.saas(tenant_id)),
            )
        return self.fetchone("SELECT * FROM ai_jobs WHERE id = ?", (job_id,))

    def set_job_policy(self, job_id: int, flag: str, blocked: bool) -> None:
        status = "blocked" if blocked else "pending"
        flag = flag if flag in POLICY_FLAGS else "none"
        self.execute(
            "UPDATE ai_jobs SET policy_flag = ?, status = ?, digest_id = CASE WHEN ? = 1 THEN NULL ELSE digest_id END, updated_at = ? WHERE id = ?",
            (flag, status, 1 if blocked else 0, _now(), job_id),
        )

    def attach_to_digest(self, job_id: int, digest_id: int) -> None:
        self.execute(
            "UPDATE ai_jobs SET digest_id = ?, updated_at = ? WHERE id = ? AND status != 'blocked'",
            (digest_id, _now(), job_id),
        )

    def get_or_create_digest(self, tenant_id: str, day: str | None = None) -> dict:
        sid = self.saas(tenant_id)
        day = day or _today()
        row = self.fetchone(
            "SELECT * FROM daily_digests WHERE tenant_id = ? AND date = ?",
            (sid, day),
        )
        if row:
            return row
        now = _now()
        did = self.insert(
            "daily_digests",
            tenant_id=sid,
            date=day,
            status="pending",
            created_at=now,
        )
        return self.fetchone("SELECT * FROM daily_digests WHERE id = ?", (did,)) or {
            "id": did,
            "tenant_id": sid,
            "date": day,
            "status": "pending",
        }

    def digest_jobs(self, digest_id: int, tenant_id: str) -> list[dict]:
        sid = self.saas(tenant_id)
        today = _today()
        rows = self.fetchall(
            """
            SELECT id, tenant_id, jobable_type, jobable_id, status, policy_flag,
                   created_by, approved_by_user_id, digest_id, snooze_until, created_at, updated_at
            FROM ai_jobs
            WHERE digest_id = ? AND tenant_id = ? AND status != 'blocked'
              AND (snooze_until IS NULL OR snooze_until <= ?)
            ORDER BY id
            """,
            (digest_id, sid, today),
        )
        out = []
        for row in rows:
            jobable = self.jobable(row["jobable_type"], row["jobable_id"]) or {}
            item = dict(row)
            item["app"] = APP_GROUPS.get(row["jobable_type"], "notes")
            item["title"] = jobable.get("title") or jobable.get("subject") or row["jobable_type"]
            item["body"] = jobable.get("body") or ""
            item["kind"] = jobable.get("kind") or ""
            item["is_payroll"] = row["jobable_type"] == "operates_alert" and jobable.get("kind") == "payslip"
            out.append(item)
        return out

    def tenant_digest(self, tenant_id: str, day: str | None = None) -> dict:
        sid = self.saas(tenant_id)
        digest = self.get_or_create_digest(sid, day)
        jobs = self.digest_jobs(digest["id"], sid)
        grouped = {"notes": [], "posts": [], "network": [], "operates": []}
        for job in jobs:
            grouped.setdefault(job["app"], []).append(job)
        posts = self.posts_status(sid)
        replies = self.replies_leads(sid)
        operates = self.operates_status(sid)
        return {
            "digest": {"id": digest["id"], "date": digest["date"], "status": digest["status"], "tenant_id": sid},
            "jobs": grouped,
            "posts": posts,
            "replies": replies,
            "operates": operates,
        }

    def posts_status(self, tenant_id: str) -> list[dict]:
        sid = self.saas(tenant_id)
        posts = self.fetchall(
            """
            SELECT pp.id, pp.status, pp.external_id, pp.external_url, pp.post_draft_id,
                   p.name AS platform_name, p.adapter_key
            FROM platform_posts pp
            JOIN platforms p ON p.id = pp.platform_id
            WHERE pp.tenant_id = ?
            ORDER BY pp.id DESC
            """,
            (sid,),
        )
        out = []
        for post in posts:
            metric = self.fetchone(
                "SELECT views, reactions, comments_count, polled_at FROM platform_metrics WHERE platform_post_id = ? ORDER BY id DESC LIMIT 1",
                (post["id"],),
            )
            row = dict(post)
            if post["status"] == "published" and metric:
                row["metrics"] = metric
                row["manual"] = False
            else:
                row["metrics"] = None
                row["manual"] = post["status"] != "published" or not post.get("adapter_key")
            out.append(row)
        manuals = self.fetchall(
            """
            SELECT pd.id, pd.title
            FROM post_drafts pd
            LEFT JOIN platform_posts pp ON pp.post_draft_id = pd.id
            JOIN ai_jobs j ON j.jobable_type = 'post_draft' AND j.jobable_id = pd.id
            WHERE pd.tenant_id = ? AND pp.id IS NULL AND j.status IN ('approved', 'sent')
            """,
            (sid,),
        )
        for draft in manuals:
            out.append(
                {
                    "id": None,
                    "status": "manual",
                    "external_id": "",
                    "external_url": "",
                    "post_draft_id": draft["id"],
                    "platform_name": "",
                    "adapter_key": "",
                    "metrics": None,
                    "manual": True,
                    "title": draft["title"],
                }
            )
        return out

    def replies_leads(self, tenant_id: str) -> dict:
        sid = self.saas(tenant_id)
        replies = self.fetchall(
            "SELECT id, author, needs_action, status FROM post_replies WHERE tenant_id = ? AND needs_action = 1",
            (sid,),
        )
        threads = self.fetchall(
            "SELECT id, sender, subject, is_known_contact, needs_action, status FROM email_threads WHERE tenant_id = ? AND needs_action = 1",
            (sid,),
        )
        known = sum(1 for t in threads if t["is_known_contact"])
        unknown = sum(1 for t in threads if not t["is_known_contact"])
        return {
            "post_replies": len(replies),
            "email_threads": len(threads),
            "needs_action": len(replies) + len(threads),
            "known_contact": known,
            "lead_candidate": unknown + len(replies),
            "threads": threads,
            "replies": replies,
        }

    def operates_status(self, tenant_id: str) -> dict:
        sid = self.saas(tenant_id)
        month = date.today().strftime("%Y-%m")
        invoices = self.fetchall(
            "SELECT id, status, send_after, sent_at FROM invoices WHERE tenant_id = ? AND created_at LIKE ?",
            (sid, month + "%"),
        )
        payslips = self.fetchall(
            "SELECT id, status, sent_at FROM payslips WHERE tenant_id = ? AND created_at LIKE ?",
            (sid, month + "%"),
        )

        def counts(rows: list[dict], keys: tuple[str, ...]) -> dict[str, int]:
            out = {k: 0 for k in keys}
            for row in rows:
                st = row.get("status") or ""
                if st in out:
                    out[st] += 1
                elif st in ("draft_pending_send", "created"):
                    out["draft"] = out.get("draft", 0) + 1
                elif st == "pending_send":
                    out["pending"] = out.get("pending", 0) + 1
            return out

        return {
            "invoices": counts(invoices, ("draft", "pending", "sent", "cancelled")),
            "payslips": counts(payslips, ("draft", "pending", "sent", "created")),
            "invoice_rows": invoices,
            "payslip_rows": payslips,
        }

    def super_health(self) -> dict:
        """Counts and adapter health only. Never jobable body, invoices totals, or payroll figures."""
        jobs = self.fetchall(
            """
            SELECT tenant_id,
                   SUM(CASE WHEN status IN ('pending', 'edited') THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN status IN ('approved', 'skipped', 'sent') THEN 1 ELSE 0 END) AS reviewed,
                   SUM(CASE WHEN status = 'blocked' THEN 1 ELSE 0 END) AS blocked
            FROM ai_jobs
            GROUP BY tenant_id
            """
        )
        blocks = self.fetchall(
            """
            SELECT tenant_id, policy_flag, COUNT(*) AS n
            FROM ai_jobs
            WHERE status = 'blocked'
            GROUP BY tenant_id, policy_flag
            """
        )
        runs = self.fetchall(
            "SELECT tenant_id, run_date, status, finished_at, error FROM daily_runs ORDER BY finished_at DESC"
        )
        adapters = self.fetchall("SELECT adapter_key, last_ok_at, last_error, error_count FROM adapter_health")
        tenants = []
        from tenants import get as get_tenant

        seen = {row["tenant_id"] for row in jobs} | {row["tenant_id"] for row in runs}
        for tid in sorted(seen):
            row = get_tenant(tid) or {}
            last = next((r for r in runs if r["tenant_id"] == tid), None)
            counts = next((j for j in jobs if j["tenant_id"] == tid), {"pending": 0, "reviewed": 0, "blocked": 0})
            tenants.append(
                {
                    "id": tid,
                    "plan": row.get("plan") or "standard",
                    "last_run": last["finished_at"] if last else None,
                    "last_run_status": last["status"] if last else "never",
                    "pending": int(counts.get("pending") or 0),
                    "reviewed": int(counts.get("reviewed") or 0),
                    "blocked": int(counts.get("blocked") or 0),
                    "errored": bool(last and last["status"] != "ok"),
                }
            )
        return {
            "tenants": tenants,
            "policy_blocks": [
                {"tenant_id": b["tenant_id"], "policy_flag": b["policy_flag"], "count": int(b["n"])} for b in blocks
            ],
            "adapters": adapters,
        }

    def is_payroll_job(self, job: dict) -> bool:
        if job.get("jobable_type") != "operates_alert":
            return False
        alert = self.jobable("operates_alert", int(job["jobable_id"])) or {}
        return alert.get("kind") == "payslip"

    def is_invoice_job(self, job: dict) -> bool:
        if job.get("jobable_type") != "operates_alert":
            return False
        alert = self.jobable("operates_alert", int(job["jobable_id"])) or {}
        return alert.get("kind") == "invoice"

    def set_job_status(self, job_id: int, tenant_id: str, status: str, *, user_id: str | None = None) -> dict | None:
        sid = self.saas(tenant_id)
        job = self.get_job(job_id, sid)
        if not job:
            return None
        if status not in JOB_STATUSES:
            return job
        approved_by = user_id if status == "approved" else job.get("approved_by_user_id")
        self.execute(
            "UPDATE ai_jobs SET status = ?, approved_by_user_id = ?, updated_at = ? WHERE id = ? AND tenant_id = ?",
            (status, approved_by, _now(), job_id, sid),
        )
        return self.get_job(job_id, sid)

    def snooze_job(self, job_id: int, tenant_id: str) -> dict | None:
        sid = self.saas(tenant_id)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.execute(
            "UPDATE ai_jobs SET digest_id = NULL, snooze_until = ?, status = 'pending', updated_at = ? WHERE id = ? AND tenant_id = ?",
            (tomorrow, _now(), job_id, sid),
        )
        return self.get_job(job_id, sid)

    def pending_digest_jobs(self, digest_id: int, tenant_id: str) -> list[dict]:
        sid = self.saas(tenant_id)
        return self.fetchall(
            "SELECT * FROM ai_jobs WHERE digest_id = ? AND tenant_id = ? AND status IN ('pending', 'edited') AND status != 'blocked'",
            (digest_id, sid),
        )

    def create_invoice_draft(self, *, tenant_id: str, alert_id: int, job_id: int, send_after: str) -> int:
        return self.insert(
            "invoices",
            tenant_id=self.saas(tenant_id),
            operates_alert_id=alert_id,
            ai_job_id=job_id,
            status="draft_pending_send",
            send_after=send_after,
            created_at=_now(),
        )

    def create_payslip_record(self, *, tenant_id: str, alert_id: int, job_id: int) -> int:
        return self.insert(
            "payslips",
            tenant_id=self.saas(tenant_id),
            operates_alert_id=alert_id,
            ai_job_id=job_id,
            status="created",
            created_at=_now(),
        )

    def mark_invoice_sent(self, invoice_id: int) -> None:
        self.execute(
            "UPDATE invoices SET status = 'sent', sent_at = ? WHERE id = ? AND status = 'draft_pending_send'",
            (_now(), invoice_id),
        )

    def cancel_invoice(self, invoice_id: int, tenant_id: str) -> None:
        self.execute(
            "UPDATE invoices SET status = 'cancelled', cancelled_at = ? WHERE id = ? AND tenant_id = ? AND status = 'draft_pending_send'",
            (_now(), invoice_id, self.saas(tenant_id)),
        )

    def due_invoices(self, now: str | None = None) -> list[dict]:
        stamp = now or _now()
        return self.fetchall(
            "SELECT * FROM invoices WHERE status = 'draft_pending_send' AND send_after IS NOT NULL AND send_after <= ?",
            (stamp,),
        )

    def mark_payslip_sent(self, payslip_id: int, tenant_id: str) -> None:
        self.execute(
            "UPDATE payslips SET status = 'sent', sent_at = ? WHERE id = ? AND tenant_id = ? AND status = 'created'",
            (_now(), payslip_id, self.saas(tenant_id)),
        )

    def add_platform(self, *, tenant_id: str, name: str, adapter_key: str, credentials: dict, active: bool = True) -> int:
        return self.insert(
            "platforms",
            tenant_id=self.saas(tenant_id),
            name=name,
            adapter_key=adapter_key,
            credentials=seal(json.dumps(credentials)),
            active=1 if active else 0,
            created_at=_now(),
        )

    def platform_credentials(self, platform_id: int, tenant_id: str) -> dict:
        row = self.fetchone(
            "SELECT credentials FROM platforms WHERE id = ? AND tenant_id = ?",
            (platform_id, self.saas(tenant_id)),
        )
        if not row:
            return {}
        raw = unseal(row["credentials"] or "")
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def active_platforms(self, tenant_id: str) -> list[dict]:
        return self.fetchall(
            "SELECT id, tenant_id, name, adapter_key, active FROM platforms WHERE tenant_id = ? AND active = 1",
            (self.saas(tenant_id),),
        )

    def published_posts(self, tenant_id: str) -> list[dict]:
        return self.fetchall(
            """
            SELECT pp.*, p.adapter_key, p.id AS platform_id
            FROM platform_posts pp
            JOIN platforms p ON p.id = pp.platform_id
            WHERE pp.tenant_id = ? AND pp.status = 'published' AND p.active = 1
            """,
            (self.saas(tenant_id),),
        )

    def upsert_metric(self, platform_post_id: int, views: int, reactions: int, comments_count: int) -> None:
        self.insert(
            "platform_metrics",
            platform_post_id=platform_post_id,
            views=int(views or 0),
            reactions=int(reactions or 0),
            comments_count=int(comments_count or 0),
            polled_at=_now(),
        )

    def add_reply_if_new(self, *, tenant_id: str, platform_post_id: int, reply: dict) -> int | None:
        sid = self.saas(tenant_id)
        ext = str(reply.get("external_reply_id") or "")
        if not ext:
            return None
        existing = self.fetchone(
            "SELECT id FROM post_replies WHERE tenant_id = ? AND platform_post_id = ? AND external_reply_id = ?",
            (sid, platform_post_id, ext),
        )
        if existing:
            return None
        return self.insert(
            "post_replies",
            tenant_id=sid,
            platform_post_id=platform_post_id,
            external_reply_id=ext,
            author=str(reply.get("author") or ""),
            body=str(reply.get("body") or ""),
            url=str(reply.get("url") or ""),
            posted_at=str(reply.get("posted_at") or ""),
            needs_action=1,
            status="new",
        )

    def upsert_email_thread(self, *, tenant_id: str, thread: dict, known: bool) -> int:
        sid = self.saas(tenant_id)
        ext = str(thread.get("external_thread_id") or "")
        existing = self.fetchone(
            "SELECT id FROM email_threads WHERE tenant_id = ? AND external_thread_id = ?",
            (sid, ext),
        )
        if existing:
            self.execute(
                "UPDATE email_threads SET sender = ?, subject = ?, body = ?, is_known_contact = ? WHERE id = ?",
                (
                    str(thread.get("sender") or ""),
                    str(thread.get("subject") or ""),
                    str(thread.get("body") or ""),
                    1 if known else 0,
                    existing["id"],
                ),
            )
            return int(existing["id"])
        return self.insert(
            "email_threads",
            tenant_id=sid,
            external_thread_id=ext,
            sender=str(thread.get("sender") or ""),
            subject=str(thread.get("subject") or ""),
            body=str(thread.get("body") or ""),
            needs_action=1,
            status="new",
            is_known_contact=1 if known else 0,
        )

    def is_known_contact(self, tenant_id: str, sender: str) -> bool:
        email = (sender or "").strip().lower()
        if "<" in email and ">" in email:
            email = email[email.find("<") + 1 : email.find(">")].strip().lower()
        row = self.fetchone(
            "SELECT id FROM known_contacts WHERE tenant_id = ? AND lower(email) = ?",
            (self.saas(tenant_id), email),
        )
        return bool(row)

    def add_contact(self, tenant_id: str, email: str, name: str = "") -> int:
        return self.insert(
            "known_contacts",
            tenant_id=self.saas(tenant_id),
            email=(email or "").strip().lower(),
            name=name,
        )

    def record_run(self, tenant_id: str, status: str, error: str = "") -> None:
        sid = self.saas(tenant_id)
        day = _today()
        now = _now()
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO daily_runs (tenant_id, run_date, status, finished_at, error)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, run_date) DO UPDATE SET
                  status = excluded.status, finished_at = excluded.finished_at, error = excluded.error
                """,
                (sid, day, status, now, error),
            )

    def run_today(self, tenant_id: str) -> dict | None:
        return self.fetchone(
            "SELECT * FROM daily_runs WHERE tenant_id = ? AND run_date = ?",
            (self.saas(tenant_id), _today()),
        )

    def record_adapter(self, adapter_key: str, ok: bool, error: str = "") -> None:
        now = _now()
        row = self.fetchone("SELECT * FROM adapter_health WHERE adapter_key = ?", (adapter_key,))
        if not row:
            self.insert(
                "adapter_health",
                adapter_key=adapter_key,
                last_ok_at=now if ok else None,
                last_error="" if ok else error,
                error_count=0 if ok else 1,
            )
            return
        if ok:
            self.execute(
                "UPDATE adapter_health SET last_ok_at = ?, last_error = '', error_count = 0 WHERE adapter_key = ?",
                (now, adapter_key),
            )
        else:
            self.execute(
                "UPDATE adapter_health SET last_error = ?, error_count = error_count + 1 WHERE adapter_key = ?",
                (error, adapter_key),
            )

    def pending_action_threads(self, tenant_id: str) -> list[dict]:
        return self.fetchall(
            "SELECT * FROM email_threads WHERE tenant_id = ? AND needs_action = 1 AND is_known_contact = 1 AND status = 'new'",
            (self.saas(tenant_id),),
        )

    def pending_action_replies(self, tenant_id: str) -> list[dict]:
        return self.fetchall(
            "SELECT * FROM post_replies WHERE tenant_id = ? AND needs_action = 1 AND status = 'new'",
            (self.saas(tenant_id),),
        )

    def approved_notes_without_draft(self, tenant_id: str) -> list[dict]:
        return self.fetchall(
            """
            SELECT n.*
            FROM brand_notes n
            JOIN ai_jobs j ON j.jobable_type = 'brand_note' AND j.jobable_id = n.id
            WHERE n.tenant_id = ? AND j.status = 'approved'
              AND NOT EXISTS (SELECT 1 FROM post_drafts d WHERE d.brand_note_id = n.id)
            """,
            (self.saas(tenant_id),),
        )

    def notes_today(self, tenant_id: str, day: str) -> list[dict]:
        return self.fetchall(
            "SELECT * FROM brand_notes WHERE tenant_id = ? AND created_at LIKE ?",
            (self.saas(tenant_id), day + "%"),
        )

    def pending_jobs_unattached(self, tenant_id: str) -> list[dict]:
        today = _today()
        return self.fetchall(
            """
            SELECT * FROM ai_jobs
            WHERE tenant_id = ? AND status IN ('pending', 'edited') AND policy_flag = 'none'
              AND digest_id IS NULL
              AND (snooze_until IS NULL OR snooze_until <= ?)
            """,
            (self.saas(tenant_id), today),
        )

    def job_for_jobable(self, tenant_id: str, jobable_type: str, jobable_id: int) -> dict | None:
        return self.fetchone(
            "SELECT * FROM ai_jobs WHERE tenant_id = ? AND jobable_type = ? AND jobable_id = ?",
            (self.saas(tenant_id), jobable_type, jobable_id),
        )

    def mark_digest_reviewed_if_done(self, digest_id: int, tenant_id: str) -> None:
        open_jobs = self.fetchall(
            "SELECT id FROM ai_jobs WHERE digest_id = ? AND tenant_id = ? AND status IN ('pending', 'edited')",
            (digest_id, self.saas(tenant_id)),
        )
        if not open_jobs:
            self.execute(
                "UPDATE daily_digests SET status = 'reviewed' WHERE id = ? AND tenant_id = ?",
                (digest_id, self.saas(tenant_id)),
            )

    def post_by_title(self, tenant_id: str, title: str) -> dict | None:
        return self.fetchone(
            "SELECT * FROM post_drafts WHERE tenant_id = ? AND title = ?",
            (self.saas(tenant_id), title),
        )

    def posts_board(self, tenant_id: str) -> list[dict]:
        sid = self.saas(tenant_id)
        drafts = self.fetchall(
            "SELECT id, title, body, source, source_url, created_at FROM post_drafts WHERE tenant_id = ? ORDER BY id DESC",
            (sid,),
        )
        out = []
        for draft in drafts:
            job = self.job_for_jobable(sid, "post_draft", int(draft["id"])) or {}
            post = self.fetchone(
                "SELECT id, status, external_url FROM platform_posts WHERE tenant_id = ? AND post_draft_id = ? ORDER BY id DESC LIMIT 1",
                (sid, draft["id"]),
            )
            views = reactions = comments = 0
            if post:
                metric = self.fetchone(
                    "SELECT views, reactions, comments_count FROM platform_metrics WHERE platform_post_id = ? ORDER BY id DESC LIMIT 1",
                    (post["id"],),
                )
                if metric:
                    views = int(metric.get("views") or 0)
                    reactions = int(metric.get("reactions") or 0)
                    comments = int(metric.get("comments_count") or 0)
            replies = self.fetchall(
                "SELECT id FROM post_replies WHERE tenant_id = ? AND platform_post_id = ? AND needs_action = 1",
                (sid, (post or {}).get("id") or 0),
            )
            status = job.get("status") or "draft"
            if post and post.get("status") == "published":
                status = "sent"
            out.append(
                {
                    "id": draft["id"],
                    "title": draft["title"],
                    "body": draft["body"],
                    "source": draft.get("source") or "",
                    "source_url": draft.get("source_url") or "",
                    "status": status,
                    "views": views,
                    "reactions": reactions,
                    "comments": comments,
                    "responses": len(replies),
                    "created_at": draft["created_at"],
                }
            )
        return out

    def post_kpis(self, tenant_id: str) -> dict:
        items = self.posts_board(tenant_id)
        return {
            "created": len(items),
            "sent": sum(1 for row in items if row["status"] in ("sent", "approved")),
            "viewed": sum(int(row["views"] or 0) for row in items),
            "responded": sum(int(row["responses"] or 0) for row in items),
        }

    def record_nested_snapshot(self, tenant_id: str, nested_count: int) -> None:
        sid = self.saas(tenant_id)
        day = _today()
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO client_snapshots (tenant_id, captured_on, nested_count)
                VALUES (?, ?, ?)
                ON CONFLICT(tenant_id, captured_on) DO UPDATE SET nested_count = excluded.nested_count
                """,
                (sid, day, int(nested_count)),
            )

    def nested_trend(self, tenant_id: str) -> list[dict]:
        return self.fetchall(
            "SELECT captured_on AS date, nested_count AS n FROM client_snapshots WHERE tenant_id = ? ORDER BY captured_on",
            (self.saas(tenant_id),),
        )

    def record_revenue(self, tenant_id: str, month: str, amount_inr: int) -> None:
        sid = self.saas(tenant_id)
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO revenue_snapshots (tenant_id, month, amount_inr)
                VALUES (?, ?, ?)
                ON CONFLICT(tenant_id, month) DO UPDATE SET amount_inr = excluded.amount_inr
                """,
                (sid, str(month), int(amount_inr)),
            )

    def revenue_trend(self, tenant_id: str) -> list[dict]:
        return self.fetchall(
            "SELECT month, amount_inr FROM revenue_snapshots WHERE tenant_id = ? ORDER BY month",
            (self.saas(tenant_id),),
        )
