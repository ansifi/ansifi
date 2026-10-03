# Ubuntu Desktop App

## What this adds

The coding agent can now run as a native Ubuntu desktop app using Electron.

The desktop shell:

- starts the FastAPI backend automatically
- serves the built React UI locally
- opens a single desktop window
- shuts the backend down when the app closes

## First-time setup

```bash
cd /home/ansif/works/projects/coding-agent
./scripts/install
./scripts/install-desktop
```

Make sure Ollama is installed and your coding model is available:

```bash
ollama run qwen2.5-coder:14b
```

## Launch options

### From terminal

```bash
cd /home/ansif/works/projects/coding-agent
./scripts/desktop-start
```

### From Ubuntu applications menu

After running `./scripts/install-desktop`, search for **Coding Agent** in the app launcher.

## Rebuild UI after frontend changes

```bash
cd /home/ansif/works/projects/coding-agent
npm run build --prefix frontend
./scripts/desktop-start
```

## Notes

- The desktop app still depends on local Python, Ollama, and the project virtualenv.
- This is a local desktop wrapper, not a fully packaged `.deb` installer yet.
- A future step can add `electron-builder` to ship a standalone installer.
