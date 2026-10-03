"""Load Redmine 7.x patterns for the coding-agent system prompt. No port story."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_FILE = ROOT / "knowledge" / "redmine-7-patterns.yaml"


def redmine_knowledge_text() -> str:
    if not KNOWLEDGE_FILE.is_file():
        return ""
    return KNOWLEDGE_FILE.read_text(encoding="utf-8").strip()


def redmine_system_section() -> str:
    body = redmine_knowledge_text()
    if not body:
        return ""
    return (
        "Redmine 7.x patterns (architecture first; never a “we ported 5.1→7.0” story):\n"
        "- Suggest code only. Do not write or commit the contract git.\n"
        "- Do not put hosts, mailboxes, or client GitHub in suggestions meant for public posts.\n"
        f"{body}"
    )
