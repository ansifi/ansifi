"""Daily AI run, policy-gated digest, and approve-only dispatch. No new job queue — call these functions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ai_review.adapters import GmailAdapter, adapter_for
from ai_review.drafts import DraftGenerator
from ai_review.policy import policy_scan
from ai_review.scope import saas_tenant_id, saas_tenants
from ai_review.store import Store, _now, _today


def _wrap(store: Store, tenant_id: str, jobable_type: str, jobable_id: int) -> dict:
    existing = store.job_for_jobable(tenant_id, jobable_type, jobable_id)
    if existing:
        return existing
    return store.create_job(
        tenant_id=tenant_id,
        jobable_type=jobable_type,
        jobable_id=jobable_id,
        scan=lambda jid: policy_scan(jid, store),
    )


def _draft(tenant_id: str, kind: str, **kwargs) -> dict:
    return DraftGenerator.call(tenant=tenant_id, type=kind, **kwargs)


def daily_ai_run(tenant_id: str, store: Store | None = None, *, force: bool = False) -> dict:
    """Once per tenant per day. Idempotent. Never creates a sendable invoice or payslip."""
    store = store or Store()
    sid = saas_tenant_id(tenant_id)
    today = _today()
    existing = store.run_today(sid)
    digest = store.get_or_create_digest(sid, today)

    if existing and existing.get("status") == "ok" and not force:
        _poll_platforms(store, sid)
        _sync_email(store, sid)
        _roll_digest(store, sid, digest["id"])
        send_due_invoices(store)
        return store.tenant_digest(sid, today)

    try:
        # a. Analysis → BrandNote
        if not store.notes_today(sid, today):
            note = _draft(sid, "brand_note")
            nid = store.insert(
                "brand_notes",
                tenant_id=sid,
                title=note["title"],
                body=note["body"],
                created_at=_now(),
            )
            _wrap(store, sid, "brand_note", nid)

        # b. Approved BrandNote without PostDraft → PostDraft
        for note_row in store.approved_notes_without_draft(sid):
            post = _draft(sid, "post_draft", about=note_row.get("title") or "")
            pid = store.insert(
                "post_drafts",
                tenant_id=sid,
                brand_note_id=note_row["id"],
                title=post["title"],
                body=post["body"],
                created_at=_now(),
            )
            _wrap(store, sid, "post_draft", pid)

        # c. Known-contact email + post replies needing action
        for thread in store.pending_action_threads(sid):
            existing_mail = store.fetchone(
                "SELECT id FROM outreach_drafts WHERE tenant_id = ? AND target_type = 'email_thread' AND target_id = ?",
                (sid, thread["id"]),
            )
            if existing_mail:
                continue
            draft = _draft(sid, "email_reply", subject=thread.get("subject") or "")
            oid = store.insert(
                "outreach_drafts",
                tenant_id=sid,
                kind="email",
                target_type="email_thread",
                target_id=thread["id"],
                body=draft["body"],
                created_at=_now(),
            )
            _wrap(store, sid, "outreach_draft", oid)
        for reply in store.pending_action_replies(sid):
            existing_job = store.fetchone(
                """
                SELECT j.id FROM ai_jobs j
                JOIN outreach_drafts o ON o.id = j.jobable_id
                WHERE j.tenant_id = ? AND j.jobable_type = 'outreach_draft'
                  AND o.target_type = 'post_reply' AND o.target_id = ?
                """,
                (sid, reply["id"]),
            )
            if existing_job:
                continue
            draft = _draft(sid, "post_reply", about=reply.get("author") or "")
            oid = store.insert(
                "outreach_drafts",
                tenant_id=sid,
                kind="post_reply",
                target_type="post_reply",
                target_id=reply["id"],
                body=draft["body"],
                created_at=_now(),
            )
            _wrap(store, sid, "outreach_draft", oid)

        # d. Operates suggestions only — never a sendable Invoice/Payslip
        if not store.fetchall(
            "SELECT id FROM operates_alerts WHERE tenant_id = ? AND kind = 'invoice' AND created_at LIKE ?",
            (sid, today + "%"),
        ):
            inv = _draft(sid, "invoice")
            aid = store.insert(
                "operates_alerts",
                tenant_id=sid,
                kind="invoice",
                title=inv["title"],
                body=inv["body"],
                amount_hint="",
                created_at=_now(),
            )
            _wrap(store, sid, "operates_alert", aid)
        if not store.fetchall(
            "SELECT id FROM operates_alerts WHERE tenant_id = ? AND kind = 'payslip' AND created_at LIKE ?",
            (sid, today + "%"),
        ):
            pay = _draft(sid, "payslip")
            aid = store.insert(
                "operates_alerts",
                tenant_id=sid,
                kind="payslip",
                title=pay["title"],
                body=pay["body"],
                amount_hint="",
                created_at=_now(),
            )
            _wrap(store, sid, "operates_alert", aid)

        _poll_platforms(store, sid)
        _sync_email(store, sid)
        _roll_digest(store, sid, digest["id"])
        send_due_invoices(store)
        store.record_run(sid, "ok")
    except Exception as exc:  # noqa: BLE001 — record and surface on super-admin health
        store.record_run(sid, "error", str(exc)[:400])
        raise
    return store.tenant_digest(sid, today)


def _roll_digest(store: Store, tenant_id: str, digest_id: int) -> None:
    for job in store.pending_jobs_unattached(tenant_id):
        store.attach_to_digest(int(job["id"]), digest_id)


def _poll_platforms(store: Store, tenant_id: str) -> None:
    for post in store.published_posts(tenant_id):
        creds = store.platform_credentials(int(post["platform_id"]), tenant_id)
        adapter = adapter_for(post["adapter_key"], creds)
        if not adapter:
            continue
        try:
            metrics = adapter.fetch_metrics(post["external_id"])
            store.upsert_metric(
                int(post["id"]),
                metrics.get("views") or 0,
                metrics.get("reactions") or 0,
                metrics.get("comments_count") or 0,
            )
            for reply in adapter.fetch_replies(post["external_id"]):
                store.add_reply_if_new(tenant_id=tenant_id, platform_post_id=int(post["id"]), reply=reply)
            store.record_adapter(post["adapter_key"], True)
        except Exception as exc:  # noqa: BLE001
            store.record_adapter(post["adapter_key"], False, str(exc)[:200])


def _sync_email(store: Store, tenant_id: str) -> None:
    for row in store.fetchall(
        "SELECT id, adapter_key FROM platforms WHERE tenant_id = ? AND active = 1 AND adapter_key = 'gmail'",
        (store.saas(tenant_id),),
    ):
        creds = store.platform_credentials(int(row["id"]), tenant_id)
        gmail = GmailAdapter(creds)
        try:
            for thread in gmail.fetch_threads():
                sender = str(thread.get("sender") or "")
                known = store.is_known_contact(tenant_id, sender)
                store.upsert_email_thread(tenant_id=tenant_id, thread=thread, known=known)
            store.record_adapter("gmail", True)
        except Exception as exc:  # noqa: BLE001
            store.record_adapter("gmail", False, str(exc)[:200])


def digest_dispatch(job_id: int, user_id: str, store: Store | None = None) -> dict:
    """Explicit approve only. Never auto-sends payroll. Invoice becomes a 24h cancellable draft."""
    store = store or Store()
    job = store.get_job(job_id)
    if not job:
        raise ValueError("unknown_job")
    if job["status"] == "blocked":
        raise ValueError("blocked")
    sid = job["tenant_id"]
    kind = job["jobable_type"]
    jobable = store.jobable(kind, int(job["jobable_id"])) or {}

    if kind == "post_draft":
        published = _publish_post(store, sid, job, jobable)
        store.set_job_status(int(job["id"]), sid, "sent" if published else "approved", user_id=user_id)
        return store.get_job(int(job["id"]), sid) or job
    if kind == "outreach_draft":
        _send_reply(store, sid, jobable)
        store.set_job_status(int(job["id"]), sid, "sent", user_id=user_id)
        return store.get_job(int(job["id"]), sid) or job
    if kind == "operates_alert" and jobable.get("kind") == "invoice":
        send_after = (datetime.now(timezone.utc) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
        store.create_invoice_draft(
            tenant_id=sid,
            alert_id=int(jobable["id"]),
            job_id=int(job["id"]),
            send_after=send_after,
        )
        store.set_job_status(int(job["id"]), sid, "approved", user_id=user_id)
        return store.get_job(int(job["id"]), sid) or job
    if kind == "operates_alert" and jobable.get("kind") == "payslip":
        store.create_payslip_record(tenant_id=sid, alert_id=int(jobable["id"]), job_id=int(job["id"]))
        store.set_job_status(int(job["id"]), sid, "approved", user_id=user_id)
        return store.get_job(int(job["id"]), sid) or job
    store.set_job_status(int(job["id"]), sid, "approved", user_id=user_id)
    return store.get_job(int(job["id"]), sid) or job


def _publish_post(store: Store, tenant_id: str, job: dict, draft: dict) -> bool:
    platforms = store.active_platforms(tenant_id)
    published = False
    for plat in platforms:
        adapter = adapter_for(plat["adapter_key"], store.platform_credentials(int(plat["id"]), tenant_id))
        if not adapter:
            continue
        try:
            result = adapter.publish({"title": draft.get("title"), "body": draft.get("body")})
            store.insert(
                "platform_posts",
                tenant_id=store.saas(tenant_id),
                post_draft_id=int(draft["id"]),
                platform_id=int(plat["id"]),
                external_id=result.get("external_id") or "",
                external_url=result.get("external_url") or "",
                status="published",
                created_at=_now(),
                updated_at=_now(),
            )
            store.record_adapter(plat["adapter_key"], True)
            published = True
        except Exception as exc:  # noqa: BLE001
            store.insert(
                "platform_posts",
                tenant_id=store.saas(tenant_id),
                post_draft_id=int(draft["id"]),
                platform_id=int(plat["id"]),
                external_id="",
                external_url="",
                status="failed",
                created_at=_now(),
                updated_at=_now(),
            )
            store.record_adapter(plat["adapter_key"], False, str(exc)[:200])
    return published


def _send_reply(store: Store, tenant_id: str, draft: dict) -> None:
    target_type = draft.get("target_type")
    target_id = int(draft.get("target_id") or 0)
    if target_type == "email_thread":
        thread = store.fetchone(
            "SELECT * FROM email_threads WHERE id = ? AND tenant_id = ?",
            (target_id, store.saas(tenant_id)),
        )
        gmail_row = store.fetchone(
            "SELECT id FROM platforms WHERE tenant_id = ? AND adapter_key = 'gmail' AND active = 1",
            (store.saas(tenant_id),),
        )
        if thread and gmail_row:
            gmail = GmailAdapter(store.platform_credentials(int(gmail_row["id"]), tenant_id))
            gmail.reply(thread["external_thread_id"], draft.get("body") or "")
        if thread:
            store.execute(
                "UPDATE email_threads SET needs_action = 0, status = 'replied' WHERE id = ? AND tenant_id = ?",
                (target_id, store.saas(tenant_id)),
            )
        return
    if target_type == "post_reply":
        store.execute(
            "UPDATE post_replies SET needs_action = 0, status = 'replied' WHERE id = ? AND tenant_id = ?",
            (target_id, store.saas(tenant_id)),
        )


def approve_job(job_id: int, user_id: str, store: Store | None = None) -> dict:
    return digest_dispatch(job_id, user_id, store=store)


def approve_all(digest_id: int, tenant_id: str, user_id: str, store: Store | None = None) -> dict:
    """Bulk approve. Payroll-type AiJobs are excluded in this handler, not only the UI."""
    store = store or Store()
    sid = saas_tenant_id(tenant_id)
    approved = []
    skipped_payroll = []
    for job in store.pending_digest_jobs(digest_id, sid):
        if store.is_payroll_job(job):
            skipped_payroll.append(int(job["id"]))
            continue
        approved.append(digest_dispatch(int(job["id"]), user_id, store=store))
    store.mark_digest_reviewed_if_done(digest_id, sid)
    return {"approved": [j.get("id") for j in approved], "skipped_payroll": skipped_payroll}


def send_payroll(job_id: int, tenant_id: str, user_id: str, store: Store | None = None) -> dict:
    """Separate explicit action. Bulk approve never calls this."""
    store = store or Store()
    sid = saas_tenant_id(tenant_id)
    job = store.get_job(job_id, sid)
    if not job or not store.is_payroll_job(job):
        raise ValueError("not_payroll")
    if job["status"] not in ("approved", "edited"):
        raise ValueError("approve_first")
    row = store.fetchone(
        "SELECT id FROM payslips WHERE ai_job_id = ? AND tenant_id = ?",
        (job_id, sid),
    )
    if row:
        store.mark_payslip_sent(int(row["id"]), sid)
    store.set_job_status(job_id, sid, "sent", user_id=user_id)
    return store.get_job(job_id, sid) or job


def send_due_invoices(store: Store | None = None) -> list[int]:
    store = store or Store()
    sent = []
    for row in store.due_invoices():
        store.mark_invoice_sent(int(row["id"]))
        store.set_job_status(int(row["ai_job_id"]), row["tenant_id"], "sent")
        sent.append(int(row["id"]))
    return sent


def run_all_tenants(store: Store | None = None) -> None:
    store = store or Store()
    for row in saas_tenants():
        daily_ai_run(row["id"], store=store)
