import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_BUILD_ROOT = Path("/home/ansif/works/01_Build")
_DUMMY_ROOT = PROJECT_ROOT.parent / "tenants" / "dummy_client"
_env_workspace = os.environ.get("CODING_AGENT_WORKSPACE") or os.environ.get("REDMINE_BUILD_PATH")
if _env_workspace:
    DEFAULT_WORKSPACE = Path(_env_workspace).expanduser()
elif _BUILD_ROOT.is_dir():
    DEFAULT_WORKSPACE = _BUILD_ROOT
else:
    DEFAULT_WORKSPACE = PROJECT_ROOT / "workspace"
CURRENT_WORKSPACE = DEFAULT_WORKSPACE
IGNORED_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    "dist",
    ".venv",
    ".run",
    "log",
    "tmp",
    "coverage",
}
SKIP_TOP_LEVEL: set[str] = set()
# Huge clones stay as a single folder in the IDE tree; agent can still read_file inside them.
SIDEBAR_SHALLOW_DIRS = {
    "jcatrysse_ror/redmine",
    "jcatrysse_ror/sample_git_repo",
}
NOTES_TRACK_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")

DEFAULT_WORKSPACE.mkdir(parents=True, exist_ok=True)


class AgentError(RuntimeError):
    pass


def workspace_root() -> Path:
    CURRENT_WORKSPACE.mkdir(parents=True, exist_ok=True)
    return CURRENT_WORKSPACE


def get_workspace_info() -> dict[str, str]:
    workspace = workspace_root()
    return {"path": str(workspace), "name": workspace.name}


def set_workspace(folder_path: str) -> dict[str, str]:
    global CURRENT_WORKSPACE
    candidate = Path(folder_path).expanduser().resolve()
    if not candidate.exists() or not candidate.is_dir():
        raise AgentError(f"Workspace folder not found: {folder_path}")
    CURRENT_WORKSPACE = candidate
    return get_workspace_info()


def apply_platform_client(slug: str) -> dict[str, str]:
    """Sevendyne uses the live 01_Build tree. Dummy client uses empty tenant folders."""
    global CURRENT_WORKSPACE
    client = (slug or "sevendyne").strip().lower()
    if client == "dummy_client":
        build = _DUMMY_ROOT / "01_Build"
        build.mkdir(parents=True, exist_ok=True)
        (build / "studies" / "learns").mkdir(parents=True, exist_ok=True)
        (_DUMMY_ROOT / "04_Operate").mkdir(parents=True, exist_ok=True)
        CURRENT_WORKSPACE = build
    else:
        CURRENT_WORKSPACE = _BUILD_ROOT if _BUILD_ROOT.is_dir() else DEFAULT_WORKSPACE
    CURRENT_WORKSPACE.mkdir(parents=True, exist_ok=True)
    return get_workspace_info()


def open_workspace_file(workspace_file_path: str) -> dict[str, str]:
    workspace_file = Path(workspace_file_path).expanduser().resolve()
    if not workspace_file.exists() or not workspace_file.is_file():
        raise AgentError(f"Workspace file not found: {workspace_file_path}")

    try:
        payload = json.loads(workspace_file.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise AgentError(f"Invalid workspace file: {workspace_file_path}") from exc

    folders = payload.get("folders") or []
    if not folders:
        raise AgentError("Workspace file has no folders.")

    folder_path = folders[0].get("path")
    if not folder_path:
        raise AgentError("Workspace file first folder is missing a path.")

    folder = Path(folder_path)
    if not folder.is_absolute():
        folder = (workspace_file.parent / folder).resolve()
    return set_workspace(str(folder))


def resolve_workspace_path(relative_path: str) -> Path:
    """Jail to 01_Build. Old Notes/learns/ paths map to studies/learns/."""
    rel = Path(relative_path)
    parts = rel.parts
    workspace = workspace_root()
    if parts and parts[0] == "Notes":
        rest = Path(*parts[1:]) if len(parts) > 1 else Path()
        rel = Path("studies") / rest
    candidate = (workspace / rel).resolve()
    if workspace not in candidate.parents and candidate != workspace:
        raise AgentError(f"Path escapes workspace: {relative_path}")
    return candidate


def _relative_posix(path: Path, workspace: Path) -> str:
    rel = path.relative_to(workspace)
    if rel == Path("."):
        return ""
    return str(rel).replace("\\", "/")


def list_entries() -> list[dict[str, Any]]:
    workspace = workspace_root()
    entries: list[dict[str, Any]] = []
    for root, dirs, filenames in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIR_NAMES]
        root_path = Path(root)
        relative_root = root_path.relative_to(workspace)
        if relative_root == Path("."):
            dirs[:] = [d for d in dirs if d not in SKIP_TOP_LEVEL]
        dirs.sort()
        filenames.sort()
        rel_str = _relative_posix(root_path, workspace)
        depth = 0 if relative_root == Path(".") else len(relative_root.parts)
        if relative_root != Path("."):
            entries.append(
                {
                    "path": str(relative_root),
                    "name": root_path.name,
                    "type": "directory",
                    "depth": depth - 1,
                }
            )
        if rel_str in SIDEBAR_SHALLOW_DIRS:
            dirs[:] = []
        for filename in filenames:
            full_path = root_path / filename
            relative_path = full_path.relative_to(workspace)
            entries.append(
                {
                    "path": str(relative_path),
                    "name": filename,
                    "type": "file",
                    "depth": len(relative_path.parts) - 1,
                }
            )
    return entries


def list_files() -> list[str]:
    return [entry["path"] for entry in list_entries() if entry["type"] == "file"]


def list_notes_tracks() -> list[dict[str, str]]:
    learns = workspace_root() / "studies" / "learns"
    tracks: list[dict[str, str]] = []
    if learns.is_dir():
        for child in sorted(learns.iterdir()):
            if child.is_dir() and NOTES_TRACK_RE.match(child.name):
                tracks.append(
                    {
                        "id": child.name,
                        "path": f"studies/learns/{child.name}",
                    }
                )
    ids = {track["id"] for track in tracks}
    if "from-coding-agent" not in ids:
        tracks.append({"id": "from-coding-agent", "path": "studies/learns/from-coding-agent"})
    return tracks


def _note_slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")[:48]
    return slug or "answer"


def save_chat_note(track: str, content: str, title: str = "") -> dict[str, str]:
    from .contract_guard import assert_writable

    track_id = (track or "").strip().lower()
    if not NOTES_TRACK_RE.match(track_id):
        raise AgentError("Pick a notes track under 01_Build/studies/learns/")
    body = (content or "").strip()
    if not body:
        raise AgentError("Nothing to save — the answer is empty.")
    heading = (title or "").strip() or body.splitlines()[0][:80]
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    filename = f"{stamp}-{_note_slug(heading)}.md"
    relative = f"studies/learns/{track_id}/{filename}"
    assert_writable("write_file", relative)
    full_path = resolve_workspace_path(relative)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = f"# {heading}\n\nSaved from coding-agent chat on {datetime.now().strftime('%Y-%m-%d %H:%M')}.\n\n{body}\n"
    full_path.write_text(markdown, encoding="utf-8")
    return {
        "path": relative,
        "content_path": str(full_path),
        "track": track_id,
        "message": f"Saved to 01_Build/studies/learns/{track_id}/{filename}",
    }
