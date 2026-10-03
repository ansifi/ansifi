"""Optional Gemini assist. Patterns only — no hosts or mailboxes."""
from __future__ import annotations

import os
from typing import Any

import requests

from .redmine_knowledge import redmine_knowledge_text

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)


def gemini_configured() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def assist_task(task: str, similar: list[str] | None = None) -> dict[str, Any]:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    knowledge = redmine_knowledge_text()
    examples = "\n---\n".join((similar or [])[:5])
    prompt = (
        "You assist Redmine 7.x work. Architecture first. "
        "Never write a we-ported-5.1-to-7.0 story. "
        "Never invent hosts or mailboxes.\n\n"
        f"Knowledge:\n{knowledge}\n\n"
        f"Task:\n{task}\n\n"
        f"Similar local snippets (paths only if given):\n{examples or '(none)'}\n\n"
        "Reply with sections:\n## CODE\n## EXPLANATION\n## TESTS\n## DEPLOYMENT\n"
    )
    try:
        response = requests.post(
            GEMINI_URL,
            params={"key": key},
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Gemini request failed: {exc}") from exc
    payload = response.json()
    text = (
        payload.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    return {"text": text, "model": "gemini-2.0-flash"}
