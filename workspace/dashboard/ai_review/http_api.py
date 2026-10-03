"""Hub HTTP for the AI review inbox. Super admin: counts only."""
from __future__ import annotations

from os_auth import is_operator_admin, is_super_admin, is_tenant_admin

from ai_review.home import home_desk
from ai_review.jobs import approve_all, daily_ai_run, digest_dispatch, send_payroll
from ai_review.scope import saas_tenant_id
from ai_review.store import Store
from tenants import get as get_tenant, is_saas_tenant


def _store() -> Store:
    return Store()


def _user_id(auth: dict) -> str:
    return str(auth.get("username") or "")


def _saas_for(handler, auth: dict) -> str | None:
    current = handler._current_from_request(auth)
    mine = str(auth.get("tenant") or "") or current
    return saas_tenant_id(mine)


def handle(handler) -> bool:
    path = handler.path.split("?", 1)[0]
    if not path.startswith("/api/ai"):
        return False
    if handler.command == "OPTIONS":
        handler._json(200, {"ok": True})
        return True
    auth = handler._auth()
    if not auth:
        handler._json(401, {"ok": False, "error": "login_required"})
        return True
    uname = _user_id(auth)
    parts = [p for p in path.split("/") if p]
    # parts: api, ai, ...
    action = parts[2:] if len(parts) >= 3 else []

    if action == ["health"] and handler.command == "GET":
        if not is_super_admin(uname):
            handler._json(403, {"ok": False, "error": "super_admin_only"})
            return True
        handler._json(200, {"ok": True, **_store().super_health()})
        return True

    if action == ["home"] and handler.command == "GET":
        if not is_operator_admin(uname, str(auth.get("tenant") or "")):
            handler._json(403, {"ok": False, "error": "admin_only"})
            return True
        sid = _saas_for(handler, auth)
        row = get_tenant(sid)
        if not row or not is_saas_tenant(row):
            handler._json(403, {"ok": False, "error": "saas_tenant_only"})
            return True
        payload = home_desk(sid, is_super=is_super_admin(uname), store=_store())
        handler._json(200, {"ok": True, **payload})
        return True

    if action == ["stories"] and handler.command == "GET":
        if not is_operator_admin(uname, str(auth.get("tenant") or "")):
            handler._json(403, {"ok": False, "error": "admin_only"})
            return True
        sid = _saas_for(handler, auth)
        payload = home_desk(sid, is_super=False, store=_store())
        handler._json(200, {"ok": True, "tenant_id": sid, "posts": payload.get("posts") or []})
        return True

    if action == ["digest"] and handler.command == "GET":
        if is_super_admin(uname):
            handler._json(403, {"ok": False, "error": "use_health"})
            return True
        if not is_operator_admin(uname, str(auth.get("tenant") or "")):
            handler._json(403, {"ok": False, "error": "admin_only"})
            return True
        sid = _saas_for(handler, auth)
        row = get_tenant(sid)
        if not row or not is_saas_tenant(row):
            handler._json(403, {"ok": False, "error": "saas_tenant_only"})
            return True
        store = _store()
        try:
            daily_ai_run(sid, store=store)
        except Exception:
            pass
        payload = store.tenant_digest(sid)
        handler._json(200, {"ok": True, "tenant_id": sid, **payload})
        return True

    if action == ["run"] and handler.command == "POST":
        if is_super_admin(uname):
            body = handler._read_json()
            sid = saas_tenant_id(str(body.get("tenant_id") or handler._current_from_request(auth)))
            daily_ai_run(sid, store=_store(), force=True)
            handler._json(200, {"ok": True, "tenant_id": sid})
            return True
        if not is_tenant_admin(uname, str(auth.get("tenant") or "")):
            handler._json(403, {"ok": False, "error": "admin_only"})
            return True
        sid = _saas_for(handler, auth)
        daily_ai_run(sid, store=_store(), force=True)
        handler._json(200, {"ok": True, "tenant_id": sid})
        return True

    if len(action) >= 3 and action[0] == "digest" and action[2] == "approve-all" and handler.command == "POST":
        if is_super_admin(uname) or not is_operator_admin(uname, str(auth.get("tenant") or "")):
            handler._json(403, {"ok": False, "error": "tenant_admin_only"})
            return True
        digest_id = int(action[1])
        sid = _saas_for(handler, auth)
        result = approve_all(digest_id, sid, uname, store=_store())
        handler._json(200, {"ok": True, **result})
        return True

    if len(action) >= 3 and action[0] == "jobs" and handler.command == "POST":
        if is_super_admin(uname) or not is_operator_admin(uname, str(auth.get("tenant") or "")):
            handler._json(403, {"ok": False, "error": "tenant_admin_only"})
            return True
        job_id = int(action[1])
        verb = action[2]
        sid = _saas_for(handler, auth)
        store = _store()
        job = store.get_job(job_id, sid)
        if not job:
            handler._json(404, {"ok": False, "error": "not_found"})
            return True
        try:
            if verb == "approve":
                updated = digest_dispatch(job_id, uname, store=store)
            elif verb == "skip":
                updated = store.set_job_status(job_id, sid, "skipped", user_id=uname)
            elif verb == "snooze":
                updated = store.snooze_job(job_id, sid)
            elif verb == "edit":
                body = handler._read_json()
                store.update_jobable_body(job["jobable_type"], int(job["jobable_id"]), str(body.get("body") or ""))
                from ai_review.policy import policy_scan

                flag = policy_scan(job_id, store)
                if flag != "none":
                    handler._json(200, {"ok": True, "job": store.get_job(job_id, sid), "policy_flag": flag})
                    return True
                updated = store.set_job_status(job_id, sid, "edited", user_id=uname)
            elif verb == "send-payroll":
                updated = send_payroll(job_id, sid, uname, store=store)
            else:
                handler._json(404, {"ok": False, "error": "unknown_action"})
                return True
        except ValueError as exc:
            handler._json(400, {"ok": False, "error": str(exc)})
            return True
        handler._json(200, {"ok": True, "job": updated})
        return True

    handler._json(404, {"ok": False, "error": "unknown_ai_route"})
    return True
