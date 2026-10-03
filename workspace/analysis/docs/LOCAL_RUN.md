# Local Run Guide

## 1. Start Ollama

Make sure Ollama is installed, then pull or start the coding model:

```bash
ollama run qwen2.5-coder:14b
```

## 2. Install backend dependencies

```bash
cd /home/ansif/works/projects/coding-agent
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
```

## 3. Install frontend dependencies

```bash
cd /home/ansif/works/projects/coding-agent/frontend
npm install
```

## 4. Start the app

```bash
cd /home/ansif/works/projects/coding-agent
./scripts/dev-start
```

## 5. Open the UI

- `http://127.0.0.1:5176`

## 6. Smoke test

Try this in the chat panel:

```text
Create a file named hello.py that prints "Hello from Coding Agent", then run it.
```
