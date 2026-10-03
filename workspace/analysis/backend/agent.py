import json
import os
import re
from collections.abc import Generator
from typing import Any

import requests

from .codebase_index import codebase_context_text
from .project_rules import load_project_rules
from .redmine_knowledge import redmine_system_section
from .sessions import append_message, get_session
from .tools import TOOLS_SCHEMA, normalize_tool_name, read_file as read_workspace_file, run_tool
from .workspace import AgentError, get_workspace_info

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/v1/chat/completions")
OLLAMA_CHAT_URL = os.environ.get("OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_TAGS_URL = os.environ.get("OLLAMA_TAGS_URL", "http://127.0.0.1:11434/api/tags")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:14b")
MAX_AGENT_TURNS = int(os.environ.get("CODING_AGENT_MAX_AGENT_TURNS", "12"))
# 1.5b/0.5b on CPU cannot finish a tools+huge-prompt call before Ollama's 5m cutoff.
SMALL_MODEL_MARKERS = (":0.5b", ":1b", ":1.5b", ":3b")
FAST_CPU_MODELS = ("qwen2.5-coder:0.5b", "qwen2.5-coder:1.5b")
CHAT_TIMEOUT_SMALL = int(os.environ.get("CODING_AGENT_CHAT_TIMEOUT_SMALL", "90"))
CHAT_TIMEOUT_FULL = int(os.environ.get("CODING_AGENT_CHAT_TIMEOUT", "120"))
CONTEXT_FILE_CHARS = 1800
RULE_CHARS = 2500
JSON_TOOL_RE = re.compile(r"\{[^{}]*\"name\"\s*:\s*\"([^\"]+)\"[^{}]*\"arguments\"\s*:\s*(\{.*?\})[^{}]*\}", re.DOTALL)


def list_models() -> list[str]:
    try:
        response = requests.get(OLLAMA_TAGS_URL, timeout=10)
        response.raise_for_status()
        models = response.json().get("models", [])
        return [model.get("name", "") for model in models if model.get("name")]
    except Exception:  # noqa: BLE001
        return [OLLAMA_MODEL]


def resolve_model(requested: str | None = None) -> str:
    available = list_models()
    if requested and requested in available:
        return requested
    if OLLAMA_MODEL in available:
        return OLLAMA_MODEL
    for name in FAST_CPU_MODELS:
        if name in available:
            return name
    return available[0] if available else (requested or OLLAMA_MODEL)


def model_uses_tools(model: str | None) -> bool:
    name = (model or "").lower()
    return not any(marker in name for marker in SMALL_MODEL_MARKERS)


def _response_mode_instructions(mode: str) -> str:
    if mode == "step":
        return (
            "Answer style: STEP-BY-STEP.\n"
            "- Use numbered steps (1., 2., 3.).\n"
            "- One short idea per line.\n"
            "- Max 8 steps unless the user asks for more.\n"
            "- No long paragraphs."
        )
    if mode == "guided":
        return (
            "Answer style: GUIDED READ.\n"
            "- Use numbered steps (1., 2., 3.).\n"
            "- One short sentence per line.\n"
            "- Keep each line under 120 characters.\n"
            "- Max 6 steps, then stop and wait for the user."
        )
    return (
        "Answer style: QUICK.\n"
        "- Be brief and scannable.\n"
        "- Prefer 3-6 bullet points or 1 short paragraph.\n"
        "- Lead with the answer, then only essential details.\n"
        "- Avoid walls of text."
    )


def _build_system_prompt(
    context_files: list[str] | None = None,
    response_mode: str = "quick",
    compact: bool = False,
) -> str:
    workspace = get_workspace_info()
    attached = list(context_files or [])
    context_chunks: list[str] = []
    for relative_path in attached:
        try:
            content = read_workspace_file(relative_path)
            context_chunks.append(f"### {relative_path}\n{content[:CONTEXT_FILE_CHARS]}")
        except AgentError:
            context_chunks.append(f"### {relative_path}\n(could not read this file)")

    if compact:
        sections = [
            "You are a learning assistant for Empever.",
            "Ansif opens a file in 01_Build and asks what it contains. You explain it so he can Save to Notes.",
            "Write a short markdown note: one heading, then 4–8 bullets.",
            "Cover: what the file is, what it contains, why it exists in this project.",
            "Do not write or git-commit jcatrysse_ror/redmine/. Do not name client hosts, mailboxes, or their GitHub.",
            "No tools. No deploy. No patches unless asked. Answer from the open file.",
        ]
        if attached:
            sections.append("Open in editor / attached: " + ", ".join(attached))
        if context_chunks:
            sections.append("Attached file contents:\n" + "\n\n".join(context_chunks))
        return "\n\n".join(sections)

    sections = [
        "You are Empever Coding Agent — the Build worker. Ansif is on the paid contract; you run this folder.",
        f"Active workspace: {workspace['path']}",
        "Root is 01_Build: jcatrysse_ror (read-only clone, actual work). Skill demos: _common/ansif/profile/_referrals/<stack>/ (not actual work).",
        "Learning docs: studies/learns/<topic>/. Never write or git-commit jcatrysse_ror/redmine/.",
        "Never put client hosts, mailboxes, or their GitHub in text meant for a public post.",
        _response_mode_instructions(response_mode),
        "Codebase index:\n" + codebase_context_text(compact=False),
        "Inspect before proposing edits. Use search_code, git_status, git_diff, run_command (no git commit).",
        "Put new code in _common/ansif/profile/_referrals/<stack>/ unless it is a named training client folder; learning markdown under studies/learns/; suggest patches for the clone.",
        "Use exact tool names: list_files, read_file, write_file, search_code, run_command, fetch_url, search_web, git_status, git_diff.",
    ]
    redmine = redmine_system_section()
    if redmine:
        sections.append(redmine)
    rules = load_project_rules()
    if rules:
        sections.append("Project rules:\n" + rules[:RULE_CHARS])
    if attached:
        sections.append("Open in editor / attached: " + ", ".join(attached))
    if context_chunks:
        sections.append("Attached file contents:\n" + "\n\n".join(context_chunks))
    return "\n\n".join(sections)


def _history_to_messages(session_id: str | None) -> list[dict[str, Any]]:
    if not session_id:
        return []
    try:
        session = get_session(session_id)
    except FileNotFoundError:
        return []
    messages: list[dict[str, Any]] = []
    for item in session.get("messages", [])[-20:]:
        role = item.get("role")
        text = item.get("text", "")
        if role in {"user", "assistant"} and text:
            messages.append({"role": role, "content": text})
    return messages


def _extract_message(payload: dict[str, Any]) -> dict[str, Any]:
    choices = payload.get("choices") or []
    if not choices:
        raise AgentError(f"Unexpected model response: {payload}")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise AgentError(f"Unexpected message payload: {payload}")
    return message


def _parse_content_tool_calls(content: str) -> list[dict[str, Any]]:
    if not content or "\"name\"" not in content:
        return []
    calls: list[dict[str, Any]] = []
    for index, match in enumerate(JSON_TOOL_RE.finditer(content)):
        name = match.group(1)
        try:
            arguments = json.loads(match.group(2))
        except json.JSONDecodeError:
            continue
        calls.append(
            {
                "id": f"content-tool-{index}",
                "type": "function",
                "function": {"name": name, "arguments": json.dumps(arguments)},
            }
        )
    return calls


def _post_chat(messages: list[dict[str, Any]], model: str | None = None, use_tools: bool = True) -> dict[str, Any]:
    resolved = resolve_model(model)
    payload: dict[str, Any] = {
        "model": resolved,
        "messages": messages,
        "temperature": 0.1,
        "max_tokens": 256 if not use_tools else 1024,
    }
    if use_tools:
        payload["tools"] = TOOLS_SCHEMA
    timeout = CHAT_TIMEOUT_SMALL if not use_tools else CHAT_TIMEOUT_FULL
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.Timeout as exc:
        raise AgentError(
            f"Local model {resolved} timed out after {timeout}s. "
            "Ask a shorter question, or pick qwen2.5-coder:0.5b for a faster CPU reply."
        ) from exc
    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = exc.response.text[:300]
        except Exception:  # noqa: BLE001
            detail = str(exc)
        raise AgentError(f"Ollama error for {resolved}: {detail or exc}") from exc


def _ollama_plain_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    plain: list[dict[str, str]] = []
    for item in messages:
        role = item.get("role")
        if role not in {"system", "user", "assistant"}:
            continue
        plain.append({"role": role, "content": item.get("content") or ""})
    return plain


def _stream_chat_text(messages: list[dict[str, Any]], model: str) -> Generator[str, None, None]:
    payload = {
        "model": model,
        "messages": _ollama_plain_messages(messages),
        "stream": True,
        "options": {
            "num_ctx": 2048,
            "num_predict": 280,
            "temperature": 0.1,
        },
    }
    try:
        with requests.post(
            OLLAMA_CHAT_URL,
            json=payload,
            stream=True,
            timeout=(15, CHAT_TIMEOUT_SMALL),
        ) as response:
            response.raise_for_status()
            for raw in response.iter_lines():
                if not raw:
                    continue
                data = json.loads(raw)
                if data.get("error"):
                    raise AgentError(str(data["error"]))
                piece = (data.get("message") or {}).get("content") or ""
                if piece:
                    yield piece
                if data.get("done"):
                    return
    except requests.Timeout as exc:
        raise AgentError(
            f"Local model {model} timed out. Pick qwen2.5-coder:0.5b for a faster CPU reply."
        ) from exc
    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = exc.response.text[:300]
        except Exception:  # noqa: BLE001
            detail = str(exc)
        raise AgentError(f"Ollama error for {model}: {detail or exc}") from exc


def run_agent(
    user_prompt: str,
    session_id: str | None = None,
    context_files: list[str] | None = None,
    model: str | None = None,
    response_mode: str = "quick",
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    reply = ""
    for event in run_agent_stream(user_prompt, session_id, context_files, model, response_mode):
        events.append(event)
        if event.get("type") == "assistant":
            reply = event.get("text", "")
        if event.get("type") == "error":
            raise AgentError(event.get("text", "Agent failed"))
    return {"reply": reply, "events": events}


def run_agent_stream(
    user_prompt: str,
    session_id: str | None = None,
    context_files: list[str] | None = None,
    model: str | None = None,
    response_mode: str = "quick",
) -> Generator[dict[str, Any], None, None]:
    history = _history_to_messages(session_id)
    if session_id:
        append_message(session_id, "user", user_prompt, {"context_files": context_files or []})

    resolved = resolve_model(model)
    # Learn desk: explain the open file. No tool loop — answers become Content Notes.
    use_tools = False
    max_turns = 1 if not use_tools else MAX_AGENT_TURNS
    user_text = user_prompt
    if context_files:
        user_text = f"Open in editor: {', '.join(context_files)}\n\n{user_prompt}"

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": _build_system_prompt(context_files, response_mode, compact=not use_tools),
        },
        *(history[-6:] if not use_tools else history),
        {"role": "user", "content": user_text},
    ]

    yield {
        "type": "status",
        "text": f"Using {resolved}" + (" (quick, no tools)" if not use_tools else "") + "…",
    }

    for turn in range(max_turns):
        yield {"type": "status", "text": f"Thinking (step {turn + 1}/{max_turns})..."}
        if not use_tools:
            reply = ""
            try:
                for piece in _stream_chat_text(messages, resolved):
                    reply += piece
                    yield {"type": "assistant", "text": reply}
            except Exception as exc:  # noqa: BLE001
                yield {"type": "error", "text": str(exc)}
                return
            reply = reply.strip() or "(empty model reply)"
            yield {"type": "assistant", "text": reply}
            if session_id:
                append_message(session_id, "assistant", reply)
            yield {"type": "done"}
            return
        try:
            message = _extract_message(_post_chat(messages, resolved, use_tools=True))
        except Exception as exc:  # noqa: BLE001
            yield {"type": "error", "text": str(exc)}
            return

        messages.append(message)
        tool_calls = message.get("tool_calls") or []
        if use_tools and not tool_calls:
            tool_calls = _parse_content_tool_calls(message.get("content") or "")
        if not tool_calls:
            reply = (message.get("content") or "").strip() or "(empty model reply)"
            yield {"type": "assistant", "text": reply}
            if session_id:
                append_message(session_id, "assistant", reply)
            yield {"type": "done"}
            return

        for tool_call in tool_calls:
            function = tool_call.get("function") or {}
            raw_name = function.get("name", "")
            name = normalize_tool_name(raw_name)
            raw_arguments = function.get("arguments") or "{}"
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                arguments = {}

            yield {"type": "tool_start", "name": name, "args": arguments}
            try:
                result = run_tool(name, arguments)
            except Exception as exc:  # noqa: BLE001
                result = {"error": str(exc)}
            yield {"type": "tool_end", "name": name, "result": result}

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id", name),
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=True),
                }
            )

    error_text = "Agent stopped after reaching the safety turn limit."
    yield {"type": "error", "text": error_text}
    if session_id:
        append_message(session_id, "assistant", error_text)
