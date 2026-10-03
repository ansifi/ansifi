import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .workspace import PROJECT_ROOT

SESSIONS_DIR = PROJECT_ROOT / ".run" / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def create_session(title: str = "New chat") -> dict[str, Any]:
    session_id = uuid.uuid4().hex[:12]
    payload = {
        "id": session_id,
        "title": title,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "messages": [],
    }
    _session_path(session_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def list_sessions() -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for path in sorted(SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            sessions.append(
                {
                    "id": payload.get("id"),
                    "title": payload.get("title", "Chat"),
                    "updated_at": payload.get("updated_at"),
                    "message_count": len(payload.get("messages", [])),
                }
            )
        except Exception:  # noqa: BLE001
            continue
    return sessions


def get_session(session_id: str) -> dict[str, Any]:
    path = _session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(f"Session not found: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def append_message(session_id: str, role: str, text: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    session = get_session(session_id)
    message = {
        "role": role,
        "text": text,
        "meta": meta or {},
        "at": datetime.now(timezone.utc).isoformat(),
    }
    session["messages"].append(message)
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    if role == "user" and len(session["messages"]) == 1:
        session["title"] = text[:60]
    _session_path(session_id).write_text(json.dumps(session, indent=2), encoding="utf-8")
    return session
