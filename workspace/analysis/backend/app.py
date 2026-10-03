import json
import os
import re
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .agent import list_models, resolve_model, run_agent, run_agent_stream
from .codebase_index import build_codebase_index
from .contract_guard import workspace_is_contract
from .gemini_assists import assist_task, gemini_configured
from .sessions import create_session, get_session, list_sessions
from .tools import git_diff, git_status, read_file, run_command, write_file
from .workspace import (
    AgentError,
    apply_platform_client,
    get_workspace_info,
    list_entries,
    list_files,
    list_notes_tracks,
    open_workspace_file,
    save_chat_note,
    set_workspace,
)


class AgentRequest(BaseModel):
    prompt: str
    session_id: str | None = None
    context_files: list[str] = Field(default_factory=list)
    model: str | None = None
    response_mode: str = "quick"


class FileSaveRequest(BaseModel):
    path: str
    content: str


class CommandRequest(BaseModel):
    command: str


class WorkspaceOpenRequest(BaseModel):
    path: str


class ClientOpenRequest(BaseModel):
    client: str = "sevendyne"


class SessionCreateRequest(BaseModel):
    title: str = "New chat"


class AssistRequest(BaseModel):
    task: str
    similar: list[str] = Field(default_factory=list)


class NotesSaveRequest(BaseModel):
    track: str = "jan-redmine"
    content: str
    title: str = ""


class SkillsAnalyzeRequest(BaseModel):
    kind: str = "project"
    title: str = ""
    path: str = ""
    description: str = ""


SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


app = FastAPI(title="Empever Skills API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "CORS_ALLOW_ORIGINS",
        "http://127.0.0.1:5176,http://localhost:5176,http://127.0.0.1:4040,http://localhost:4040",
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, object]:
    workspace = get_workspace_info()
    return {
        "status": "ok",
        "workspace": str(Path(workspace["path"]).resolve()),
        "model": resolve_model(),
        "models": list_models(),
        "features": [
            "open-folder",
            "open-workspace",
            "chat-sessions",
            "agent-tools",
            "web-search",
            "git",
            "project-rules",
            "streaming",
            "codebase-index",
            "redmine-knowledge",
            "save-to-notes",
        ],
        "gemini": gemini_configured(),
        "contract_readonly": workspace_is_contract(),
        "contract_clone_protected": True,
        "workspace_name": workspace.get("name"),
    }


@app.get("/api/models")
def api_models() -> dict[str, object]:
    return {"models": list_models(), "default": resolve_model()}


@app.get("/api/files")
def api_files() -> dict[str, list[str]]:
    return {"files": list_files()}


@app.get("/api/tree")
def api_tree() -> dict[str, object]:
    return {"workspace": get_workspace_info(), "entries": list_entries()}


@app.post("/api/workspace/open-folder")
def api_open_folder(request: WorkspaceOpenRequest) -> dict[str, object]:
    try:
        workspace = set_workspace(request.path)
        index = build_codebase_index()
        return {"status": "success", "workspace": workspace, "index": index}
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workspace/open-client")
def api_open_client(request: ClientOpenRequest) -> dict[str, object]:
    try:
        workspace = apply_platform_client(request.client)
        index = build_codebase_index()
        return {"status": "success", "workspace": workspace, "index": index}
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/workspace/open-workspace")
def api_open_workspace(request: WorkspaceOpenRequest) -> dict[str, object]:
    try:
        workspace = open_workspace_file(request.path)
        index = build_codebase_index()
        return {"status": "success", "workspace": workspace, "index": index}
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/workspace/index")
def api_workspace_index() -> dict[str, object]:
    try:
        return {"status": "success", "index": build_codebase_index()}
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/sessions")
def api_sessions() -> dict[str, object]:
    return {"sessions": list_sessions()}


@app.post("/api/sessions")
def api_create_session(request: SessionCreateRequest) -> dict[str, object]:
    return {"session": create_session(request.title)}


@app.get("/api/sessions/{session_id}")
def api_get_session(session_id: str) -> dict[str, object]:
    try:
        return {"session": get_session(session_id)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/file")
def api_file(path: str) -> dict[str, str]:
    try:
        return {"content": read_file(path)}
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.put("/api/file")
def api_save_file(request: FileSaveRequest) -> dict[str, str]:
    try:
        message = write_file(request.path, request.content)
        return {"status": "success", "message": message}
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/notes/tracks")
def api_notes_tracks() -> dict[str, object]:
    return {"tracks": list_notes_tracks()}


@app.post("/api/notes/save")
def api_save_note(request: NotesSaveRequest) -> dict[str, str]:
    try:
        result = save_chat_note(request.track, request.content, request.title)
        return {"status": "success", **result}
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _split_notes_and_course(text: str) -> tuple[str, str]:
    raw = (text or "").strip()
    if not raw:
        return "", ""
    upper = raw.upper()
    course_at = upper.find("## COURSE")
    notes_at = upper.find("## NOTES")
    if course_at >= 0 and notes_at >= 0:
        if notes_at < course_at:
            notes = raw[notes_at:course_at].split("\n", 1)[-1].strip()
            course = raw[course_at:].split("\n", 1)[-1].strip()
        else:
            course = raw[course_at:notes_at].split("\n", 1)[-1].strip()
            notes = raw[notes_at:].split("\n", 1)[-1].strip()
        return notes, course
    if course_at >= 0:
        return raw[:course_at].strip(), raw[course_at:].split("\n", 1)[-1].strip()
    parts = raw.split("\n\n", 1)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return raw, raw


def _fallback_skills_pack(kind: str, title: str, path: str, description: str) -> tuple[str, str]:
    heading = title or path or kind or "Untitled"
    notes = (
        f"# {heading} — notes\n\n"
        f"- Kind: {kind}\n"
        f"- Path: {path or '(none)'}\n\n"
        f"{description.strip() or 'Describe the brand, service, or solution, then re-run analyse.'}\n\n"
        "Map the pain, the 7.x neighbour if this is a port, the trap, and the test. "
        "No NDA, hosts, mailboxes, or client GitHub.\n"
    )
    course = (
        f"# {heading} — programme\n\n"
        "## Module 1 — See it\nReproduce the current behaviour. Write the click path.\n\n"
        "## Module 2 — Map it\nName the files and the data that move.\n\n"
        "## Module 3 — Change one piece\nPort the intent, not the old file layout.\n\n"
        "## Module 4 — Prove it\nUI again, then a test.\n\n"
        "## Module 5 — Publish\nOne pain how-to. Copy into LinkedIn / Dev.to / X from the Post step.\n"
    )
    return notes, course


@app.post("/api/skills/analyze")
def api_skills_analyze(request: SkillsAnalyzeRequest) -> dict[str, object]:
    kind = (request.kind or "project").strip().lower()
    title = (request.title or "").strip()
    path = (request.path or "").strip()
    description = (request.description or "").strip()
    if path:
        try:
            set_workspace(path)
        except AgentError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    workspace = get_workspace_info()
    prompt = (
        "You are Empever Skills, a training tool. Analyse this "
        f"{kind} and write TWO markdown sections exactly titled ## NOTES and ## COURSE.\n"
        "NOTES: architecture map and teaching notes. No NDA, hosts, mailboxes, or client GitHub.\n"
        "COURSE: a short programme — modules, exercises, what to practise, then how to post a pain how-to.\n"
        f"Title: {title or workspace.get('name')}\n"
        f"Folder: {workspace.get('path')}\n"
        f"Description:\n{description or '(none)'}\n"
        "If the folder is open, read README and a few key files first."
    )
    used_agent = False
    answer = ""
    try:
        result = run_agent(prompt, response_mode="quick")
        answer = str((result or {}).get("reply") or (result or {}).get("answer") or (result or {}).get("text") or "")
        used_agent = bool(answer.strip())
    except Exception:  # noqa: BLE001
        answer = ""
    notes, course = _split_notes_and_course(answer) if used_agent else ("", "")
    if not notes.strip() or not course.strip():
        notes, course = _fallback_skills_pack(kind, title, path, description)
        used_agent = False
    heading = title or Path(workspace["path"]).name
    operate_notes = Path("/home/ansif/works/04_Operate/Empever/notes")
    operate_notes.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")

    def _write_operate(kind: str, body: str) -> dict[str, str]:
        slug = re.sub(r"[^a-z0-9]+", "-", f"{heading} {kind}".lower()).strip("-")[:48] or kind
        filename = f"{stamp}-{slug}.md"
        full = operate_notes / filename
        full.write_text(
            f"# {heading} — {kind}\n\n"
            f"Saved from coding-agent on {datetime.now().strftime('%Y-%m-%d %H:%M')}.\n\n"
            f"{body}\n",
            encoding="utf-8",
        )
        rel = f"04_Operate/Empever/notes/{filename}"
        return {"path": rel, "content_path": str(full)}

    note_saved = _write_operate("notes", notes)
    course_saved = _write_operate("course", course)
    draft_rel = course_saved["path"]
    return {
        "status": "success",
        "used_agent": used_agent,
        "workspace": workspace,
        "notes": notes,
        "course": course,
        "note_path": note_saved.get("path"),
        "course_path": course_saved.get("path"),
        "draft_path": draft_rel,
        "platforms": [
            {"id": "linkedin", "label": "LinkedIn", "compose": "https://www.linkedin.com/feed/"},
            {"id": "devto", "label": "Dev.to", "compose": "https://dev.to/new"},
            {"id": "medium", "label": "Medium", "compose": "https://medium.com/new-story"},
            {"id": "x", "label": "X / Twitter", "compose": "https://twitter.com/compose/tweet"},
            {"id": "hashnode", "label": "Hashnode", "compose": "https://hashnode.com/draft"},
        ],
    }


@app.post("/api/command/run")
def api_run_command(request: CommandRequest) -> dict[str, object]:
    try:
        return {"status": "success", "result": run_command(request.command)}
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/git/status")
def api_git_status() -> dict[str, object]:
    try:
        return {"status": "success", "result": git_status()}
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/git/diff")
def api_git_diff(path: str = "") -> dict[str, object]:
    try:
        return {"status": "success", "result": git_diff(path)}
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/assist")
def api_assist(request: AssistRequest) -> dict[str, object]:
    try:
        return {"status": "success", "result": assist_task(request.task, request.similar)}
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/agent/execute")
def api_execute_agent(request: AgentRequest) -> dict[str, object]:
    try:
        result = run_agent(
            request.prompt,
            session_id=request.session_id,
            context_files=request.context_files,
            model=request.model,
            response_mode=request.response_mode,
        )
        return {"status": "success", "result": result}
    except AgentError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/agent/stream")
def api_execute_agent_stream(request: AgentRequest) -> StreamingResponse:
    def event_stream():
        # Pad so uvicorn/h11 flushes the first event instead of buffering until Ollama returns.
        yield ": " + (" " * 2048) + "\n\n"
        try:
            for event in run_agent_stream(
                request.prompt,
                session_id=request.session_id,
                context_files=request.context_files,
                model=request.model,
                response_mode=request.response_mode,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=True)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'text': str(exc)}, ensure_ascii=True)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=SSE_HEADERS)
