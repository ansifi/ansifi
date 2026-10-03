"""Dashboard chat about work status. Does not publish, mail, or pay.

One question → one short reply. Coding-agent (:8006) is used when it is up.
Jobs are recorded as later — they do not start an app process yet.
"""
from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request

from desks import all_reports, one_report
from desk_explore import is_lookup_ask, is_system_ask, lookup_answer, system_answer

JOB_WORDS = (
    "run job",
    "start job",
    "process a job",
    "queue job",
    "publish this",
    "send mail",
    "send email",
    "pay out",
    "approve all",
)
OPEN_WORDS = ("open ", "go to ", "show dashboard", "open dashboard")
DESK_HINTS = {
    "analysis": ("analysis", "build", "geoxyz", "geo.xyz", "kde", "ror", "redmine", "product", "idea", "resources"),
    "content": ("content", "post", "draft", "blog", "social", "publish"),
    "network": ("network", "mail", "gmail", "inbox", "lead", "people"),
    "operate": ("operate", "sevendyne", "empever", "axxxx", "payroll", "loan"),
}
STOP = {
    "what",
    "whats",
    "the",
    "a",
    "an",
    "is",
    "are",
    "on",
    "with",
    "going",
    "go",
    "to",
    "of",
    "for",
    "and",
    "or",
    "how",
    "this",
    "that",
    "about",
    "me",
    "my",
    "in",
    "it",
    "do",
    "does",
    "status",
    "ask",
    "please",
    "can",
    "you",
    "tell",
}
MAX_REPLY = 420


def coding_up() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 8006), timeout=0.4):
            return True
    except OSError:
        return False


def detect_desk(prompt: str, requested: str = "") -> str:
    key = (requested or "").strip().lower()
    if key in DESK_HINTS:
        return key
    blob = (prompt or "").lower()
    hits = [desk for desk, hints in DESK_HINTS.items() if any(h in blob for h in hints)]
    if len(hits) == 1:
        return hits[0]
    return ""


def is_job_request(prompt: str) -> bool:
    blob = (prompt or "").lower()
    return any(w in blob for w in JOB_WORDS)


def is_open_request(prompt: str) -> bool:
    blob = (prompt or "").lower()
    return any(w in blob for w in OPEN_WORDS)


def _format_report(row: dict) -> str:
    lines = [f"{row['title']} ({row['desk']}) — {row['summary']}"]
    for item in row.get("items") or []:
        detail = item.get("detail") or ""
        lines.append(f"- {item.get('status')}: {item.get('title')}. {detail}".strip())
    return "\n".join(lines)


def status_answer(prompt: str, desk: str = "") -> str:
    key = detect_desk(prompt, desk)
    if key:
        row = one_report(key)
        rows = [row] if row else []
    else:
        rows = all_reports()
    if not rows:
        return "No work status on this desk."
    parts = [_format_report(r) for r in rows]
    if key:
        parts.append("Click the card to open that app. Open dashboard is the working screen.")
    else:
        parts.append("Ask about Analysis, Content, Network, or Operate, or click a card.")
    return "\n\n".join(parts)


def job_reply(prompt: str, desk: str = "") -> dict:
    key = detect_desk(prompt, desk) or "analysis"
    apps = {
        "analysis": "Analysis would read 01_Build and draft notes. It does not write client code from this chat yet.",
        "content": "Content would open the notes desk. It does not publish to social until you paste and send by hand.",
        "network": "Network would open the people desk. It does not send mail from this chat.",
        "operate": "Operate stays status-only. It does not open invoices, payouts, or payroll.",
    }
    return {
        "ok": True,
        "started": False,
        "deferred": True,
        "app": key,
        "text": (
            f"Queued for later on {key}. {apps.get(key, '')} "
            "Nothing publishes, mails, or pays out from here."
        ),
    }


def _first_sentence(text: str) -> str:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", raw, maxsplit=1)
    return parts[0].rstrip()


def _shorten(text: str, max_sents: int = 4) -> str:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return raw
    parts = re.split(r"(?<=[.!?])\s+", raw)
    out = " ".join(parts[:max_sents]).strip()
    if len(out) <= MAX_REPLY:
        return out
    cut = out[: MAX_REPLY - 1].rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "."


def _tokens(prompt: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9.]+", (prompt or "").lower()) if t not in STOP and len(t) > 1]


def _item_blob(desk_id: str, item: dict) -> str:
    return " ".join(
        [
            desk_id,
            str(item.get("title") or ""),
            str(item.get("status") or ""),
            str(item.get("kind") or ""),
            str(item.get("detail") or ""),
        ]
    ).lower()


def _score_item(tokens: list[str], prompt: str, desk_id: str, item: dict) -> int:
    blob = _item_blob(desk_id, item)
    title = str(item.get("title") or "").lower()
    status = str(item.get("status") or "").lower()
    kind = str(item.get("kind") or "").lower()
    score = 0
    for t in tokens:
        if t in title:
            score += 6
        elif t in blob:
            score += 2
    low = prompt.lower()
    ready_ask = any(w in low for w in ("ready", "post", "draft", "publish"))
    if ready_ask and desk_id == "content" and ("ready" in status or kind == "ready"):
        score += 8
    if "geoxyz" in low or "geo.xyz" in low or "geo xyz" in low:
        if "geo" in title:
            score += 10
    if "kde" in low and "kde" in title:
        score += 10
    if any(w in low for w in ("ror", "rails", "programme", "learning")) and "ror" in title:
        score += 8
    if any(w in low for w in ("mail", "gmail", "inbox", "signal")) and desk_id == "network":
        score += 4
        if "inbox" in title or "aes37" in title or "signal" in title.lower() or "gmail" in blob:
            score += 4
    if "sevendyne" in low or "payroll" in low:
        if "sevendyne" in title:
            score += 10
    if "empever" in low and "empever" in title:
        score += 10
    if "axxxx" in low and "axxxx" in title:
        score += 10
    if any(w in low for w in ("next", "should i", "what now")) and "geo" in title:
        score += 5
    return score


def _line_for(item: dict) -> str:
    title = (item.get("title") or "That work").strip()
    status = (item.get("status") or "").strip()
    detail = _first_sentence(str(item.get("detail") or ""))
    if status and detail:
        return f"{title} is {status.lower()}. {detail}"
    if status:
        return f"{title} is {status.lower()}."
    return detail or f"{title} is on the status cards."


def _reports_for(desk: str) -> list[dict]:
    key = (desk or "").strip().lower()
    if key:
        row = one_report(key)
        return [row] if row else []
    return all_reports()


def _history_text(history: list | None) -> str:
    parts = []
    for row in history or []:
        if not isinstance(row, dict):
            continue
        txt = str(row.get("text") or "").strip()
        if txt:
            parts.append(txt)
    return " ".join(parts)


def _already_said(history: list | None, title: str) -> bool:
    blob = _history_text(history).lower()
    name = (title or "").lower()
    if not name or not blob:
        return False
    short = name.split("(")[0].strip()
    return name in blob or (len(short) > 3 and short in blob)


def _is_followup(prompt: str) -> bool:
    return bool(
        re.fullmatch(
            r"(what else|anything else|and then|more|others?|next|what about the rest|any other.*)",
            (prompt or "").strip().rstrip("?."),
            flags=re.I,
        )
    )


def _live_items(reports: list[dict]) -> list[dict]:
    kinds = {"ongoing", "progress", "ready", "live", "forming", "mail"}
    out = []
    for row in reports:
        for item in row.get("items") or []:
            kind = str(item.get("kind") or "")
            status = str(item.get("status") or "").lower()
            if kind in kinds or "ongoing" in status or "progress" in status:
                out.append(item)
    return out


def chat_answer(prompt: str, desk: str = "", history: list | None = None) -> str:
    text = (prompt or "").strip()
    if not text:
        return "Ask one thing about the desks."
    if re.fullmatch(r"(hi|hello|hey|yo)[!., ]*", text, flags=re.I):
        return "Hi. Ask one thing — what’s on disk, GEO.XYZ, a post, or what Sevendyne is."

    bits = [b.strip() for b in re.split(r"[?]+", text) if b.strip()]
    if len(bits) > 1:
        parts = []
        seen: set[str] = set()
        for bit in bits[:3]:
            line = _answer_one(bit + "?", desk, history)
            key = line.lower()
            if key not in seen:
                seen.add(key)
                parts.append(line)
        return _shorten(" ".join(parts), max_sents=5)

    return _answer_one(text, desk, history)


def _answer_one(prompt: str, desk: str, history: list | None = None) -> str:
    tokens = _tokens(prompt)
    hinted = detect_desk(prompt, "")
    reports = _reports_for(hinted or desk)
    if not reports:
        reports = all_reports()
    low = prompt.lower()
    named = any(n in low for n in ("geo", "kde", "ror", "redmine", "jan", "sevendyne", "empever", "axxxx"))
    list_rest = _is_followup(prompt) or (
        not named and any(w in low for w in ("other", "else", "projects"))
    )
    if list_rest:
        rest = [item for item in _live_items(reports) if not _already_said(history, str(item.get("title") or ""))]
        if rest:
            return _shorten(" ".join(_line_for(item) for item in rest[:2]))

    scored: list[tuple[int, dict]] = []
    for row in reports:
        desk_id = str(row.get("id") or "")
        for item in row.get("items") or []:
            if _already_said(history, str(item.get("title") or "")) and _is_followup(prompt):
                continue
            s = _score_item(tokens, prompt, desk_id, item)
            if s > 0:
                scored.append((s, item))
    scored.sort(key=lambda x: -x[0])
    picks = [item for s, item in scored if s >= 4][:2]
    if not picks and scored:
        picks = [scored[0][1]]
    if not picks:
        if reports and len(reports) == 1:
            return _shorten(
                f"{reports[0]['title']} — {reports[0].get('summary') or reports[0].get('now') or 'status is on the card.'}"
            )
        return "I only know the four status cards. Ask about GEO.XYZ, a post, mail, Sevendyne, or Empever."
    return _shorten(" ".join(_line_for(item) for item in picks))


def try_coding_agent(prompt: str, context: str) -> str | None:
    if not coding_up():
        return None
    body = json.dumps(
        {
            "prompt": (
                "You are the Ansif Workspace desk chat.\n"
                "Reply like a 1-to-1 chat: 2–4 short sentences, only what was asked.\n"
                "Do not dump every status card. Do not invent payroll figures or send mail.\n\n"
                f"Work status:\n{context}\n\nUser: {prompt}"
            ),
            "response_mode": "quick",
            "context_files": [],
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:8006/api/agent/execute",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    result = data.get("result") if isinstance(data, dict) else None
    if isinstance(result, dict):
        text = result.get("text") or result.get("message") or ""
        if text:
            return _shorten(str(text))
    if isinstance(result, str) and result.strip():
        return _shorten(result)
    return None


def reply(prompt: str, desk: str = "", history: list | None = None) -> dict:
    text = (prompt or "").strip()
    if not text:
        return {"ok": False, "error": "empty", "text": "Ask one thing about a work status card."}
    key = detect_desk(text, desk)
    if is_job_request(text):
        out = job_reply(text, key)
        out["source"] = "deferred"
        out["coding"] = coding_up()
        return out
    if is_system_ask(text, history):
        try:
            listed = system_answer(text, history)
        except Exception:
            listed = "Could not read the works folders just now."
        return {
            "ok": True,
            "text": listed,
            "source": "disk",
            "desk": key,
            "coding": False,
            "open": "",
            "started": False,
            "deferred": False,
        }
    if is_lookup_ask(text, history):
        try:
            looked = lookup_answer(text, history)
        except Exception:
            looked = "Could not look that up just now. Ask again, or ask what’s on disk."
        return {
            "ok": True,
            "text": looked,
            "source": "web",
            "desk": key,
            "coding": False,
            "open": "",
            "started": False,
            "deferred": False,
        }
    try:
        context = status_answer(text, key)
        short = chat_answer(text, key, history)
    except Exception:
        context = ""
        short = "Work status is briefly unavailable. Ask again in a moment."
    agent = try_coding_agent(text, context) if context else None
    if agent:
        return {
            "ok": True,
            "text": agent,
            "source": "coding-agent",
            "desk": key,
            "coding": True,
            "open": key if is_open_request(text) else "",
        }
    return {
        "ok": True,
        "text": short,
        "source": "status",
        "desk": key,
        "coding": False,
        "open": key if is_open_request(text) else "",
        "started": False,
        "deferred": False,
    }
