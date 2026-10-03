import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from .contract_guard import assert_writable, command_mutates_git
from .workspace import (
    AgentError,
    SIDEBAR_SHALLOW_DIRS,
    list_files,
    resolve_workspace_path,
    workspace_root,
)

MAX_FILE_SIZE = 200_000
MAX_SEARCH_RESULTS = 40
COMMAND_TIMEOUT_SECONDS = 120
FETCH_TIMEOUT_SECONDS = 20
IGNORED_DIR_NAMES = {".git", "node_modules", "__pycache__", "dist", ".venv", ".run"}
BLOCKED_COMMAND_TOKENS = {
    "rm",
    "sudo",
    "shutdown",
    "reboot",
    "mkfs",
    "dd",
    "mount",
    "umount",
    "poweroff",
    "passwd",
    "chown",
    "chmod",
}
TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".json",
    ".md",
    ".txt",
    ".html",
    ".css",
    ".scss",
    ".yml",
    ".yaml",
    ".xml",
    ".sh",
    ".rb",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".gradle",
    ".sql",
    ".env",
    ".toml",
    ".ini",
    ".cfg",
}


def read_file(relative_path: str) -> str:
    full_path = resolve_workspace_path(relative_path)
    if not full_path.exists() or not full_path.is_file():
        raise AgentError(f"File not found: {relative_path}")
    if full_path.stat().st_size > MAX_FILE_SIZE:
        raise AgentError(f"File is too large to open in the editor: {relative_path}")
    return full_path.read_text(encoding="utf-8")


def write_file(relative_path: str, content: str) -> str:
    assert_writable("write_file", relative_path)
    full_path = resolve_workspace_path(relative_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return f"Saved {relative_path}"


def run_command(command: str) -> dict[str, Any]:
    tokens = shlex.split(command)
    if not tokens:
        raise AgentError("Command is empty.")

    first = tokens[0]
    if first in BLOCKED_COMMAND_TOKENS:
        raise AgentError(f"Blocked command for safety: {first}")
    if command_mutates_git(command):
        raise AgentError(
            "The coding agent does not git add/commit/push. Suggest the patch; you apply it."
        )

    process = subprocess.run(
        command,
        shell=True,
        cwd=workspace_root(),
        text=True,
        capture_output=True,
        timeout=COMMAND_TIMEOUT_SECONDS,
    )
    return {
        "command": command,
        "exit_code": process.returncode,
        "stdout": process.stdout[-MAX_FILE_SIZE:],
        "stderr": process.stderr[-MAX_FILE_SIZE:],
    }


def fetch_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AgentError(f"Invalid URL: {url}")

    response = requests.get(
        url,
        timeout=FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": "CodingAgent/0.2"},
    )
    response.raise_for_status()
    return {
        "url": url,
        "content_type": response.headers.get("content-type", ""),
        "status_code": response.status_code,
        "content": response.text[:MAX_FILE_SIZE],
    }


def search_web(query: str) -> dict[str, Any]:
    response = requests.get(
        "https://api.duckduckgo.com/",
        params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
        timeout=FETCH_TIMEOUT_SECONDS,
        headers={"User-Agent": "CodingAgent/0.2"},
    )
    response.raise_for_status()
    payload = response.json()
    related = [
        {"text": item.get("Text"), "url": item.get("FirstURL")}
        for item in payload.get("RelatedTopics", [])
        if isinstance(item, dict) and item.get("FirstURL")
    ][:8]
    return {
        "query": query,
        "abstract": payload.get("AbstractText") or "",
        "abstract_url": payload.get("AbstractURL") or "",
        "related": related,
    }


def search_code(query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[dict[str, Any]]:
    workspace = workspace_root()
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    matches: list[dict[str, Any]] = []

    for root, dirs, filenames in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIR_NAMES]
        rel_root = str(Path(root).relative_to(workspace)).replace("\\", "/")
        if rel_root in SIDEBAR_SHALLOW_DIRS:
            dirs[:] = []
            continue
        for filename in filenames:
            if Path(filename).suffix.lower() not in TEXT_EXTENSIONS and filename not in {".gitignore", "Dockerfile"}:
                continue
            full_path = Path(root) / filename
            if full_path.stat().st_size > MAX_FILE_SIZE:
                continue
            try:
                lines = full_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            relative_path = str(full_path.relative_to(workspace))
            for line_no, line in enumerate(lines, start=1):
                if pattern.search(line):
                    matches.append(
                        {
                            "path": relative_path,
                            "line": line_no,
                            "text": line.strip()[:240],
                        }
                    )
                    if len(matches) >= max_results:
                        return matches
    return matches


def git_status() -> dict[str, Any]:
    result = run_command("git status --short --branch")
    return result


def git_diff(path: str = "") -> dict[str, Any]:
    command = f"git diff -- {shlex.quote(path)}" if path else "git diff"
    return run_command(command)


TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "list_files", "description": "List all files in the workspace."}},
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the workspace.",
            "parameters": {
                "type": "object",
                "properties": {"relative_path": {"type": "string"}},
                "required": ["relative_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create or overwrite a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "relative_path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["relative_path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Search for text across project source files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command in the workspace (build, test, docker, npm, etc.).",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch a public documentation or web page.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the public web for docs, APIs, deployment steps, or examples.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    {"type": "function", "function": {"name": "git_status", "description": "Show git branch and changed files."}},
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": "Show git diff for the workspace or one file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
            },
        },
    },
]


TOOL_ALIASES = {
    "listfiles": "list_files",
    "list_files": "list_files",
    "list": "list_files",
    "readfile": "read_file",
    "read_file": "read_file",
    "writefile": "write_file",
    "write_file": "write_file",
    "searchcode": "search_code",
    "search_code": "search_code",
    "grep": "search_code",
    "runcommand": "run_command",
    "run_command": "run_command",
    "terminal": "run_command",
    "fetchurl": "fetch_url",
    "fetch_url": "fetch_url",
    "searchweb": "search_web",
    "search_web": "search_web",
    "web_search": "search_web",
    "gitstatus": "git_status",
    "git_status": "git_status",
    "gitdiff": "git_diff",
    "git_diff": "git_diff",
}


def normalize_tool_name(name: str) -> str:
    key = (name or "").strip().lower().replace("-", "_")
    return TOOL_ALIASES.get(key, key)


def normalize_tool_args(name: str, args: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(args or {})
    if name in {"read_file", "write_file"}:
        if "relative_path" not in normalized:
            for alt in ("path", "file", "filepath", "file_path", "filename"):
                if alt in normalized:
                    normalized["relative_path"] = normalized[alt]
                    break
    if name == "run_command" and "command" not in normalized and "cmd" in normalized:
        normalized["command"] = normalized["cmd"]
    if name == "search_code" and "query" not in normalized and "pattern" in normalized:
        normalized["query"] = normalized["pattern"]
    if name == "search_web" and "query" not in normalized and "q" in normalized:
        normalized["query"] = normalized["q"]
    if name == "fetch_url" and "url" not in normalized and "link" in normalized:
        normalized["url"] = normalized["link"]
    return normalized


def run_tool(name: str, args: dict[str, Any]) -> Any:
    normalized_name = normalize_tool_name(name)
    normalized_args = normalize_tool_args(normalized_name, args)

    if normalized_name == "list_files":
        return list_files()
    if normalized_name == "read_file":
        return read_file(normalized_args["relative_path"])
    if normalized_name == "write_file":
        return write_file(normalized_args["relative_path"], normalized_args["content"])
    if normalized_name == "search_code":
        return search_code(normalized_args["query"], int(normalized_args.get("max_results", MAX_SEARCH_RESULTS)))
    if normalized_name == "run_command":
        return run_command(normalized_args["command"])
    if normalized_name == "fetch_url":
        return fetch_url(normalized_args["url"])
    if normalized_name == "search_web":
        return search_web(normalized_args["query"])
    if normalized_name == "git_status":
        return git_status()
    if normalized_name == "git_diff":
        return git_diff(normalized_args.get("path", ""))
    raise AgentError(f"Unknown tool requested: {name}")
