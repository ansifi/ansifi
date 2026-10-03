"""Home desk: posts, leads, admin-client growth. Apps open from these rows."""
from __future__ import annotations

from ai_review.brand_sites import posts_for, source_url
from ai_review.operates_accounts import accounts_for, active_nested_employers
from ai_review.policy import policy_scan
from ai_review.revenue import combined_revenue, revenue_view
from ai_review.scope import saas_tenant_id, saas_tenants
from ai_review.store import Store, _now
from tenants import get as get_tenant, is_saas_tenant


def _wrap(store: Store, tenant_id: str, jobable_type: str, jobable_id: int) -> None:
    if store.job_for_jobable(tenant_id, jobable_type, jobable_id):
        return
    store.create_job(
        tenant_id=tenant_id,
        jobable_type=jobable_type,
        jobable_id=jobable_id,
        scan=lambda jid: policy_scan(jid, store),
    )


def ensure_site_posts(tenant_id: str, store: Store | None = None) -> int:
    """Create public-site post drafts once per title. Never includes mailboxes or nested names."""
    store = store or Store()
    sid = saas_tenant_id(tenant_id)
    url = source_url(sid)
    created = 0
    for item in posts_for(sid):
        if store.post_by_title(sid, item["title"]):
            continue
        fields = dict(
            tenant_id=sid,
            title=item["title"],
            body=item["body"],
            created_at=_now(),
            source="site",
            source_url=url,
        )
        pid = store.insert("post_drafts", **fields)
        _wrap(store, sid, "post_draft", pid)
        created += 1
    return created


def _growth(trend: list[dict], current: int) -> dict:
    series = [int(row.get("n") or 0) for row in trend] or [current]
    if series[-1] != current:
        series.append(current)
    prev = series[-2] if len(series) > 1 else current
    if current > prev:
        direction = "up"
    elif current < prev:
        direction = "down"
    else:
        direction = "flat"
    return {"direction": direction, "series": series[-8:], "from": prev, "to": current}


def _admin_row(store: Store, row: dict) -> dict:
    tid = row["id"]
    nested = active_nested_employers(tid)
    store.record_nested_snapshot(tid, len(nested))
    trend = store.nested_trend(tid)
    kpis = store.post_kpis(tid)
    leads = store.replies_leads(tid)
    acc = accounts_for(tid)
    if acc and acc.get("revenue"):
        rev = acc["revenue"]
        for month_row in acc.get("months") or []:
            store.record_revenue(tid, month_row["month"], int(month_row.get("amount_inr") or 0))
    else:
        rev = revenue_view(store, tid, sqlite_path=False)
        acc = {}
    return {
        "id": tid,
        "name": row.get("name") or tid,
        "plan": row.get("plan") or "standard",
        "nested_count": len(nested),
        "nested": [{"id": n["id"], "name": n["name"]} for n in nested],
        "growth": _growth(trend, len(nested)),
        "revenue": rev,
        "accounts": acc.get("nested") or [],
        "invoice_count": int(acc.get("invoice_count") or 0),
        "posts": kpis,
        "leads_open": int(leads.get("needs_action") or 0),
    }


def home_desk(tenant_id: str, *, is_super: bool = False, store: Store | None = None) -> dict:
    store = store or Store()
    sid = saas_tenant_id(tenant_id)
    ensure_site_posts(sid, store=store)
    kpis = store.post_kpis(sid)
    posts = store.posts_board(sid)
    if is_super:
        # Super home lists titles and views, not full post bodies.
        posts = [{k: v for k, v in row.items() if k != "body"} for row in posts]
    leads = store.replies_leads(sid)
    lead_items = []
    for thread in leads.get("threads") or []:
        lead_items.append(
            {
                "id": thread["id"],
                "kind": "email",
                "title": thread.get("subject") or thread.get("sender") or "Thread",
                "known": bool(thread.get("is_known_contact")),
            }
        )
    for reply in leads.get("replies") or []:
        lead_items.append(
            {
                "id": reply["id"],
                "kind": "comment",
                "title": reply.get("author") or "Comment",
                "known": False,
            }
        )
    current = get_tenant(sid) or {"id": sid, "name": sid, "plan": "standard"}
    clients = []
    if is_super:
        for row in saas_tenants():
            clients.append(_admin_row(store, row))
    else:
        clients.append(_admin_row(store, current))
    money = combined_revenue([c.get("revenue") or {} for c in clients])
    return {
        "tenant_id": sid,
        "tenant_name": current.get("name") or sid,
        "kpis": {
            "posts_created": kpis["created"],
            "posts_sent": kpis["sent"],
            "posts_viewed": kpis["viewed"],
            "posts_responded": kpis["responded"],
            "leads_open": int(leads.get("needs_action") or 0),
            "known_contacts": int(leads.get("known_contact") or 0),
            "lead_candidates": int(leads.get("lead_candidate") or 0),
            "admin_clients": len(clients) if is_super else 1,
            "nested_clients": sum(c["nested_count"] for c in clients),
            "invoice_count": sum(int(c.get("invoice_count") or 0) for c in clients),
            "revenue_inr": money["amount_inr"],
            "revenue_label": money["amount_label"],
            "revenue_pct": money.get("pct_label") or "—",
            "revenue_pct_change": money.get("pct_change"),
            "revenue_direction": money["direction"],
            "revenue_trend": money["label"],
        },
        "posts": posts,
        "leads": lead_items,
        "clients": clients,
    }


def story(tenant_id: str, post_id: int, store: Store | None = None) -> dict | None:
    store = store or Store()
    sid = saas_tenant_id(tenant_id)
    row = store.fetchone(
        "SELECT * FROM post_drafts WHERE id = ? AND tenant_id = ?",
        (post_id, sid),
    )
    if not row:
        return None
    board = next((p for p in store.posts_board(sid) if int(p["id"]) == int(post_id)), None)
    return board
