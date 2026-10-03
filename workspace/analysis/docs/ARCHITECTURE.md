# Empever — Architecture & Code Flow

Local-first Cursor/Claude-style coding workspace. The LLM runs on **your machine via Ollama**; there is no cloud model dependency and no user auth in this MVP.

**Repo:** [github.com/ansifi/coding-agent](https://github.com/ansifi/coding-agent)

---

## What it is

| Surface | Role |
|---------|------|
| **Frontend** | React + Vite + Monaco — file tree, editor, terminal panel, agent chat |
| **Backend** | FastAPI on `:8006` — workspace APIs, sessions, agent tool loop |
| **Desktop** | Electron shell — native Open Folder / Open Workspace, spawns API + UI |
| **Ollama** | Local OpenAI-compatible chat completions + tool calling |

Default sandbox: `01_Build/` when that folder exists, else repo `workspace/`. Desktop (or API) can switch folder. Contract git under `jcatrysse_ror/redmine/` stays read-only.

---

## Layout

```text
coding-agent/
├── backend/
│   ├── app.py              HTTP routes (FastAPI)
│   ├── agent.py            LLM tool loop + system prompt
│   ├── tools.py            Tool registry + implementations
│   ├── workspace.py        Active root + path jail
│   ├── sessions.py         Chat JSON under .run/sessions/
│   ├── codebase_index.py   Lightweight workspace summary for the prompt
│   └── project_rules.py    Loads .coding-agent/rules.md, AGENTS.md, …
├── frontend/src/
│   ├── App.jsx             Main UI + SSE consumer
│   └── AssistantMessage.jsx
├── desktop/
│   ├── main.js             Process spawn, menus, dialogs
│   └── preload.js          window.codingAgentDesktop bridge
├── scripts/                install, dev-start, desktop-start, smoke-test
├── workspace/              Default project sandbox
└── docs/                   Install, desktop, roadmap, this doc
```

---

## Architecture

```text
┌──────────────────────┐         ┌─────────────────────┐
│ Electron (desktop)   │         │ Browser (dev-start) │
│ main.js + preload    │         │ Vite UI :5176       │
└──────────┬───────────┘         └──────────┬──────────┘
           │ IPC / file dialogs             │
           ▼                                ▼
      React + Monaco  ──── fetch / SSE ────►  FastAPI :8006
                                                   │
                    ┌──────────────────────────────┼──────────────────────┐
                    ▼                              ▼                      ▼
              workspace.py                   sessions.py              agent.py
           CURRENT_WORKSPACE              .run/sessions/*.json            │
                    ▲                              ▲                      ▼
                    │                              │         Ollama :11434
              tools.py ◄───────────────────────────┘    /v1/chat/completions
         read/write/search/git/shell/web              + tool_calls
```

**Trust model:** localhost-only. Safety is path confinement inside the workspace root plus a short blocklist of shell command tokens. Not for public hosting without auth and stronger controls.

---

## Code flow — agent chat

1. User submits a prompt in `App.jsx` (optional `@file` attachments, model, response mode: `quick` | `step` | `guided`).
2. If needed, **POST `/api/sessions`** creates a chat session.
3. **POST `/api/agent/stream`** with `{ prompt, session_id, context_files, model, response_mode }`.
4. `run_agent_stream` (`backend/agent.py`):
   - Appends the user message to the session
   - Builds messages: **system prompt** + last ~20 history turns + user
   - Loops up to `CODING_AGENT_MAX_AGENT_TURNS` (default 12):
     - Calls Ollama with `TOOLS_SCHEMA`
     - Emits SSE events: `status`, `tool_start`, `tool_end`, `assistant`, `done`, `error`
     - If the model returns `tool_calls` → `run_tool` → feed results back as tool messages → next turn
     - If no tools → final assistant reply, persist, stop
5. Frontend reads the SSE body and updates the activity log + chat bubble.

Non-stream path: **POST `/api/agent/execute`** → same loop, returns `{ reply, events }`.

**Note:** “Streaming” means **tool/status event streaming** to the UI. Each Ollama turn is still a full (non-token-streamed) completion.

---

## Code flow — editor & desktop

| Action | Path |
|--------|------|
| List tree | `GET /api/tree` → `workspace.list_entries` |
| Open file | `GET /api/file?path=` → `tools.read_file` |
| Save file | `PUT /api/file` → `tools.write_file` |
| Run command | `POST /api/command/run` → `tools.run_command` |
| Open folder (desktop) | Dialog → `POST /api/workspace/open-folder` → rebuild index → UI event |

Desktop bridge: `window.codingAgentDesktop` (`desktop/preload.js`) — `apiBase`, `openFolder`, `openWorkspace`, `onWorkspaceChanged`.

---

## Core logic

### System prompt (`agent.py`)

Built from:

- Role instructions (“Coding Agent”, inspect before edit, etc.)
- Active workspace path
- Response-mode style (`quick` / `step` / `guided`)
- Codebase index summary
- Project rules files (if present)
- `@file` contents (truncated)

### Tools (`tools.py`)

| Tool | Behavior |
|------|----------|
| `list_files` | Workspace listing |
| `read_file` / `write_file` | Sandboxed R/W (size capped) |
| `search_code` | Regex walk of text files |
| `run_command` | Shell in workspace; blocks tokens like `rm`, `sudo`, … |
| `git_status` / `git_diff` | Via shell helpers |
| `search_web` | DuckDuckGo Instant Answer |
| `fetch_url` | HTTP(S) GET, truncated |

Alias normalization maps common names (`grep` → `search_code`, etc.).

### Workspace (`workspace.py`)

- Module-global `CURRENT_WORKSPACE` (default: `01_Build/` if present, else repo `workspace/`)
- `resolve_workspace_path` prevents escaping the root
- Ignores heavy dirs: `.git`, `node_modules`, `.venv`, `dist`, …

### Sessions (`sessions.py`)

JSON files under `.run/sessions/{id}.json` — id, title, timestamps, messages.

### Project rules (`project_rules.py`)

Loaded into the prompt if found, in order:

1. `.coding-agent/rules.md`
2. `AGENTS.md`
3. `.cursorrules`
4. `CLAUDE.md`

---

## Main API surface

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Status, workspace, models, feature flags |
| GET | `/api/models` | Ollama tag list |
| GET | `/api/tree`, `/api/files` | File browser |
| POST | `/api/workspace/open-folder`, `open-workspace` | Switch root + index |
| GET | `/api/workspace/index` | Codebase index |
| GET/POST | `/api/sessions`, `/api/sessions/{id}` | Chat history |
| GET/PUT | `/api/file` | Editor R/W |
| POST | `/api/command/run` | Terminal |
| GET | `/api/git/status`, `/api/git/diff` | Git |
| POST | `/api/agent/execute` | Sync agent |
| POST | `/api/agent/stream` | SSE agent |

---

## Config (environment)

| Variable | Default | Use |
|----------|---------|-----|
| `OLLAMA_URL` | `http://127.0.0.1:11434/v1/chat/completions` | Chat API |
| `OLLAMA_TAGS_URL` | `http://127.0.0.1:11434/api/tags` | Model list |
| `OLLAMA_MODEL` | `qwen2.5-coder:14b` | Default model |
| `CODING_AGENT_MAX_AGENT_TURNS` | `12` | Agent loop cap |
| `CODING_AGENT_BACKEND_PORT` | `8006` | Desktop / scripts |
| `CODING_AGENT_UI_PORT` | `5176` | Desktop UI port |
| `CODING_AGENT_API_BASE` | `http://127.0.0.1:8006` | Desktop preload / smoke |
| `CORS_ALLOW_ORIGINS` | `http://127.0.0.1:5176,…` | FastAPI CORS |
| `VITE_API_BASE` | (optional) | Frontend override |

`.env` under `backend/` is documented for humans; the app reads **process environment** (no automatic `load_dotenv` today).

---

## How to run

```bash
./scripts/install
ollama serve
ollama pull qwen2.5-coder:14b   # or a smaller coder model

./scripts/dev-start             # browser: UI :5176, API :8006
# or
./scripts/install-desktop && ./scripts/desktop-start

./scripts/smoke-test.sh
```

---

## Design caveats (MVP)

1. **No auth** — assume a trusted local user.
2. **Single workspace per process** — global state; reopen folder after restart.
3. **Shell safety is shallow** — first-token blocklist only.
4. **No token-level LLM streaming** yet — SSE is for agent/tool lifecycle events.
5. Roadmap gaps (see [PARITY_ROADMAP.md](PARITY_ROADMAP.md)): apply-diff UI, MCP, semantic index, credential vault, packaging.

---

## Related docs

- [INSTALL.md](INSTALL.md) — fresh machine setup
- [LOCAL_RUN.md](LOCAL_RUN.md) — day-to-day browser run
- [DESKTOP_UBUNTU.md](DESKTOP_UBUNTU.md) — Electron on Ubuntu
- [PARITY_ROADMAP.md](PARITY_ROADMAP.md) — Cursor/Claude feature parity plan
