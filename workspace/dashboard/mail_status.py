"""Read-only Gmail status for aes37group@gmail.com.

Never send, never open Sevendyne marketing/HR mailboxes.
"""
from __future__ import annotations

import email.header
import imaplib
import json
import re
import socket
import time
from email.utils import parsedate_to_datetime
from pathlib import Path

ALLOWED = ("aes37group@gmail.com",)
CONFIG_CANDIDATES = (
    Path("/home/ansif/works/00_Ansif/workspace/leads/data/crm/gmail_sync_accounts.json"),
)
CACHE_SEC = 90
IMAP_TIMEOUT = 12
MAX_HEADERS = 24
SNIPPET_BYTES = 700
SNIPPET_CHARS = 280

NOISE_SUBJECT = (
    "security alert",
    "2-step verification",
    "terms of service",
    "community guidelines",
    "privacy policy",
    "stop repeating yourself",
    "connect your email, calendar",
    "start a project to give each idea",
)
NOISE_FROM = (
    "no-reply@email.claude.com",
    "noreply@youtube.com",
    "no-reply@accounts.google.com",
)

# Order matters: first match is the primary chip.
SIGNAL_KINDS = (
    (
        "project_need",
        "Project need",
        (
            "looking for",
            "we need",
            "need a",
            "need developers",
            "rfp",
            "request for proposal",
            "requirement",
            "scope of work",
            "quote for",
            "tender",
            "build us",
            "head of product",
            "product development",
            "hiring",
            "vacancy",
            "open role",
            "staff this",
        ),
    ),
    ("payroll", "Payroll / staffing", ("payroll", "staffing", "timesheet", "consultant")),
    ("training", "Training", ("training", "workshop", "programme", "program")),
    (
        "named_client",
        "Named client",
        (
            "geoxyz",
            "geo.xyz",
            "csr",
            "quantyf",
            "oovattil",
            "ovt",
            "crossdock",
            "kde",
            "redmine",
        ),
    ),
    ("own_desk", "Desk follow-up", ("sevendyne", "empever")),
)

_cache: dict | None = None
_cache_at = 0.0


def _decode_header(raw: str) -> str:
    parts = email.header.decode_header(raw or "")
    out = []
    for chunk, enc in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(str(chunk))
    return " ".join(out).replace("\n", " ").strip()


def _is_noise(subject: str, from_addr: str) -> bool:
    sub = (subject or "").lower()
    src = (from_addr or "").lower()
    if any(n in src for n in NOISE_FROM):
        return True
    return any(n in sub for n in NOISE_SUBJECT)


def classify_signals(subject: str, from_addr: str, snippet: str = "") -> list[dict]:
    if _is_noise(subject, from_addr):
        return []
    blob = f"{subject} {from_addr} {snippet}".lower()
    out = []
    seen = set()
    for kid, label, words in SIGNAL_KINDS:
        if any(w in blob for w in words):
            if kid not in seen:
                seen.add(kid)
                out.append({"id": kid, "label": label})
    return out


def is_client_mail(subject: str, from_addr: str, snippet: str = "") -> bool:
    return bool(classify_signals(subject, from_addr, snippet))


def _plain_snippet(raw, limit: int = SNIPPET_CHARS) -> str:
    text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw or "")
    plain = re.search(
        r'(?is)content-type:\s*text/plain[^\n]*\n(?:[^\n]+:[^\n]*\n)*\s*\n(.*?)(?:\n--|\Z)',
        text,
    )
    if plain:
        text = plain.group(1)
    else:
        html = re.search(
            r'(?is)content-type:\s*text/html[^\n]*\n(?:[^\n]+:[^\n]*\n)*\s*\n(.*?)(?:\n--|\Z)',
            text,
        )
        if html:
            text = html.group(1)
    text = re.sub(r"=\r?\n", "", text)
    try:
        import quopri

        text = quopri.decodestring(text.encode("utf-8", errors="replace")).decode("utf-8", errors="replace")
    except Exception:
        pass
    text = re.sub(r"(?is)<(style|script)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&amp;|&lt;|&gt;|&quot;", " ", text)
    text = re.sub(r"--[0-9a-fA-F-]{8,}", " ", text)
    text = re.sub(r"(?im)^(content-type|content-transfer-encoding|charset):.*$", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _short_date(raw: str) -> str:
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime("%d %b %Y · %H:%M")
    except (TypeError, ValueError, OverflowError):
        return (raw or "")[:22]


def _read_accounts() -> list[dict]:
    data = None
    for path in CONFIG_CANDIDATES:
        if path.is_file():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = None
            break
    rows = []
    seen = set()
    for entry in (data or {}).get("accounts") or []:
        email_addr = str(entry.get("email") or "").strip().lower()
        if email_addr not in ALLOWED or email_addr in seen:
            continue
        secret = str(entry.get("app_password") or "").replace(" ", "")
        if not secret or secret.startswith("xxxx"):
            continue
        seen.add(email_addr)
        rows.append({"email": email_addr, "secret": secret, "label": entry.get("label") or email_addr})
    return rows


def _fetch_snippet(imap, num) -> str:
    try:
        typ, fetched = imap.fetch(num, f"(BODY.PEEK[TEXT]<0.{SNIPPET_BYTES}>)")
    except Exception:
        return ""
    if typ != "OK" or not fetched:
        return ""
    raw = b""
    for part in fetched:
        if isinstance(part, tuple) and len(part) > 1 and isinstance(part[1], (bytes, bytearray)):
            raw += bytes(part[1])
    return _plain_snippet(raw)


def _imap_snapshot(email_addr: str, secret: str) -> dict:
    box = {
        "email": email_addr,
        "connected": False,
        "unseen": 0,
        "total": 0,
        "error": "",
        "recent": [],
        "client_mail": [],
        "signals": [],
    }
    imap = None
    try:
        socket.setdefaulttimeout(IMAP_TIMEOUT)
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        imap.socket().settimeout(IMAP_TIMEOUT)
        imap.login(email_addr, secret)
        typ, data = imap.status("INBOX", "(MESSAGES UNSEEN)")
        if typ == "OK" and data:
            blob = data[0].decode("utf-8", errors="replace") if isinstance(data[0], bytes) else str(data[0])
            m = re.search(r"MESSAGES\s+(\d+)", blob)
            u = re.search(r"UNSEEN\s+(\d+)", blob)
            if m:
                box["total"] = int(m.group(1))
            if u:
                box["unseen"] = int(u.group(1))
        typ, _ = imap.select("INBOX", readonly=True)
        if typ != "OK":
            box["connected"] = True
            return box
        typ, ids = imap.search(None, "ALL")
        seq = []
        if typ == "OK" and ids and ids[0]:
            seq = ids[0].split()[-MAX_HEADERS:]
            seq.reverse()
        recent = []
        client_mail = []
        for num in seq:
            typ, fetched = imap.fetch(num, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if typ != "OK" or not fetched or not fetched[0]:
                continue
            raw = fetched[0][1] if isinstance(fetched[0], tuple) else fetched[0]
            msg = email.message_from_bytes(raw if isinstance(raw, bytes) else bytes(raw))
            subject = _decode_header(msg.get("Subject") or "")
            from_addr = _decode_header(msg.get("From") or "")
            date = _decode_header(msg.get("Date") or "")
            row = {
                "from": from_addr,
                "subject": subject or "(no subject)",
                "date": date,
                "when": _short_date(date),
            }
            recent.append(row)
            chips = classify_signals(subject, from_addr)
            if not chips:
                continue
            snippet = _fetch_snippet(imap, num)
            if snippet:
                extra = classify_signals(subject, from_addr, snippet)
                if extra:
                    chips = extra
            hit = {
                **row,
                "mailbox": email_addr,
                "snippet": snippet,
                "signals": chips,
                "kind": (chips[0]["id"] if chips else ""),
                "kind_label": (chips[0]["label"] if chips else ""),
            }
            client_mail.append(hit)
        box["recent"] = recent
        box["client_mail"] = client_mail
        box["signals"] = client_mail
        box["connected"] = True
    except Exception as exc:
        box["error"] = str(exc).split("\n")[0][:180]
    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception:
                pass
        socket.setdefaulttimeout(None)
    return box


def mailbox_status(live: bool = True) -> dict:
    global _cache, _cache_at
    now = time.monotonic()
    if live and _cache is not None and now - _cache_at < CACHE_SEC:
        return _cache
    accounts = {row["email"]: row for row in _read_accounts()} if live else {}
    boxes = []
    for addr in ALLOWED:
        cred = accounts.get(addr)
        if not cred:
            boxes.append(
                {
                    "email": addr,
                    "connected": False,
                    "unseen": 0,
                    "total": 0,
                    "error": "App password missing. Copy gmail_sync_accounts.example.json to gmail_sync_accounts.json (gitignored).",
                    "recent": [],
                    "client_mail": [],
                    "signals": [],
                }
            )
            continue
        boxes.append(_imap_snapshot(cred["email"], cred["secret"]))
    client_hits = []
    for box in boxes:
        for row in box.get("client_mail") or []:
            client_hits.append({**row, "mailbox": row.get("mailbox") or box["email"]})
    out = {
        "mailboxes": ALLOWED,
        "boxes": boxes,
        "client_hits": client_hits,
        "signals": client_hits,
        "connected": any(b.get("connected") for b in boxes),
    }
    if live:
        _cache = out
        _cache_at = now
    return out


def mail_feed(live: bool = True) -> dict:
    st = mailbox_status(live=live)
    box = (st.get("boxes") or [{}])[0]
    return {
        "ok": True,
        "mailbox": ALLOWED[0],
        "connected": bool(st.get("connected")),
        "unseen": box.get("unseen") or 0,
        "total": box.get("total") or 0,
        "scanned": len(box.get("recent") or []),
        "signals": st.get("signals") or [],
        "error": box.get("error") or "",
    }
