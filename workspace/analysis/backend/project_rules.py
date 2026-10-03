from pathlib import Path

from .workspace import workspace_root

RULE_FILENAMES = (
    ".coding-agent/rules.md",
    "AGENTS.md",
    ".cursorrules",
    "CLAUDE.md",
)


def load_project_rules() -> str:
    workspace = workspace_root()
    chunks: list[str] = []
    for relative in RULE_FILENAMES:
        candidate = workspace / relative
        if candidate.exists() and candidate.is_file():
            chunks.append(f"# {relative}\n{candidate.read_text(encoding='utf-8')}")
    return "\n\n".join(chunks).strip()
