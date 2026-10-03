# Install Empever on another system

## Requirements

- **Ubuntu 22.04+** (desktop app) or any Linux with Python 3.11+
- **Python 3.11+**
- **Node.js 18+** and **npm**
- **Git**
- **Ollama** (local LLM runtime)

Optional for desktop mode:

- **Electron** dependencies (installed automatically by npm in `desktop/`)

## 1. Clone the private repo

```bash
git clone git@github.com:ansifi/coding-agent.git
cd coding-agent
```

If you use HTTPS with a personal access token:

```bash
git clone https://github.com/ansifi/coding-agent.git
cd coding-agent
```

## 2. Install Ollama and a coding model

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5-coder:0.5b
```

For better quality (needs more RAM):

```bash
ollama pull qwen2.5-coder:14b
```

## 3. Install app dependencies

```bash
./scripts/install
cp backend/.env.example backend/.env
```

## 4. Run in browser mode

Terminal 1 — keep Ollama running:

```bash
ollama serve
```

Terminal 2 — start the app:

```bash
./scripts/dev-start
```

Open:

- UI: http://127.0.0.1:5176
- API: http://127.0.0.1:8006/health

## 5. Run as Ubuntu desktop app

```bash
./scripts/install-desktop
./scripts/desktop-start
```

Then use **File → Open Folder** and select your project.

## 6. Smoke test

```bash
./scripts/smoke-test.sh
```

## Troubleshooting

| Problem | Fix |
|--------|-----|
| Agent errors / no reply | Run `ollama list` and pull a model |
| Port 8006 in use | `fuser -k 8006/tcp` then restart |
| Desktop UI blank | Run `npm run build --prefix frontend` |
| Tool name errors | Restart app after pulling latest code |

## Update on another machine

```bash
cd coding-agent
git pull
./scripts/install
npm run build --prefix frontend
./scripts/desktop-start
```
