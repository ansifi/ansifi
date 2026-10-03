"""Reverse-proxy Empever apps onto the dashboard port (4040).

Backends still listen on loopback. The browser only needs http://127.0.0.1:4040/
"""
from __future__ import annotations

import http.client
import select
import socket
from typing import Optional

HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}

LOCAL_API = {
    "/api/status",
    "/api/operates",
    "/api/session",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/tenant",
    "/api/accounts",
    "/api/accounts/login",
    "/api/ai",
    "/api/presence",
    "/api/presence/bye",
    "/api/desk-reports",
    "/api/desk-chat",
    "/api/desk-mail",
    "/api/works",
}
LOCAL_FILES = {
    "/",
    "/index.html",
    "/dashboard.js",
    "/dashboard.css",
    "/operates.json",
    "/favicon.ico",
    "/favicon.svg",
    "/app.js",
    "/app.css",
    "/analyse",
    "/analyse/",
    "/analyse/index.html",
    "/auth",
    "/auth/",
    "/auth/index.html",
    "/auth/login.js",
    "/presence.js",
    "/operates/overview.html",
    "/operates/overview.js",
    "/desk-app.js",
    "/desk-app.css",
    "/apps/analysis",
    "/apps/analysis/",
    "/apps/content",
    "/apps/content/",
    "/apps/network",
    "/apps/network/",
    "/apps/automate",
    "/apps/automate/",
    "/apps/operate",
    "/apps/operate/",
}

PAYROLL_PREFIXES = ("/hrms", "/_next", "/__nextjs", "/login", "/clients")
DJANGO_PAGE_PREFIXES = ("/portal", "/media", "/accounts")


def is_local_path(path: str) -> bool:
    p = path.split("?", 1)[0]
    if p.startswith("/static/portal") or p.startswith("/static/admin"):
        return False
    if p in LOCAL_API or p in LOCAL_FILES:
        return True
    if p.startswith("/api/works"):
        return True
    if p.startswith("/api/ai"):
        return True
    if p.startswith("/analyse"):
        return True
    if p.startswith("/apps/analysis") or p.startswith("/apps/content"):
        return True
    if p.startswith("/apps/network") or p.startswith("/apps/automate"):
        return True
    if p.startswith("/apps/operate"):
        return True
    if p == "/app" or p.startswith("/app/"):
        return True
    if p.startswith("/auth/"):
        return True
    if p.startswith("/operates/"):
        return True
    if p.startswith("/static/"):
        return True
    return False


def match_upstream(raw_path: str) -> Optional[tuple[str, int, str]]:
    """Map a public path to (host, port, upstream path including query)."""
    path, _, query = raw_path.partition("?")
    suffix = f"?{query}" if query else ""

    def keep(port: int) -> tuple[str, int, str]:
        return ("127.0.0.1", port, path + suffix)

    def strip(prefix: str, port: int) -> tuple[str, int, str]:
        rest = path[len(prefix) :] or "/"
        if not rest.startswith("/"):
            rest = "/" + rest
        return ("127.0.0.1", port, rest + suffix)

    if path == "/apps/coding-api" or path.startswith("/apps/coding-api/"):
        return strip("/apps/coding-api", 8006)
    if path == "/apps/coding" or path.startswith("/apps/coding/"):
        return keep(5176)
    if path == "/apps/desk" or path.startswith("/apps/desk/"):
        # Vite serves with VITE_BASE_PATH=/apps/desk/ — keep the prefix.
        return keep(6175)
    # Leads public/js plus a Dockerfile.free build that used VITE_BASE_PATH=/.
    if path.startswith("/assets/") or path.startswith("/js/"):
        return keep(6175)
    if path == "/apps/playwright" or path.startswith("/apps/playwright/"):
        return strip("/apps/playwright", 5001)
    # Jobs portal (workspace accounts) — nginx on :3080
    if path == "/jobs" or path.startswith("/jobs/"):
        return keep(3080)
    if path.startswith("/static/portal") or path.startswith("/static/admin"):
        return keep(8008)
    if path == "/dashboard" or path.startswith("/dashboard/"):
        return keep(8008)
    # Browser iframe uses /hr/django on public hosts, /django on localhost.
    if path == "/hr/django" or path.startswith("/hr/django/"):
        return strip("/hr/django", 8008)
    if path == "/django" or path.startswith("/django/"):
        return strip("/django", 8008)
    if path.startswith(DJANGO_PAGE_PREFIXES):
        return keep(8008)
    if path == "/hr" or path.startswith("/hr/"):
        return strip("/hr", 3001)
    if path.startswith(PAYROLL_PREFIXES):
        return keep(3001)
    if path.startswith("/api/"):
        return keep(6175)
    return None


def _forward_headers(handler) -> dict[str, str]:
    out = {}
    for key, value in handler.headers.items():
        if key.lower() in HOP or key.lower() == "host":
            continue
        out[key] = value
    return out


def proxy_http(handler, host: str, port: int, upstream_path: str, extra_headers: Optional[dict[str, str]] = None) -> None:
    if handler.headers.get("Upgrade", "").lower() == "websocket":
        _tunnel_ws(handler, host, port, upstream_path)
        return

    length = int(handler.headers.get("Content-Length") or 0)
    body = handler.rfile.read(length) if length > 0 else None
    headers = _forward_headers(handler)
    headers["Host"] = f"{host}:{port}"
    headers["X-Forwarded-Host"] = handler.headers.get("Host") or "127.0.0.1:4040"
    headers["X-Forwarded-Proto"] = "http"
    if extra_headers:
        for key, value in extra_headers.items():
            if value:
                headers[key] = value

    conn = http.client.HTTPConnection(host, port, timeout=300)
    try:
        conn.request(handler.command, upstream_path, body=body, headers=headers)
        resp = conn.getresponse()
        handler.send_response(resp.status, resp.reason)
        for key, value in resp.getheaders():
            if key.lower() in HOP:
                continue
            handler.send_header(key, value)
        handler.send_header("X-Empever-Gateway", f"{host}:{port}")
        handler.end_headers()
        while True:
            chunk = resp.read(65536)
            if not chunk:
                break
            handler.wfile.write(chunk)
        handler.wfile.flush()
    except OSError:
        try:
            handler.send_error(502, "Upstream is not running")
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
    finally:
        conn.close()


def _tunnel_ws(handler, host: str, port: int, upstream_path: str) -> None:
    lines = [f"{handler.command} {upstream_path} HTTP/1.1"]
    for key, value in handler.headers.items():
        if key.lower() == "host":
            lines.append(f"Host: {host}:{port}")
        else:
            lines.append(f"{key}: {value}")
    blob = ("\r\n".join(lines) + "\r\n\r\n").encode("latin1")
    upstream = socket.create_connection((host, port), timeout=15)
    try:
        upstream.sendall(blob)
        client = handler.connection
        handler.close_connection = True
        while True:
            readable, _, _ = select.select([client, upstream], [], [], 300)
            if not readable:
                break
            for src in readable:
                dest = upstream if src is client else client
                data = src.recv(65536)
                if not data:
                    return
                dest.sendall(data)
    finally:
        try:
            upstream.close()
        except OSError:
            pass
