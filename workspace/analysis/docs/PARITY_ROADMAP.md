# Cursor / Claude Parity Roadmap

Coding Agent is being built as a **local-first Cursor/Claude-style IDE** powered by your own Ollama models.

## Already available

- Open folder / workspace
- File tree sidebar
- Monaco editor
- Integrated terminal commands
- Local LLM agent with tools
- File read/write
- Code search
- Git status / diff
- Web search and URL fetch
- Chat sessions
- Project rules (`.coding-agent/rules.md`, `AGENTS.md`, `.cursorrules`, `CLAUDE.md`)
- Streaming agent activity
- `@file` context attachments
- Ubuntu desktop app

## Phase 2 — IDE depth

- [ ] Inline edit / apply diff UI
- [ ] Multi-file composer panel
- [ ] Tabbed editors
- [ ] Better terminal panel with history
- [ ] Checkpoint / undo for agent edits
- [ ] Semantic codebase indexing
- [ ] Faster symbol search

## Phase 3 — Agent power

- [ ] Long-running background tasks
- [ ] Deployment recipes (Android, React, Node, AWS, Docker)
- [ ] Credential vault + approval gates
- [ ] MCP tool integrations
- [ ] Browser automation for docs and dashboards
- [ ] Subagents for research / test / deploy

## Phase 4 — Product polish

- [ ] Model manager UI
- [ ] Plugin marketplace
- [ ] Team rules and shared prompts
- [ ] Customer install bundles
- [ ] `.deb` / AppImage packaging

## Important constraint

Cursor and Claude also rely on cloud models, hosted infrastructure, and managed safety systems. Coding Agent's advantage is **privacy and local control**, but full parity still depends on:

- stronger local models or hybrid model routing
- safe orchestration for Docker/cloud/deploy actions
- explicit user approval for risky operations

The current build is the **foundation layer**. The next step is Phase 2 IDE depth plus deployment recipes.
