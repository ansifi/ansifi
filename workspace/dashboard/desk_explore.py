"""Disk listing and public-site lookup for desk chat.

Stays under /home/ansif/works. Does not open payroll invoices, secrets, or mailboxes.
"""
from __future__ import annotations

import html as htmlmod
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

WORKS = Path("/home/ansif/works")
SKIP_NAMES = {
    ".git",
    ".gradle",
    ".venv",
    ".run",
    ".env",
    "node_modules",
    "__pycache__",
    "media",
    "credentials.json",
}
BLOCK_DEEP = ("sevendyne_payrolls", "media", "reports", ".git")
EXPLORE_MAX = 780
UA = "AnsifWorkspaceDesk/1.0 (+local hub)"

SITES = {
    "sevendyne": {
        "urls": ("https://www.sevendyne.com/",),
        "notes": WORKS / "04_Operate" / "Sevendyne" / "README.md",
        "query": "Sevendyne Consultancy Kochi managed engineering",
    },
    "empever": {
        "urls": ("https://empever.com/", "https://www.empever.com/"),
        "notes": WORKS / "04_Operate" / "Empever" / "README.md",
        "query": "Empever Infoservices Kochi engineering training",
    },
    "axxxx": {
        "urls": (),
        "notes": None,
        "query": "",
        "memory": "Axxxx is later retail / robotics (2039). No Operate folder yet. Product ideas stay in 01_Build/resources/.",
    },
}

FOLDER_ALIASES = {
    "works": WORKS,
    "system": WORKS,
    "ansif": WORKS / "00_Ansif",
    "00_ansif": WORKS / "00_Ansif",
    "build": WORKS / "01_Build",
    "01_build": WORKS / "01_Build",
    "content": WORKS / "02_Content",
    "02_content": WORKS / "02_Content",
    "network": WORKS / "03_Network",
    "03_network": WORKS / "03_Network",
    "operate": WORKS / "04_Operate",
    "04_operate": WORKS / "04_Operate",
    "sevendyne": WORKS / "04_Operate" / "Sevendyne",
    "empever": WORKS / "04_Operate" / "Empever",
    "resources": WORKS / "01_Build" / "resources",
    "studies": WORKS / "01_Build" / "studies",
    "technicals": WORKS / "01_Build" / "technicals",
}

SYSTEM_PHRASES = (
    "in my system",
    "on my system",
    "on this system",
    "on disk",
    "in works",
    "my folders",
    "my directories",
    "list folders",
    "list directories",
    "show folders",
    "what's in the system",
    "what is in the system",
    "what do i have",
    "what folders",
)


def fetch_url(url: str, timeout: float = 8.0) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read(120_000)
    return raw.decode("utf-8", errors="replace")


def _html_text(raw: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = htmlmod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _clip(text: str, n: int = EXPLORE_MAX) -> str:
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if len(raw) <= n:
        return raw
    return raw[: n - 1].rsplit(" ", 1)[0].rstrip(".,;:") + "."


def _history_blob(history: list | None) -> str:
    parts = []
    for row in history or []:
        if isinstance(row, dict):
            parts.append(str(row.get("text") or ""))
    return " ".join(parts)


def _under_works(path: Path) -> Path | None:
    try:
        resolved = path.expanduser().resolve()
        resolved.relative_to(WORKS.resolve())
    except (OSError, ValueError):
        return None
    return resolved if resolved.exists() else None


def _blocked(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return any(b in parts for b in BLOCK_DEEP)


def _list_names(folder: Path, limit: int = 12) -> list[str]:
    names: list[str] = []
    try:
        entries = sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError:
        return []
    for item in entries:
        if item.name.startswith(".") or item.name in SKIP_NAMES:
            continue
        names.append(item.name + ("/" if item.is_dir() else ""))
        if len(names) >= limit:
            break
    return names


def _last_disk_path(history: list | None) -> Path | None:
    found = re.findall(r"On disk `([^`]+)`", _history_blob(history))
    if not found:
        return None
    return _under_works(Path(found[-1]))


def _named_folder(prompt: str) -> Path | None:
    low = (prompt or "").lower()
    # longest alias first
    for key in sorted(FOLDER_ALIASES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(key)}\b", low) or key.replace("_", " ") in low:
            return FOLDER_ALIASES[key]
    m = re.search(r"\b(00_Ansif|01_Build|02_Content|03_Network|04_Operate)\b", prompt or "", flags=re.I)
    if m:
        return WORKS / m.group(1)
    return None


def is_system_ask(prompt: str, history: list | None = None) -> bool:
    low = (prompt or "").lower()
    if any(p in low for p in SYSTEM_PHRASES):
        return True
    if re.search(r"\b(ls|list|inside|contents of|what's in|what is in|dig deeper|go deeper)\b", low):
        if _named_folder(prompt) or "folder" in low or "dir" in low or "system" in low or "works" in low:
            return True
        if "On disk `" in _history_blob(history):
            return True
    if re.fullmatch(r"(more|what else|anything else|deeper|dig deeper|go deeper|next)\??", low.strip()):
        return "On disk `" in _history_blob(history)
    return False


def system_answer(prompt: str, history: list | None = None) -> str:
    low = (prompt or "").lower()
    if "sevendyne_payrolls" in low or "media/reports" in low:
        return "That folder is payroll / media. Chat does not open invoices, payouts, or bank files."
    named = _named_folder(prompt)
    last = _last_disk_path(history)
    target = named or last or WORKS
    if named is None and last is not None and re.fullmatch(
        r"(more|what else|anything else|deeper|dig deeper|go deeper|next)\??",
        (prompt or "").strip().rstrip("?."),
        flags=re.I,
    ):
        # one level deeper: first directory not yet named in the last reply
        blob = _history_blob(history).lower()
        for child in _list_names(last, limit=20):
            if not child.endswith("/"):
                continue
            stem = child.rstrip("/")
            if stem.lower() not in blob.replace("on disk", ""):
                deeper = last / stem
                if _under_works(deeper):
                    target = deeper
                    break
        else:
            kids = [last / n.rstrip("/") for n in _list_names(last) if n.endswith("/")]
            if kids:
                target = kids[0]
    safe = _under_works(target) if target else WORKS
    if safe is None:
        safe = WORKS
    if _blocked(safe):
        return "That folder is payroll / media. Chat does not open invoices, payouts, or bank files."
    if not safe.is_dir():
        return f"On disk `{safe}` is a file, not a folder."
    names = _list_names(safe)
    if not names:
        return f"On disk `{safe}` is empty (or only hidden / skipped files)."
    shown = ", ".join(names)
    extra = " Ask for any name to list inside." if any(n.endswith("/") for n in names) else ""
    return _clip(f"On disk `{safe}`: {shown}.{extra}")


def is_lookup_ask(prompt: str, history: list | None = None) -> bool:
    low = (prompt or "").lower()
    if "payroll" in low and any(w in low for w in ("desk", "status", "how are")):
        return False
    if re.search(r"what(?:'s| is) in\b", low):
        return False
    if low.strip().startswith("search ") or low.strip().startswith("google "):
        return True
    entities = tuple(SITES)
    has_ent = any(e in low for e in entities)
    hist = _history_blob(history).lower()
    if re.fullmatch(r"(more|more details|tell me more|deeper|what else)\??", low.strip()):
        return any(e in hist for e in entities) and "On disk `" not in _history_blob(history)
    if not has_ent:
        return False
    if any(k in low for k in ("what is", "what's", "who is", "tell me", "website", "about", "explain")):
        return True
    if low.strip("?. ") in entities:
        return True
    return False


def _entity_from(prompt: str, history: list | None) -> str:
    blob = ((prompt or "") + " " + _history_blob(history)).lower()
    for name in SITES:
        if name in blob:
            return name
    return ""


def _local_note(path: Path | None) -> str:
    if not path or not path.is_file():
        return ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    keep: list[str] = []
    for line in lines:
        low = line.lower()
        if any(x in low for x in ("app.sevendyne", "@", "github.com/", "127.0.0.1", "payrolls")):
            continue
        line = line.strip()
        if not line or line.startswith("|") or line.startswith("#"):
            if line.startswith("# ") and len(keep) < 1:
                keep.append(line[2:].strip())
            continue
        keep.append(re.sub(r"[*_`]+", "", re.sub(r"\s+", " ", line)))
        if len(keep) >= 4:
            break
    return " ".join(keep)


def _clean_site(text: str) -> str:
    for marker in (
        "Your product",
        "Sevendyne has been",
        "EMPEVER Infoservices",
        "Skilled engineering training",
        "Managed engineering",
    ):
        i = text.find(marker)
        if i >= 40:
            return text[i:]
        if i >= 0:
            return text[max(0, i - 80) :]
    return text


def _site_text(urls: tuple[str, ...]) -> str:
    for url in urls:
        try:
            text = _clean_site(_html_text(fetch_url(url)))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
        if len(text) > 80:
            return _clip(text, 420)
    return ""


def _ddg_snippet(query: str) -> str:
    if not query:
        return ""
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        raw = fetch_url(url)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return ""
    snippets = re.findall(r'(?is)class="result__snippet"[^>]*>(.*?)</(?:a|td|div)', raw)
    if not snippets:
        snippets = re.findall(r"(?is)<a[^>]+class=\"result__a\"[^>]*>(.*?)</a>", raw)
    cleaned = []
    for snip in snippets[:2]:
        t = _html_text(snip)
        if t:
            cleaned.append(t)
    return _clip(" ".join(cleaned), 280) if cleaned else ""


def lookup_answer(prompt: str, history: list | None = None) -> str:
    low = (prompt or "").lower().strip()
    if low.startswith("search ") or low.startswith("google "):
        q = re.sub(r"^(search|google)\s+", "", low, flags=re.I).strip()
        found = _ddg_snippet(q)
        return found or "Search did not return a snippet. Try a company name (Sevendyne, Empever) or a folder on disk."
    name = _entity_from(prompt, history)
    if not name:
        return "Ask about Sevendyne, Empever, or Axxxx — or say search <topic>."
    spec = SITES[name]
    memory = spec.get("memory") or ""
    site = _site_text(spec.get("urls") or ())
    note = _local_note(spec.get("notes") if isinstance(spec.get("notes"), Path) else None)
    search = ""
    if not site:
        search = _ddg_snippet(str(spec.get("query") or name))
    more = "more" in low or "detail" in low or "deeper" in low
    parts = []
    if site:
        parts.append(site)
    elif search:
        parts.append(search)
    if note and (more or not site):
        parts.append(note)
    if memory:
        parts.append(str(memory))
    if more and site and note:
        parts = [site, note]
    if not parts:
        return f"I could not reach the {name} site just now. Ask again, or ask what’s on disk under 04_Operate."
    return _clip(" ".join(parts))
