"""Hub tenants: Host first, then path slug. Nested /csr/ is not a SaaS subdomain."""
from __future__ import annotations

import ipaddress
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESERVED = frozenset(
    {
        "api",
        "apps",
        "analyse",
        "auth",
        "hrms",
        "login",
        "django",
        "clients",
        "jobs",
        "static",
        "assets",
        "js",
        "_next",
        "__nextjs",
        "favicon.ico",
        "favicon.svg",
        "dashboard.js",
        "dashboard.css",
        "app.js",
        "app.css",
        "index.html",
        "operates.json",
        "operates",
    }
)
PLATFORM_HOSTS = frozenset(
    {
        "127.0.0.1",
        "localhost",
        "0.0.0.0",
        "167.233.65.24",
        "app.empever.com",
        "empever.com",
        "www.empever.com",
    }
)
SAAS_PARENT = "empever.com"


def hostname(host: str) -> str:
    return (host or "").split(":")[0].strip().lower()


def is_lan_hub_host(host: str) -> bool:
    """Phone / mDNS / private IP — same operator desk as localhost."""
    h = hostname(host)
    if h in PLATFORM_HOSTS:
        return True
    if h.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(h)
    except ValueError:
        return False
    return bool(ip.is_private or ip.is_loopback or ip.is_link_local)


@lru_cache(maxsize=1)
def _rows() -> tuple[dict, ...]:
    raw = (ROOT / "tenants.json").read_text(encoding="utf-8")
    lines = [ln for ln in raw.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    data = json.loads("\n".join(lines))
    if not isinstance(data, list):
        raise ValueError("tenants.json must be a list")
    return tuple(data)


def _normalize(row: dict) -> dict:
    brand = row.get("brand") if isinstance(row.get("brand"), dict) else {}
    domains = [hostname(d) for d in (row.get("domains") or []) if d]
    return {
        "id": str(row["id"]),
        "name": str(row["name"]),
        "slug": str(row.get("slug") or ""),
        "crm_subdir": str(row.get("crm_subdir") or row["id"]),
        "payroll_db": str(row.get("payroll_db") or row["id"]),
        "managed_by": str(row.get("managed_by") or "sevendyne"),
        "kind": str(row.get("kind") or ("saas" if not row.get("slug") else "employer")),
        "plan": str(row.get("plan") or "standard"),
        "white_label": bool(row.get("white_label")),
        "hide_platform": bool(row.get("hide_platform")),
        "brand_title": str(brand.get("title") or row.get("name") or "Empever"),
        "brand_mark": str(brand.get("mark") or "E")[:1].upper() or "E",
        "domains": domains,
        "company_hint": str(row.get("company_hint") or ""),
    }


def all_clients() -> list[dict]:
    return [_normalize(row) for row in _rows()]


def slugs() -> frozenset[str]:
    return frozenset(c["slug"] for c in all_clients() if c["slug"])


def get(client_id: str) -> dict | None:
    key = (client_id or "").strip().lower()
    if not key:
        return None
    for row in all_clients():
        if row["id"] == key or row["slug"] == key:
            return row
    return None


def is_saas_tenant(row: dict | None) -> bool:
    if not row:
        return False
    return row.get("kind") == "saas" or row["payroll_db"] == row["id"]


def nested_employers(parent_id: str) -> list[dict]:
    parent = get(parent_id)
    if not parent:
        return []
    return [
        row
        for row in all_clients()
        if row["id"] != parent["id"]
        and row.get("kind") == "employer"
        and (
            row.get("managed_by") == parent["id"]
            or row.get("payroll_db") == parent.get("payroll_db")
        )
    ]


def is_nested_employer(parent: dict | None, row: dict | None) -> bool:
    if not parent or not row or row["id"] == parent["id"]:
        return False
    return row.get("kind") == "employer" and (
        row.get("managed_by") == parent["id"] or row.get("payroll_db") == parent.get("payroll_db")
    )


def split_path(raw_path: str) -> tuple[str, str]:
    """Return (tenant_slug_or_empty, path_for_router including query)."""
    path, _, query = raw_path.partition("?")
    suffix = f"?{query}" if query else ""
    stripped = path.lstrip("/")
    if not stripped:
        return "", "/" + suffix
    first, _, rest = stripped.partition("/")
    if first.lower() in slugs() and first.lower() not in RESERVED:
        inner = "/" + rest if rest else "/"
        return first.lower(), inner + suffix
    return "", path + suffix


def home_path(client_id: str) -> str:
    row = get(client_id)
    if not row or not row["slug"]:
        return "/"
    return f"/{row['slug']}/"


def find_by_domain(host: str) -> dict | None:
    h = hostname(host)
    if not h:
        return None
    for row in all_clients():
        if h in row["domains"]:
            return row
    if h.endswith("." + SAAS_PARENT):
        slug = h[: -(len(SAAS_PARENT) + 1)]
        row = get(slug)
        if is_saas_tenant(row):
            return row
    return None


def _host_allows_path_tenant(host: str, row: dict) -> bool:
    h = hostname(host)
    if is_lan_hub_host(h):
        return True
    parent = find_by_domain(h)
    if not parent:
        return False
    if row["id"] == parent["id"]:
        return True
    return row.get("managed_by") == parent["id"] or row.get("payroll_db") == parent.get("payroll_db")


def resolve(*, host: str = "", path: str = "/") -> dict | None:
    """Host wins for SaaS domains. Path /csr/ only on platform or parent white-label host."""
    h = hostname(host)
    path_slug, _inner = split_path(path)
    if path_slug:
        row = get(path_slug)
        if row and _host_allows_path_tenant(h, row):
            return row
        if row:
            return None
    by_host = find_by_domain(h)
    if by_host:
        return by_host
    if is_lan_hub_host(h) or not h:
        return get("sevendyne")
    if "sevendyne" in h:
        return get("sevendyne")
    return None


def _chrome(title: str, mark: str, hide_platform: bool) -> dict:
    t = title or "EMPEVER"
    m = (mark or t[:1] or "E")[:1].upper()
    return {"title": t, "mark": m, "hide_platform": bool(hide_platform)}


def public_brand(host: str, tenant: dict | None) -> dict:
    """Chrome follows Host: white-label name, SaaS tenant name, or EMPEVER on platform hosts."""
    h = hostname(host)
    row = tenant or {}
    owner = find_by_domain(h) if h else None
    if owner and h and h not in PLATFORM_HOSTS:
        hide = bool(owner.get("hide_platform") or owner.get("white_label"))
        return _chrome(owner.get("brand_title") or owner.get("name") or "EMPEVER", owner.get("brand_mark") or "E", hide)
    if h in {"app.empever.com", "empever.com", "www.empever.com", "167.233.65.24"}:
        return _chrome("EMPEVER", "E", False)
    sevendyne = get("sevendyne") or {}
    if row.get("id") == "sevendyne" or row.get("managed_by") == "sevendyne":
        return _chrome(sevendyne.get("brand_title") or "Sevendyne", sevendyne.get("brand_mark") or "S", True)
    if row:
        return _chrome(row.get("brand_title") or row.get("name") or "EMPEVER", row.get("brand_mark") or "E", False)
    return _chrome("EMPEVER", "E", False)


def brand_for_host(host: str) -> str:
    return public_brand(host, resolve(host=host, path="/"))["title"]


def proxy_headers(tenant: dict | None) -> dict[str, str]:
    if not tenant:
        return {}
    return {
        "X-Empever-Tenant": tenant["id"],
        "X-Empever-Payroll-Db": tenant["payroll_db"],
        "X-Empever-Plan": tenant.get("plan") or "standard",
    }
