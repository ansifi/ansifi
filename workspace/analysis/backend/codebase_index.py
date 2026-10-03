import os
from collections import Counter
from pathlib import Path
from typing import Any

from .tools import list_files, read_file
from .workspace import AgentError, workspace_root

SKIP_SNIPPET_PREFIXES = ("jcatrysse_ror/redmine/",)

KEY_FILES = (
    "README.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "docker-compose.yml",
    "Dockerfile",
    "Makefile",
    "Gemfile",
    "build.gradle",
)


def build_codebase_index() -> dict[str, Any]:
    workspace = workspace_root()
    files = list_files()
    extensions = Counter(Path(path).suffix.lower() or "(no ext)" for path in files)
    top_level_dirs = sorted(
        {
            path.split("/", 1)[0]
            for path in files
            if "/" in path and not path.startswith(".")
        }
    )

    detected: list[str] = []
    snippets: list[str] = []
    for name in KEY_FILES:
        matches = [path for path in files if path == name or path.endswith(f"/{name}")]
        for match in matches[:2]:
            if any(match.startswith(prefix) for prefix in SKIP_SNIPPET_PREFIXES):
                continue
            detected.append(match)
            try:
                content = read_file(match)
                snippets.append(f"## {match}\n{content[:1200]}")
            except AgentError:
                continue

    stack_hints: list[str] = []
    if any(path.endswith("package.json") for path in files):
        stack_hints.append("Node/JavaScript")
    if any(path.endswith(".py") for path in files):
        stack_hints.append("Python")
    if any(path.endswith(".rb") for path in files):
        stack_hints.append("Ruby")
    if any(path.endswith(".java") or path.endswith(".kt") for path in files):
        stack_hints.append("JVM/Android")
    if any(path.endswith(".go") for path in files):
        stack_hints.append("Go")
    if any(path.endswith(".rs") for path in files):
        stack_hints.append("Rust")

    summary_lines = [
        f"Workspace: {workspace}",
        f"Files: {len(files)}",
        f"Top-level folders: {', '.join(top_level_dirs[:20]) or '(none)'}",
        f"Likely stack: {', '.join(stack_hints) or 'unknown'}",
        f"Extensions: {', '.join(f'{ext}({count})' for ext, count in extensions.most_common(12))}",
        f"Key files: {', '.join(detected[:12]) or '(none)'}",
    ]

    return {
        "workspace": str(workspace),
        "file_count": len(files),
        "top_level_dirs": top_level_dirs,
        "extensions": dict(extensions),
        "stack_hints": stack_hints,
        "key_files": detected,
        "summary": "\n".join(summary_lines),
        "snippets": "\n\n".join(snippets[:6]),
    }


def codebase_context_text(compact: bool = False) -> str:
    index = build_codebase_index()
    if compact:
        return index["summary"]
    chunks = [index["summary"]]
    if index.get("snippets"):
        chunks.append(index["snippets"])
    return "\n\n".join(chunks)
