"""Dashboard OS login — seed workspace accounts (no jobs backend required)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

from tenants import get as get_tenant, home_path
from ai_review.operates_accounts import active_nested_employers

ROOT = Path(__file__).resolve().parent
SECRET_PATH = ROOT / ".run" / "auth-secret"
ACCOUNT_STORE = ROOT / ".run" / "accounts.json"
COOKIE_NAME = "empever_os"
TTL_SEC = 7 * 24 * 60 * 60

# Platform super admin can switch SaaS tenants. Tenant admins (Sevendyne, Dummy) share the same desk without the switcher.
SUPER_ADMIN_USERNAMES = frozenset({"empever", "ansif"})
STAFF_USERNAMES = frozenset({"sd_csr_001", "fathima", "sd_oovattil_001", "mgouse"})
SEED_ACCOUNTS = (
    {
        "username": "sevendyne",
        "aliases": ("sevendyne@local",),
        "full_name": "Sevendyne",
        "password": "7dyne123",
        "tenant": "sevendyne",
    },
    {
        "username": "empever",
        "aliases": ("empever@local",),
        "full_name": "EMPEVER Infoservices",
        "password": "ansif123$",
        "tenant": "sevendyne",
    },
    {
        "username": "ansif",
        "aliases": ("ansif@local",),
        "full_name": "Ansif",
        "password": "ansif123",
        "tenant": "sevendyne",
    },
    {
        "username": "csr",
        "aliases": (),
        "full_name": "CSR Informatik",
        "password": "csr123$",
        "tenant": "csr",
    },
    {
        "username": "sd_csr_001",
        "aliases": (),
        "full_name": "CSR Informatik",
        "password": "Payslip2026!",
        "tenant": "csr",
    },
    {
        "username": "quantyf",
        "aliases": (),
        "full_name": "QUANTYF",
        "password": "quantyf123$",
        "tenant": "quantyf",
    },
    {
        "username": "fathima",
        "aliases": (),
        "full_name": "QUANTYF",
        "password": "fathima123$",
        "tenant": "quantyf",
    },
    {
        "username": "geoxyz",
        "aliases": ("jan",),
        "full_name": "GEOxyz",
        "password": "geoxyz123$",
        "tenant": "geoxyz",
    },
    {
        "username": "ovt",
        "aliases": (),
        "full_name": "Oovattil",
        "password": "ovt123$",
        "tenant": "ovt",
    },
    {
        "username": "sd_oovattil_001",
        "aliases": (),
        "full_name": "Oovattil",
        "password": "Payslip2026!",
        "tenant": "ovt",
    },
    {
        "username": "crossdock",
        "aliases": (),
        "full_name": "CROSSDOCK",
        "password": "Crossdock123$",
        "tenant": "crossdock",
    },
    {
        "username": "mgouse",
        "aliases": (),
        "full_name": "CROSSDOCK",
        "password": "Mgouse123$",
        "tenant": "crossdock",
    },
    {
        "username": "dummy_client",
        "aliases": ("dummy", "dummy client", "client"),
        "full_name": "Dummy client",
        "password": "demo123$",
        "tenant": "dummy_client",
    },
)


def _secret() -> bytes:
    SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_PATH.is_file():
        raw = SECRET_PATH.read_bytes().strip()
        if raw:
            return raw
    raw = secrets.token_bytes(32)
    SECRET_PATH.write_bytes(raw)
    return raw


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def sign_session(payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(_secret(), body, hashlib.sha256).digest()
    return _b64(body) + "." + _b64(sig)


def read_session_token(token: str | None) -> dict | None:
    if not token or "." not in token:
        return None
    left, right = token.split(".", 1)
    try:
        body = _b64d(left)
        sig = _b64d(right)
    except (ValueError, OSError):
        return None
    expect = hmac.new(_secret(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expect):
        return None
    try:
        payload = json.loads(body.decode())
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        return None
    until = int(payload.get("until") or 0)
    if until < int(time.time()):
        return None
    return payload


def cookie_header(token: str | None, *, clear: bool = False) -> str:
    if clear or not token:
        return f"{COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax"
    return f"{COOKIE_NAME}={token}; Path=/; Max-Age={TTL_SEC}; HttpOnly; SameSite=Lax"


def parse_cookie(header: str, name: str = COOKIE_NAME) -> str | None:
    if not header:
        return None
    for part in header.split(";"):
        piece = part.strip()
        if piece.startswith(name + "="):
            return piece.split("=", 1)[1]
    return None


def is_super_admin(username: str) -> bool:
    return (username or "").strip().lower() in SUPER_ADMIN_USERNAMES


def is_tenant_admin(username: str, tenant: str | None = None) -> bool:
    uname = (username or "").strip().lower()
    if not uname or is_super_admin(uname):
        return False
    row = get_tenant(tenant or uname) or get_tenant(uname)
    if not row:
        return False
    return row.get("kind") == "saas" and uname in {row["id"], row.get("slug")}


def is_operator_admin(username: str, tenant: str | None = None) -> bool:
    return is_super_admin(username) or is_tenant_admin(username, tenant)


def _account_payload(row: dict, desk: str) -> dict:
    return {
        "name": row["full_name"],
        "username": row["username"],
        "password": row["password"],
        "tenant": str(row.get("tenant") or row["username"]),
        "desk": desk,
    }


def _names(row: dict) -> set[str]:
    names = {str(row["username"]).lower()}
    for alias in row.get("aliases") or ():
        names.add(str(alias).strip().lower())
    return {n for n in names if n}


def _empty_store() -> dict:
    return {"accounts": [], "deleted": []}


def _load_store() -> dict:
    try:
        data = json.loads(ACCOUNT_STORE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return _empty_store()
    if not isinstance(data, dict):
        return _empty_store()
    accounts = data.get("accounts") if isinstance(data.get("accounts"), list) else []
    deleted = data.get("deleted") if isinstance(data.get("deleted"), list) else []
    return {
        "accounts": [row for row in accounts if isinstance(row, dict)],
        "deleted": [str(name).strip().lower() for name in deleted if str(name).strip()],
    }


def _save_store(data: dict) -> None:
    ACCOUNT_STORE.parent.mkdir(parents=True, exist_ok=True)
    ACCOUNT_STORE.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _overlay_row(base: dict, extra: dict) -> dict:
    row = dict(base)
    if extra.get("username"):
        row["username"] = str(extra["username"]).strip()
    if extra.get("full_name") or extra.get("name"):
        row["full_name"] = str(extra.get("full_name") or extra.get("name")).strip()
    if extra.get("password"):
        row["password"] = str(extra["password"])
    if extra.get("tenant"):
        row["tenant"] = str(extra["tenant"]).strip().lower()
    aliases = extra.get("aliases")
    if isinstance(aliases, (list, tuple)):
        row["aliases"] = tuple(str(a).strip() for a in aliases if str(a).strip())
    return row


def live_accounts() -> list[dict]:
    store = _load_store()
    deleted = set(store["deleted"])
    seed_names = {str(row["username"]).lower() for row in SEED_ACCOUNTS}
    overlays: dict[str, dict] = {}
    extras: list[dict] = []
    for extra in store["accounts"]:
        uname = str(extra.get("username") or "").strip().lower()
        was = str(extra.get("was") or extra.get("username") or "").strip().lower()
        key = was or uname
        if not uname:
            continue
        if key in seed_names:
            overlays[key] = extra
        else:
            extras.append(extra)
    out: list[dict] = []
    seen: set[str] = set()
    for seed in SEED_ACCOUNTS:
        key = str(seed["username"]).lower()
        extra = overlays.get(key)
        uname = str(extra.get("username") or seed["username"]).strip().lower() if extra else key
        if key in deleted or uname in deleted:
            continue
        row = _overlay_row(seed, extra) if extra else dict(seed)
        out.append(row)
        seen.add(str(row["username"]).lower())
    for extra in extras:
        uname = str(extra.get("username") or "").strip().lower()
        if not uname or uname in seen or uname in deleted:
            continue
        out.append(
            {
                "username": str(extra["username"]).strip(),
                "aliases": tuple(extra.get("aliases") or ()),
                "full_name": str(extra.get("full_name") or extra.get("name") or extra["username"]).strip(),
                "password": str(extra.get("password") or ""),
                "tenant": str(extra.get("tenant") or extra["username"]).strip().lower(),
            }
        )
        seen.add(uname)
    return out


def find_account(username: str) -> dict | None:
    user = (username or "").strip().lower()
    if not user:
        return None
    for row in live_accounts():
        if user in _names(row):
            return row
    return None


def workspace_accounts(username: str) -> list[dict]:
    """Logins on this desk. Super admin does not see tenant passwords. Tenant admin: nested clients."""
    uname = (username or "").strip().lower()
    if is_super_admin(uname):
        return []
    if is_tenant_admin(uname):
        nested_ids = {row["id"] for row in active_nested_employers(uname)}
        out = []
        for row in live_accounts():
            tid = str(row.get("tenant") or row["username"])
            if tid not in nested_ids:
                continue
            if row["username"] in STAFF_USERNAMES:
                continue
            out.append(_account_payload(row, "client"))
        return out
    return []


def can_manage_account(admin: str, username: str) -> bool:
    wanted = (username or "").strip().lower()
    if not wanted or wanted in SUPER_ADMIN_USERNAMES:
        return False
    return any(str(row["username"]).lower() == wanted for row in workspace_accounts(admin))


def session_for_account(row: dict) -> dict:
    uname = row["username"]
    tenant = str(row.get("tenant") or uname)
    found = get_tenant(tenant) or get_tenant("sevendyne")
    tenant_id = found["id"] if found else tenant
    super_admin = is_super_admin(uname)
    operator = is_operator_admin(uname, tenant_id)
    if operator:
        desk = "admin"
    elif uname in STAFF_USERNAMES:
        desk = "staff"
    else:
        desk = "client"
    return {
        "username": uname,
        "role": "super_admin" if super_admin else ("admin" if operator else desk),
        "is_admin": operator,
        "is_super_admin": super_admin,
        "desk": desk,
        "portal_username": uname,
        "client_name": row["full_name"],
        "tenant": tenant_id,
        "home": home_path(tenant_id),
        "email": f"{uname}@local",
        "until": int(time.time()) + TTL_SEC,
    }


def update_account(admin: str, username: str, *, name: str = "", password: str = "") -> dict | None:
    current = find_account(username)
    if not current or not can_manage_account(admin, current["username"]):
        return None
    key = str(current["username"]).lower()
    store = _load_store()
    overlays = [
        row
        for row in store["accounts"]
        if str(row.get("username") or "").strip().lower() != key
        and str(row.get("was") or "").strip().lower() != key
    ]
    overlays.append(
        {
            "username": current["username"],
            "was": key,
            "full_name": (name or current["full_name"]).strip() or current["full_name"],
            "password": password or current["password"],
            "tenant": str(current.get("tenant") or current["username"]),
            "aliases": list(current.get("aliases") or ()),
        }
    )
    store["accounts"] = overlays
    _save_store(store)
    return find_account(current["username"])


def delete_account(admin: str, username: str) -> bool:
    current = find_account(username)
    if not current or not can_manage_account(admin, current["username"]):
        return False
    key = str(current["username"]).lower()
    if is_tenant_admin(current["username"], str(current.get("tenant") or current["username"])):
        return False
    store = _load_store()
    if key not in store["deleted"]:
        store["deleted"].append(key)
    store["accounts"] = [
        row
        for row in store["accounts"]
        if str(row.get("username") or "").strip().lower() != key
        and str(row.get("was") or "").strip().lower() != key
    ]
    _save_store(store)
    return True


def authenticate(username: str, password: str) -> dict | None:
    user = (username or "").strip().lower()
    pwd = password or ""
    if not user or not pwd:
        return None
    row = find_account(user)
    if not row or row["password"] != pwd:
        return None
    return session_for_account(row)
