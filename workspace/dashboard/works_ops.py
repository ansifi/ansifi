"""Desk-app helpers: notes into 02_Content, post URLs, network signals."""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from desks import WORKS, _first_heading
from mail_status import mail_feed

NOTES = WORKS / "02_Content" / "Notes"
DRAFTS = WORKS / "02_Content" / "Posts" / "drafts"
PUBLISHED = WORKS / "02_Content" / "Posts" / "published"
SIGNALS = WORKS / "03_Network" / "Leads" / "signals.json"
SOURCES = WORKS / "03_Network" / "Leads" / "signal-sources.json"
PEOPLE = WORKS / "03_Network" / "Leads" / "target-people.md"

SKIP_NOTES = {"Readme.md", "README.md"}
SKIP_DRAFTS = {"SERIES-from-port-commits.md", "2026-08-13_redmine-how-to-build-drafts.md"}

PUBLISH = (
    {"id": "devto", "name": "Dev.to", "url": "https://dev.to/new"},
    {"id": "medium", "name": "Medium", "url": "https://medium.com/new-story"},
    {"id": "hashnode", "name": "Hashnode", "url": "https://hashnode.com/draft"},
    {"id": "linkedin", "name": "LinkedIn", "url": "https://www.linkedin.com/feed/"},
    {"id": "x", "name": "X", "url": "https://twitter.com/compose/tweet"},
)


def _slug(title: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "-", (title or "note").lower()).strip("-")
    return (raw or "note")[:60]


def save_note(title: str, body: str, work: str = "") -> dict:
    title = (title or "").strip() or "Untitled note"
    body = (body or "").strip()
    if not body:
        return {"ok": False, "error": "empty"}
    NOTES.mkdir(parents=True, exist_ok=True)
    name = f"{date.today().isoformat()}-{_slug(title)}.md"
    path = NOTES / name
    n = 2
    while path.exists():
        name = f"{date.today().isoformat()}-{_slug(title)}-{n}.md"
        path = NOTES / name
        n += 1
    work_line = f"**Work:** {work}\n\n" if work.strip() else ""
    text = (
        f"# {title}\n\n"
        f"{work_line}"
        "Public copy stays generic — no project names, hosts, or mailboxes.\n\n"
        f"{body.rstrip()}\n"
    )
    path.write_text(text, encoding="utf-8")
    return {
        "ok": True,
        "name": name,
        "path": _rel(path),
        "title": title,
    }


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKS))
    except ValueError:
        return str(path)


def _md_item(path: Path, kind: str) -> dict:
    work = ""
    try:
        for line in path.read_text(encoding="utf-8").splitlines()[:16]:
            if line.startswith("**Work:**"):
                work = line.split("**Work:**", 1)[-1].strip()
                break
    except OSError:
        work = ""
    return {
        "name": path.name,
        "title": _first_heading(path),
        "kind": kind,
        "work": work,
        "path": _rel(path),
    }


def list_contents() -> dict:
    notes = []
    if NOTES.is_dir():
        for path in sorted(NOTES.glob("*.md"), reverse=True):
            if path.name in SKIP_NOTES:
                continue
            notes.append(_md_item(path, "note"))
    drafts = []
    if DRAFTS.is_dir():
        for path in sorted(DRAFTS.glob("*.md"), reverse=True):
            if path.name in SKIP_DRAFTS:
                continue
            drafts.append(_md_item(path, "draft"))
    live = []
    log = PUBLISHED / "log.json"
    if log.is_file():
        try:
            raw = json.loads(log.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                live = raw
        except (OSError, json.JSONDecodeError):
            live = []
    return {
        "ok": True,
        "notes": notes,
        "drafts": drafts,
        "live": live,
        "publish": [dict(row) for row in PUBLISH],
        "how": (
            "Nothing auto-publishes. Open a draft, then use a Post on… link "
            "(Dev.to, Medium, Hashnode, LinkedIn, X) and paste by hand."
        ),
    }


def _load_json(path: Path, key: str) -> list:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        rows = data.get(key) or data.get("signals") or []
        return rows if isinstance(rows, list) else []
    return data if isinstance(data, list) else []


def _people() -> list[dict]:
    if not PEOPLE.is_file():
        return []
    out = []
    try:
        lines = PEOPLE.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.startswith("|") or line.startswith("| Name") or line.startswith("|------"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 6:
            continue
        name = cells[0]
        if not name:
            continue
        out.append(
            {
                "name": name,
                "url": cells[1],
                "problem": cells[2],
                "help": cells[3],
                "contact": cells[4],
                "bill_via": cells[5],
                "status": cells[6] if len(cells) > 6 else "",
            }
        )
    return out


def network_board() -> dict:
    mail = mail_feed()
    emails = []
    for hit in mail.get("signals") or []:
        chips = hit.get("signals") or []
        label = (chips[0].get("label") if chips else None) or "Inbox"
        emails.append(
            {
                "title": hit.get("subject") or "(no subject)",
                "from": hit.get("from") or "",
                "when": hit.get("when") or hit.get("date") or "",
                "label": label,
                "url": "",
            }
        )
    web = []
    for row in _load_json(SIGNALS, "signals"):
        if not isinstance(row, dict):
            continue
        web.append(
            {
                "title": row.get("title") or row.get("id") or "Signal",
                "url": row.get("url") or "",
                "snippet": row.get("snippet") or "",
                "source": row.get("source") or "",
                "contact": row.get("contact_info") or "",
                "status": row.get("status") or "",
            }
        )
    sources = []
    for row in _load_json(SOURCES, "sources"):
        if not isinstance(row, dict):
            continue
        sources.append(
            {
                "id": row.get("id") or "",
                "label": row.get("label") or row.get("id") or "Source",
                "url": row.get("href") or row.get("url") or "",
            }
        )
    return {
        "ok": True,
        "mailbox": mail.get("mailbox") or "aes37group@gmail.com",
        "connected": bool(mail.get("connected")),
        "unseen": mail.get("unseen") or 0,
        "error": mail.get("error") or "",
        "emails": emails,
        "signals": web,
        "sources": sources,
        "people": _people(),
    }
