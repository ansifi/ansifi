#!/usr/bin/env python3
"""Empever / Sevendyne hub on http://127.0.0.1:4040/

app.sevendyne.com/           operator
app.sevendyne.com/csr/       CSR Informatik
app.sevendyne.com/geoxyz/    GEOxyz
"""
from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from ai_review.http_api import handle as handle_ai_api
from desks import all_reports, one_report, works_board
from works_ops import list_contents, network_board, save_note
from ansif_books import load_compliance, save_compliance, save_upload, update_row, year_summary
from desk_chat import reply as desk_chat_reply
from mail_status import mail_feed
from gateway import is_local_path, match_upstream, proxy_http
from os_auth import (
    authenticate,
    can_manage_account,
    cookie_header,
    delete_account,
    find_account,
    is_operator_admin,
    is_super_admin,
    is_tenant_admin,
    parse_cookie,
    read_session_token,
    session_for_account,
    sign_session,
    update_account,
    workspace_accounts,
)
from ai_review.operates_accounts import active_nested_employers
from tenants import (
    all_clients,
    get as get_tenant,
    hostname,
    is_lan_hub_host,
    is_nested_employer,
    is_saas_tenant,
    proxy_headers,
    public_brand,
    resolve as resolve_tenant,
    split_path,
)

ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
PORT = 4040
PHONE_MDNS = "ansif-workspace.local"


def _lan_ipv4s() -> list[str]:
    skip_prefix = ("172.", "127.", "169.254.")
    found: list[str] = []
    for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
        ip = info[4][0]
        if ip.startswith(skip_prefix):
            continue
        if ip not in found:
            found.append(ip)
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        ip = probe.getsockname()[0]
        probe.close()
        if ip and not ip.startswith(skip_prefix) and ip not in found:
            found.insert(0, ip)
        elif ip in found:
            found.remove(ip)
            found.insert(0, ip)
    except OSError:
        pass
    return found


def phone_urls() -> dict:
    ips = _lan_ipv4s()
    mdns = f"http://{PHONE_MDNS}:4040/"
    host = f"http://{socket.gethostname().split('.')[0]}.local:4040/"
    ip_urls = [f"http://{ip}:4040/" for ip in ips]
    return {
        "ok": True,
        "url": mdns,
        "mdns": mdns,
        "hostname": host,
        "lan": ip_urls[0] if ip_urls else mdns,
        "urls": [mdns, host, *ip_urls],
    }


WORKS_APP = {
    "analysis": "/app/analysis.html",
    "content": "/app/content.html",
    "network": "/app/network.html",
    "operate": "/app/operate.html",
    "automate": "/app/",
}


def _workspace_app_id(path: str) -> str | None:
    p = path.split("?", 1)[0].rstrip("/") or "/"
    table = {
        "/apps/analysis": "analysis",
        "/apps/content": "content",
        "/apps/network": "network",
        "/apps/automate": "automate",
        "/apps/operate": "operate",
    }
    return table.get(p)


def works_app_location(path: str) -> str | None:
    """Old /apps/analysis/ stubs redirect into the shared /app/ desk screens."""
    app_id = _workspace_app_id(path)
    if not app_id:
        return None
    loc = WORKS_APP[app_id]
    query = urlparse(path).query
    if query:
        loc += ("&" if "?" in loc else "?") + query
    return loc


SESSION_FILE = ROOT / "session.json"
# Stop after the last browser tab goes away (presence.js). Not armed until a tab pings.
IDLE_AFTER_EMPTY_SEC = 8.0
TAB_STALE_SEC = 45.0
_tabs: dict[str, float] = {}
_tabs_lock = threading.Lock()
_presence_armed = False


def _note_tab(tab_id: str) -> None:
    global _presence_armed
    tid = (tab_id or "").strip()
    if not tid:
        return
    _presence_armed = True
    with _tabs_lock:
        _tabs[tid] = time.monotonic()


def _drop_tab(tab_id: str) -> None:
    tid = (tab_id or "").strip()
    if not tid:
        return
    with _tabs_lock:
        _tabs.pop(tid, None)


def _live_tab_count() -> int:
    now = time.monotonic()
    with _tabs_lock:
        for tid, seen in list(_tabs.items()):
            if now - seen > TAB_STALE_SEC:
                del _tabs[tid]
        return len(_tabs)


def _idle_watchdog() -> None:
    empty_since: float | None = None
    while True:
        time.sleep(2)
        if not _presence_armed:
            continue
        if _live_tab_count() > 0:
            empty_since = None
            continue
        if empty_since is None:
            empty_since = time.monotonic()
        elif time.monotonic() - empty_since >= IDLE_AFTER_EMPTY_SEC:
            print("No browser tabs — stopping hub.", flush=True)
            os._exit(0)


def _account_public(row: dict) -> dict:
    return {
        "name": row.get("full_name") or row.get("name") or row["username"],
        "username": row["username"],
        "password": row.get("password") or "",
        "tenant": str(row.get("tenant") or row["username"]),
    }


def _probe(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.4):
            return True
    except OSError:
        return False


def confidential_operates_path(raw_path: str) -> bool:
    """Tenant Operates records (invoices, payouts, ledgers). Super admin stays off these."""
    path = (raw_path or "").split("?", 1)[0]
    stripped = path.rstrip("/") or "/"
    if stripped in {
        "/django/dashboard/admin",
        "/hr/django/dashboard/admin",
        "/dashboard/admin",
    }:
        return False
    lowered = path.lower()
    if lowered == "/hrms" or lowered.startswith("/hrms/") or lowered.startswith("/hr/hrms"):
        return True
    if "/portal/admin" in lowered:
        return True
    if lowered == "/clients" or lowered.startswith("/clients/"):
        return True
    return False


def platform_operates_url(username: str, tenant_slug: str = "") -> str:
    uname = quote((username or "empever").strip() or "empever")
    loc = f"/django/dashboard/admin/?portal_username={uname}&dyne_embed=1"
    slug = (tenant_slug or "").strip().strip("/")
    if slug:
        return f"/{slug}{loc}"
    return loc


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        __import__("sys").stderr.write("[empever] " + (fmt % args) + "\n")

    def _send_works_app(self, path: str) -> None:
        rel = path.split("?", 1)[0][len("/app") :].lstrip("/") or "index.html"
        if rel in {"", "."}:
            rel = "index.html"
        if ".." in rel or rel.startswith("/"):
            self.send_error(404, "Not found")
            return
        target = (ROOT / "app" / rel).resolve()
        base = (ROOT / "app").resolve()
        if target != base and base not in target.parents:
            self.send_error(404, "Not found")
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self.send_error(404, "Not found")
            return
        suffix = target.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".svg": "image/svg+xml",
            ".png": "image/png",
        }.get(suffix, "application/octet-stream")
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def end_headers(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in {
            "/",
            "/index.html",
            "/dashboard.js",
            "/dashboard.css",
            "/analyse/",
            "/analyse/index.html",
            "/app.js",
            "/app.css",
            "/auth/",
            "/auth/index.html",
            "/operates/overview.html",
            "/operates/overview.js",
        }:
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        self._dispatch()

    def do_HEAD(self) -> None:
        self._dispatch()

    def do_POST(self) -> None:
        self._dispatch()

    def do_PUT(self) -> None:
        self._dispatch()

    def do_PATCH(self) -> None:
        self._dispatch()

    def do_DELETE(self) -> None:
        self._dispatch()

    def do_OPTIONS(self) -> None:
        self._dispatch()

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode() or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _read_upload(self) -> tuple[str, bytes]:
        ctype = self.headers.get("Content-Type") or ""
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length > 0 else b""
        if "multipart/form-data" not in ctype:
            return "", raw
        m = re.search(r"boundary=([^;]+)", ctype)
        if not m:
            return "", b""
        boundary = m.group(1).strip().strip('"').encode()
        for part in raw.split(b"--" + boundary):
            if b"filename=" not in part:
                continue
            head, _, body = part.partition(b"\r\n\r\n")
            body = body.rstrip(b"\r\n")
            if body.endswith(b"--"):
                body = body[:-2].rstrip(b"\r\n")
            hm = re.search(br'filename="([^"]+)"', head)
            name = hm.group(1).decode("utf-8", "replace") if hm else "statement.pdf"
            return name, body
        return "", b""

    def _json(self, code: int, payload: dict, *, set_cookie: str | None = None) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if set_cookie:
            self.send_header("Set-Cookie", set_cookie)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _send_auth_page(self) -> None:
        row = getattr(self, "empever_tenant_row", None)
        chrome = public_brand(self.headers.get("Host") or "", row)
        html = (ROOT / "auth" / "index.html").read_text(encoding="utf-8")
        html = html.replace("{{BRAND}}", chrome["title"]).replace("{{MARK}}", chrome["mark"][:1] or "E")
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if getattr(self, "_stale_workspace", False):
            self.send_header("Set-Cookie", cookie_header(None, clear=True))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _auth(self) -> dict | None:
        token = parse_cookie(self.headers.get("Cookie") or "")
        return read_session_token(token)

    def _clients_payload(self) -> list[dict]:
        return [
            {
                "id": row["id"],
                "name": row["name"],
                "slug": row["slug"],
                "kind": row.get("kind") or "employer",
                "crm_subdir": row["crm_subdir"],
                "payroll_db": row["payroll_db"],
            }
            for row in all_clients()
        ]

    def _session_body(self, auth: dict, current_id: str) -> dict:
        row = get_tenant(current_id) or get_tenant("sevendyne")
        host = self.headers.get("Host") or ""
        chrome = public_brand(host, row)
        uname = str(auth.get("username") or "")
        super_admin = is_super_admin(uname)
        operator = is_operator_admin(uname, str(auth.get("tenant") or ""))
        return {
            "ok": True,
            "current": row["id"],
            "name": row["name"],
            "slug": row["slug"],
            "base": ("/" + row["slug"]) if row["slug"] else "",
            "brand": chrome["title"],
            "brand_mark": chrome["mark"],
            "hide_platform": chrome["hide_platform"],
            "plan": row.get("plan") or "standard",
            "white_label": bool(row.get("white_label")),
            "kind": row.get("kind") or "employer",
            "payroll_db": row.get("payroll_db") or row["id"],
            "is_admin": operator,
            "is_super_admin": super_admin,
            "desk": auth.get("desk") or ("admin" if operator else "client"),
            "portal_username": auth.get("portal_username") or uname,
            "username": uname,
            "clients": self._clients_for(auth, row),
            "accounts": workspace_accounts(uname),
        }

    def _mine(self, auth: dict) -> dict | None:
        return get_tenant(str(auth.get("tenant") or "")) or get_tenant(str(auth.get("username") or ""))

    def _can_open(self, auth: dict | None, row: dict | None) -> bool:
        if not auth or not row:
            return False
        uname = str(auth.get("username") or "")
        if is_super_admin(uname):
            return is_saas_tenant(row)
        if is_tenant_admin(uname, str(auth.get("tenant") or "")):
            mine = self._mine(auth)
            return bool(mine and (row["id"] == mine["id"] or is_nested_employer(mine, row)))
        mine = self._mine(auth)
        return bool(mine and mine["id"] == row["id"])

    def _clients_for(self, auth: dict, row: dict) -> list[dict]:
        clients = self._clients_payload()
        uname = str(auth.get("username") or "")
        if is_super_admin(uname):
            return [c for c in clients if is_saas_tenant(get_tenant(c["id"]))]
        if is_tenant_admin(uname, str(auth.get("tenant") or "")):
            mine = self._mine(auth) or row
            allowed = {mine["id"]} | {n["id"] for n in active_nested_employers(mine["id"])}
            return [c for c in clients if c["id"] in allowed]
        return [c for c in clients if c["id"] == row["id"]]

    def _tenant_public(self, row: dict) -> dict:
        host = self.headers.get("Host") or ""
        chrome = public_brand(host, row)
        return {
            "ok": True,
            "id": row["id"],
            "name": row["name"],
            "slug": row["slug"],
            "kind": row.get("kind") or "employer",
            "plan": row.get("plan") or "standard",
            "white_label": bool(row.get("white_label")),
            "brand": chrome["title"],
            "brand_mark": chrome["mark"],
            "hide_platform": chrome["hide_platform"],
            "payroll_db": row.get("payroll_db") or row["id"],
        }

    def _session_current_file(self) -> str:
        try:
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return ""
        if not isinstance(data, dict):
            return ""
        wanted = str(data.get("current") or "").strip().lower()
        row = get_tenant(wanted)
        return row["id"] if row else ""

    def _current_from_request(self, auth: dict | None) -> str:
        qs = parse_qs(urlparse(self.path).query)
        hinted = (qs.get("tenant") or qs.get("client") or [""])[0].strip().lower()
        header = (self.headers.get("X-Empever-Tenant") or "").strip().lower()
        resolved = getattr(self, "empever_tenant_row", None)
        path_tenant = getattr(self, "empever_tenant", "") or ""
        if auth:
            for raw in (path_tenant, hinted, header, self._session_current_file()):
                row = get_tenant(raw)
                if row and self._can_open(auth, row):
                    return row["id"]
            if resolved and self._can_open(auth, resolved):
                return resolved["id"]
            mine = self._mine(auth)
            if mine:
                return mine["id"]
        if resolved:
            return resolved["id"]
        return "sevendyne"

    def _tab_id(self) -> str:
        qs = parse_qs(urlparse(self.path).query)
        tid = (qs.get("id") or [""])[0].strip()
        if tid:
            return tid
        if self.command in {"POST", "PUT", "PATCH"}:
            return str(self._read_json().get("id") or "").strip()
        return ""

    def _handle_api(self) -> bool:
        path = self.path.split("?", 1)[0]
        if path in {"/phone", "/api/phone"} and self.command in {"GET", "HEAD"}:
            self._json(200, phone_urls())
            return True
        if path == "/api/presence" and self.command in {"GET", "POST"}:
            _note_tab(self._tab_id())
            self._json(200, {"ok": True})
            return True
        if path == "/api/presence/bye" and self.command in {"GET", "POST"}:
            _drop_tab(self._tab_id())
            self._json(200, {"ok": True})
            return True
        if path == "/api/tenant" and self.command == "GET":
            row = getattr(self, "empever_tenant_row", None)
            if not row:
                self._json(404, {"ok": False, "error": "unknown_tenant"})
                return True
            self._json(200, self._tenant_public(row))
            return True
        if path == "/api/auth/login" and self.command == "POST":
            body = self._read_json()
            user = authenticate(str(body.get("username") or ""), str(body.get("password") or ""))
            if not user:
                self._json(401, {"ok": False, "error": "Invalid username or password"})
                return True
            token = sign_session(user)
            self._json(200, {"ok": True, "user": user}, set_cookie=cookie_header(token))
            return True
        if path == "/api/auth/logout" and self.command == "POST":
            self._json(200, {"ok": True}, set_cookie=cookie_header(None, clear=True))
            return True
        if path == "/api/auth/me" and self.command == "GET":
            if getattr(self, "_stale_workspace", False):
                self._json(401, {"ok": False}, set_cookie=cookie_header(None, clear=True))
                return True
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False})
                return True
            uname = str(auth.get("username") or "")
            auth = {
                **auth,
                "is_super_admin": is_super_admin(uname),
                "is_admin": is_operator_admin(uname, str(auth.get("tenant") or "")),
            }
            self._json(200, {"ok": True, "user": auth})
            return True
        if path == "/api/session" and self.command == "GET":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            current = self._current_from_request(auth)
            self._json(200, self._session_body(auth, current))
            return True
        if path == "/api/session" and self.command == "PUT":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            uname = str(auth.get("username") or "")
            if not is_super_admin(uname):
                self._json(403, {"ok": False, "error": "super_admin_only"})
                return True
            body = self._read_json()
            wanted = str(body.get("current") or "").strip().lower()
            row = get_tenant(wanted)
            if not row or not self._can_open(auth, row):
                self._json(403, {"ok": False, "error": "forbidden"})
                return True
            SESSION_FILE.write_text(json.dumps({"current": row["id"]}, indent=2) + "\n", encoding="utf-8")
            self._json(200, self._session_body(auth, row["id"]))
            return True
        if path == "/api/accounts/login" and self.command == "POST":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            admin = str(auth.get("username") or "")
            if not is_operator_admin(admin, str(auth.get("tenant") or "")):
                self._json(403, {"ok": False, "error": "admin_only"})
                return True
            body = self._read_json()
            wanted = str(body.get("username") or "").strip()
            row = find_account(wanted)
            if not row or not can_manage_account(admin, row["username"]):
                self._json(403, {"ok": False, "error": "forbidden"})
                return True
            user = session_for_account(row)
            token = sign_session(user)
            self._json(200, {"ok": True, "user": user}, set_cookie=cookie_header(token))
            return True
        if path == "/api/accounts" and self.command == "PATCH":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            admin = str(auth.get("username") or "")
            body = self._read_json()
            updated = update_account(
                admin,
                str(body.get("username") or ""),
                name=str(body.get("name") or ""),
                password=str(body.get("password") or ""),
            )
            if not updated:
                self._json(403, {"ok": False, "error": "forbidden"})
                return True
            self._json(200, {"ok": True, "account": _account_public(updated)})
            return True
        if path == "/api/accounts" and self.command == "DELETE":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            admin = str(auth.get("username") or "")
            body = self._read_json()
            if not delete_account(admin, str(body.get("username") or "")):
                self._json(403, {"ok": False, "error": "forbidden"})
                return True
            self._json(200, {"ok": True})
            return True
        if path == "/api/desk-reports" and self.command == "GET":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            qs = parse_qs(urlparse(self.path).query)
            app_id = (qs.get("app") or [""])[0].strip().lower()
            if app_id:
                row = one_report(app_id)
                if not row:
                    self._json(404, {"ok": False, "error": "unknown_app"})
                    return True
                self._json(200, {"ok": True, "report": row, "reports": [row]})
                return True
            self._json(200, {"ok": True, "reports": all_reports()})
            return True
        if path == "/api/works" and self.command == "GET":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            self._json(200, {"ok": True, **works_board()})
            return True
        if path == "/api/works/books" and self.command == "GET":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            year = (parse_qs(urlparse(self.path).query).get("year") or [""])[0]
            y = int(year) if year.isdigit() else None
            self._json(200, year_summary(y))
            return True
        if path == "/api/works/books/upload" and self.command == "POST":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            name, blob = self._read_upload()
            if not blob:
                self._json(400, {"ok": False, "error": "empty"})
                return True
            try:
                out = save_upload(name, blob, owner="Ansif")
            except Exception as exc:
                self._json(400, {"ok": False, "error": str(exc)})
                return True
            self._json(200 if out.get("ok") else 400, out)
            return True
        if path == "/api/works/books/row" and self.command == "POST":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            body = self._read_json()
            out = update_row(
                str(body.get("hash") or ""),
                str(body.get("category") or ""),
                str(body.get("purpose") or ""),
            )
            self._json(200 if out.get("ok") else 400, out)
            return True
        if path == "/api/works/compliance" and self.command == "GET":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            self._json(200, load_compliance())
            return True
        if path == "/api/works/compliance" and self.command == "POST":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            body = self._read_json()
            mods = body.get("modules") if isinstance(body.get("modules"), list) else []
            self._json(200, save_compliance(mods))
            return True
        if path == "/api/works/contents" and self.command == "GET":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            self._json(200, list_contents())
            return True
        if path == "/api/works/network" and self.command == "GET":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            self._json(200, network_board())
            return True
        if path == "/api/works/note" and self.command == "POST":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            body = self._read_json()
            out = save_note(
                str(body.get("title") or ""),
                str(body.get("body") or ""),
                str(body.get("work") or ""),
            )
            self._json(200 if out.get("ok") else 400, out)
            return True
        if path == "/api/desk-mail" and self.command == "GET":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            self._json(200, mail_feed())
            return True
        if path == "/api/desk-chat" and self.command == "POST":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            body = self._read_json()
            try:
                hist = body.get("history") if isinstance(body.get("history"), list) else []
                out = desk_chat_reply(
                    str(body.get("prompt") or ""),
                    str(body.get("desk") or ""),
                    hist,
                )
            except Exception as exc:
                out = {
                    "ok": True,
                    "text": "Desk is up. I could not read status just now — ask again in a few seconds.",
                    "error": str(exc).split("\n")[0][:180],
                }
            self._json(200 if out.get("ok") else 400, out)
            return True
        if path == "/api/status" and self.command == "GET":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            coding_api = _probe(8006)
            leads = _probe(6175)
            payroll = _probe(3001)
            automate = _probe(5055) or _probe(5001)
            self._json(
                200,
                {
                    "coding": coding_api,
                    "coding_api": coding_api,
                    "coding_ui": coding_api,
                    "leads": leads,
                    "payroll": payroll,
                    "automate": automate,
                },
            )
            return True
        if path == "/api/operates" and self.command == "GET":
            auth = self._auth()
            if not auth:
                self._json(401, {"ok": False, "error": "login_required"})
                return True
            try:
                data = json.loads((ROOT / "operates.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            self._json(200, data)
            return True
        if handle_ai_api(self):
            return True
        return False

    def _dispatch(self) -> None:
        host = self.headers.get("Host") or ""
        row = resolve_tenant(host=host, path=self.path)
        self.empever_tenant_row = row
        if row is None:
            self.send_error(404, "Unknown tenant for this host")
            return
        auth = self._auth()
        host_name = hostname(host)
        self._stale_workspace = False
        if (
            auth
            and not is_super_admin(str(auth.get("username") or ""))
            and not is_lan_hub_host(host_name)
        ):
            mine = get_tenant(str(auth.get("tenant") or auth.get("username") or ""))
            if mine and mine["id"] != row["id"] and mine.get("payroll_db") != row.get("payroll_db"):
                self._stale_workspace = True
                if not _auth_open_path(self.path):
                    self.send_response(302)
                    self.send_header("Location", "/auth/")
                    self.send_header("Set-Cookie", cookie_header(None, clear=True))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return
                auth = None
        tenant, inner = split_path(self.path)
        self.empever_tenant = row["id"] if not tenant else tenant
        original = self.path
        self.path = inner

        if self._handle_api():
            return

        # empever/ansif cookie: bounce HRMS + /portal/admin money pages to the
        # empty platform Operates card. Tenant admins still use /hrms.
        if auth and is_super_admin(str(auth.get("username") or "")) and confidential_operates_path(self.path):
            self.path = original
            self._redirect(platform_operates_url(str(auth.get("username") or "empever"), tenant))
            return

        path = self.path.split("?", 1)[0]
        if path.rstrip("/") == "/jobs/backend/admin_dashboard":
            self._redirect("/")
            return
        if path in {"/auth", "/auth/"}:
            return self._send_auth_page()
        if path == "/app" or path.startswith("/app/"):
            if not auth:
                loc = "/auth/"
                if tenant:
                    loc = f"/{tenant}/auth/"
                self._redirect(loc)
                return
            return self._send_works_app(path)
        if path in {"/", "/index.html"}:
            if not auth:
                loc = "/auth/"
                if tenant:
                    loc = f"/{tenant}/auth/"
                self._redirect(loc)
                return
            self.path = "/index.html"
            if self.command == "HEAD":
                return SimpleHTTPRequestHandler.do_HEAD(self)
            return SimpleHTTPRequestHandler.do_GET(self)
        if path in {"/analyse", "/analyse/"}:
            self.path = "/analyse/index.html"
            return SimpleHTTPRequestHandler.do_GET(self)
        dest = works_app_location(self.path)
        if dest:
            if not auth:
                loc = "/auth/"
                if tenant:
                    loc = f"/{tenant}/auth/"
                self._redirect(loc)
                return
            return self._redirect(dest)
        if is_local_path(self.path):
            if path in {"/", "/index.html"}:
                self.path = "/index.html"
            if self.command == "GET":
                return SimpleHTTPRequestHandler.do_GET(self)
            if self.command == "HEAD":
                return SimpleHTTPRequestHandler.do_HEAD(self)
            self.send_error(405)
            return
        matched = match_upstream(self.path)
        if not matched:
            self.send_error(404, "Not an Empever path")
            return
        _host, port, upstream = matched
        self.path = original
        extra = proxy_headers(row)
        proxy_http(self, _host, port, upstream, extra_headers=extra)


def _auth_open_path(path: str) -> bool:
    p = path.split("?", 1)[0]
    if p in {
        "/api/auth/logout",
        "/api/auth/login",
        "/api/auth/me",
        "/api/tenant",
        "/api/phone",
        "/phone",
        "/api/presence",
        "/api/presence/bye",
        "/presence.js",
        "/dashboard.js",
        "/dashboard.css",
        "/favicon.ico",
        "/favicon.svg",
        "/auth/login.js",
    }:
        return True
    if p.startswith("/auth"):
        return True
    if p.startswith("/dashboard.js") or p.startswith("/dashboard.css"):
        return True
    return False


def main() -> None:
    host = (os.environ.get("ANSIF_HUB_HOST") or "127.0.0.1").strip() or "127.0.0.1"
    if host in {"127.0.0.1", "localhost"}:
        threading.Thread(target=_idle_watchdog, name="hub-idle", daemon=True).start()
    httpd = ThreadingHTTPServer((host, PORT), Handler)
    print(f"Empever: http://{host}:{PORT}/", flush=True)
    print("Host: dummy.empever.com → Dummy sqlite. Path /csr/ only on platform/Sevendyne hosts.", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
