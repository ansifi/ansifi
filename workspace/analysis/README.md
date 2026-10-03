# Analysis

Reads **`01_Build/`** (resources, studies, technicals). Hub card → `front/`. Later: brainstorm and build here with reminders.

Local-first coding workspace (was coding-agent). Ollama by default. Optional Gemini (`GEMINI_API_KEY`) for Redmine pattern assists.

Default workspace is **`/home/ansif/works/01_Build`**. Actual work: `jcatrysse_ror/` (clone read-only). Reference stacks: **`_common/ansif/profile/_referrals/`** (not actual work). A named `01_Build/<client>/` appears when there is a real training client. Learning docs: **`01_Build/studies/learns/`**.

Redmine 7.x patterns: `knowledge/redmine-7-patterns.yaml` (architecture first; never a port story).

## Features

- File tree, Monaco editor, integrated terminal
- Local LLM agent with tools: read/write files, code search, git, web search, commands
- Open Folder / Open Workspace (desktop app)
- Chat sessions, `@file` context, Quick / Step-by-step / Guided read answer modes
- Ubuntu desktop app (Electron)

## Requirements

- Python 3.11+
- Node.js 18+
- npm
- Ollama

## Quick install (new machine)

See **[docs/INSTALL.md](docs/INSTALL.md)** for full steps.

```bash
cd /home/ansif/works/_common/ansif/workspace/analysis
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-coder:0.5b
./scripts/install
./scripts/desktop-start
```

## Project layout

```text
├── backend/          FastAPI + agent tools
├── desktop/          Electron shell (Ubuntu)
├── docs/             Install and roadmap docs
├── frontend/         React + Monaco UI
├── knowledge/        Redmine 7.x patterns for the system prompt
├── scripts/          install, dev-start, smoke-test
└── workspace/        Fallback sandbox if the contract tree is missing
```

## Run locally (browser)

```bash
./scripts/install
ollama serve          # separate terminal
./scripts/dev-start
```

- UI: http://127.0.0.1:5176
- API: http://127.0.0.1:8006/health

## Ubuntu desktop app

```bash
./scripts/install-desktop
./scripts/desktop-start
```

Use **File → Open Folder** from the top menu.

## Docs

- [Architecture & code flow](docs/ARCHITECTURE.md)
- [Install on another system](docs/INSTALL.md)
- [Ubuntu desktop](docs/DESKTOP_UBUNTU.md)
- [Feature parity roadmap](docs/PARITY_ROADMAP.md)
- [Local run](docs/LOCAL_RUN.md)

## Smoke test

```bash
./scripts/smoke-test.sh
```

## Notes

- MVP — not for unrestricted public hosting yet.
- Production deploy flows need credentials and explicit user approval.
