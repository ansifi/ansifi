import { useEffect, useRef, useState } from "react";
import Editor from "@monaco-editor/react";

import AssistantMessage from "./AssistantMessage";
import PaneResizer from "./PaneResizer";
import { usePaneLayout } from "./paneLayout";

function defaultApiBase() {
  if (typeof window !== "undefined") {
    const path = window.location.pathname || "";
    if (path.startsWith("/apps/coding") || window.location.port === "4040") {
      return `${window.location.origin}/apps/coding-api`;
    }
  }
  return import.meta.env.VITE_API_BASE || "http://127.0.0.1:8006";
}

const API_BASE =
  (typeof window !== "undefined" && window.codingAgentDesktop?.apiBase) || defaultApiBase();
const DEFAULT_EDITOR_TEXT = "// Open a file on the left, then ask what it contains.";

function trackForFile(path) {
  if (String(path || "").startsWith("jcatrysse_ror/")) return "jan-redmine";
  return "from-coding-agent";
}

function App() {
  const [entries, setEntries] = useState([]);
  const [activeFile, setActiveFile] = useState("");
  const [code, setCode] = useState(DEFAULT_EDITOR_TEXT);
  const [prompt, setPrompt] = useState("");
  const [workspaceName, setWorkspaceName] = useState("01_Build");
  const [workspacePath, setWorkspacePath] = useState("");
  const [messages, setMessages] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState("");
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [status, setStatus] = useState("Checking backend...");
  const [loadingAgent, setLoadingAgent] = useState(false);
  const [activityLog, setActivityLog] = useState([]);
  const [notesTracks, setNotesTracks] = useState([]);
  const [notesTrack, setNotesTrack] = useState("from-coding-agent");
  const [notesSaveState, setNotesSaveState] = useState({});
  const messagesEndRef = useRef(null);
  const shellBodyRef = useRef(null);
  const { layout, gridStyle, beginDrag, reset } = usePaneLayout();

  function withMessageId(message) {
    return { ...message, id: message.id || `msg-${Date.now()}-${Math.random().toString(16).slice(2)}` };
  }

  async function fetchHealth() {
    try {
      const response = await fetch(`${API_BASE}/health`);
      const data = await response.json();
      setWorkspacePath(data.workspace || "");
      const available = data.models || [];
      setModels(available);
      setSelectedModel((current) => {
        const fast = available.find((name) => String(name).includes(":0.5b"));
        if (current && available.includes(current) && !String(current).includes(":1.5b")) return current;
        if (fast) return fast;
        return available[0] || data.model || current || "";
      });
      setStatus(data.workspace || "01_Build");
    } catch (error) {
      setStatus("Backend offline. Start the API and Ollama.");
    }
  }

  async function fetchTree() {
    const response = await fetch(`${API_BASE}/api/tree`);
    const data = await response.json();
    setEntries(data.entries || []);
    setWorkspaceName(data.workspace?.name || "01_Build");
    setWorkspacePath(data.workspace?.path || "");
  }

  async function fetchSessions() {
    const response = await fetch(`${API_BASE}/api/sessions`);
    const data = await response.json();
    setSessions(data.sessions || []);
  }

  async function createNewSession() {
    const response = await fetch(`${API_BASE}/api/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "New chat" }),
    });
    const data = await response.json();
    const session = data.session;
    setSessionId(session.id);
    setMessages([]);
    setActivityLog([]);
    await fetchSessions();
  }

  async function loadSession(id) {
    const response = await fetch(`${API_BASE}/api/sessions/${id}`);
    const data = await response.json();
    setSessionId(id);
    setMessages((data.session?.messages || []).map((message) => withMessageId(message)));
    setActivityLog([]);
  }

  async function fetchNotesTracks() {
    try {
      const response = await fetch(`${API_BASE}/api/notes/tracks`);
      const data = await response.json();
      const tracks = data.tracks || [];
      setNotesTracks(tracks);
      setNotesTrack((current) =>
        tracks.some((track) => track.id === current) ? current : tracks[0]?.id || "from-coding-agent"
      );
    } catch (error) {
      setNotesTracks([{ id: "jan-redmine" }, { id: "past-projects" }, { id: "from-coding-agent" }]);
    }
  }

  async function saveAnswerToNotes(message) {
    if (!message?.text) return;
    const messageKey = message.id || message.text.slice(0, 24);
    setNotesSaveState((current) => ({ ...current, [messageKey]: "saving" }));
    const heading = activeFile
      ? `What ${activeFile} contains`
      : message.text.split("\n").find((line) => line.trim()) || "coding-agent answer";
    const body = activeFile ? `# ${heading}\n\nFile: \`${activeFile}\`\n\n${message.text}` : message.text;
    try {
      const response = await fetch(`${API_BASE}/api/notes/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          track: notesTrack,
          content: body,
          title: heading,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Save failed");
      }
      setNotesSaveState((current) => ({ ...current, [messageKey]: "saved" }));
      setStatus(data.message || "Saved to Content Notes.");
    } catch (error) {
      setNotesSaveState((current) => ({ ...current, [messageKey]: "error" }));
      setStatus(`Could not save to Notes: ${error.message}`);
    }
  }

  async function openFile(path) {
    setActiveFile(path);
    setNotesTrack(trackForFile(path));
    const response = await fetch(`${API_BASE}/api/file?path=${encodeURIComponent(path)}`);
    const data = await response.json();
    setCode(data.content || "");
  }

  async function streamAgent(userPrompt, activeSessionId, contextFiles) {
    const controller = new AbortController();
    const watchdog = window.setTimeout(() => controller.abort(), 100000);
    const response = await fetch(`${API_BASE}/api/agent/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      body: JSON.stringify({
        prompt: userPrompt,
        session_id: activeSessionId || null,
        context_files: contextFiles,
        model: selectedModel || null,
        response_mode: "quick",
      }),
    });

    if (!response.ok || !response.body) {
      window.clearTimeout(watchdog);
      throw new Error("Streaming request failed.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let assistantText = "";

    const applyEvent = (event) => {
      if (event.type === "status") {
        setActivityLog((current) => [...current, event.text]);
      }
      if (event.type === "assistant") {
        assistantText = event.text || "";
        setMessages((current) => {
          const next = [...current];
          const last = next[next.length - 1];
          if (last?.role === "assistant" && last.streaming) {
            last.text = assistantText;
            return [...next.slice(0, -1), last];
          }
          return [...next, withMessageId({ role: "assistant", text: assistantText, streaming: true })];
        });
      }
      if (event.type === "done") {
        setMessages((current) =>
          current.map((message) => (message.streaming ? { ...message, streaming: false } : message))
        );
      }
      if (event.type === "error") {
        throw new Error(event.text || "Agent failed");
      }
    };

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() || "";
        for (const part of parts) {
          const line = part.replace(/^:.*$/m, "").trim();
          if (!line.startsWith("data: ")) continue;
          applyEvent(JSON.parse(line.slice(6)));
        }
      }
      const leftover = buffer.replace(/^:.*$/m, "").trim();
      if (leftover.startsWith("data: ")) {
        applyEvent(JSON.parse(leftover.slice(6)));
      }
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error("Chat timed out waiting for the local model. Try a shorter question.");
      }
      throw error;
    } finally {
      window.clearTimeout(watchdog);
    }
  }

  async function submitPrompt() {
    if (!prompt.trim()) return;
    const userPrompt = prompt;
    setMessages((current) => [...current, withMessageId({ role: "user", text: userPrompt })]);
    setPrompt("");
    setLoadingAgent(true);
    setActivityLog([]);

    let resolvedSessionId = sessionId;

    try {
      if (!resolvedSessionId) {
        const response = await fetch(`${API_BASE}/api/sessions`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title: userPrompt.slice(0, 60) }),
        });
        const data = await response.json();
        resolvedSessionId = data.session.id;
        setSessionId(resolvedSessionId);
        await fetchSessions();
      }

      const contextFiles = activeFile ? [activeFile] : [];
      await streamAgent(userPrompt, resolvedSessionId, contextFiles);
      await fetchSessions();
      if (resolvedSessionId) {
        const sessionResponse = await fetch(`${API_BASE}/api/sessions/${resolvedSessionId}`);
        const sessionData = await sessionResponse.json();
        setMessages((sessionData.session?.messages || []).map((message) => withMessageId(message)));
      }
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: "assistant", text: `Chat failed: ${error.message}` },
      ]);
    } finally {
      setLoadingAgent(false);
    }
  }

  useEffect(() => {
    const slug = new URLSearchParams(window.location.search).get("platform_client") || "sevendyne";
    fetch(`${API_BASE}/api/workspace/open-client`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client: slug }),
    })
      .catch(() => {})
      .finally(() => {
        fetchHealth();
        fetchTree().catch(() => setEntries([]));
        fetchSessions().catch(() => setSessions([]));
        fetchNotesTracks().catch(() => {});
      });
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loadingAgent]);

  return (
    <div className="shell">
      <div className="shell-body" ref={shellBodyRef} style={gridStyle}>
        <aside className="sidebar panel">
          <div className="panel-header">
            <div>
              <strong>{workspaceName}</strong>
              <p>{workspacePath || status}</p>
              <p className="index-meta">Open a file → ask what it contains</p>
            </div>
            <div className="toolbar">
              <button onClick={() => fetchTree().catch(() => {})} type="button">
                Refresh
              </button>
            </div>
          </div>
          <div className="file-list">
            {entries.length === 0 ? <p className="empty-state">No files in 01_Build.</p> : null}
            {entries.map((entry) =>
              entry.type === "directory" ? (
                <div
                  className="tree-row directory"
                  key={entry.path}
                  style={{ paddingLeft: `${12 + entry.depth * 16}px` }}
                >
                  <span className="tree-icon">▾</span>
                  <span>{entry.name}</span>
                </div>
              ) : (
                <button
                  className={entry.path === activeFile ? "file-button active" : "file-button"}
                  key={entry.path}
                  onClick={() => openFile(entry.path)}
                  style={{ paddingLeft: `${28 + entry.depth * 16}px` }}
                  type="button"
                >
                  {entry.name}
                </button>
              )
            )}
          </div>
        </aside>

        {layout !== "narrow" ? (
          <PaneResizer
            axis="x"
            label="Resize file tree"
            onDoubleClick={() => reset("sidebar")}
            onPointerDown={(event) => beginDrag("sidebar", event, shellBodyRef.current)}
          />
        ) : null}

        <main className="editor-area panel learn-editor">
          <div className="panel-header">
            <div>
              <strong>{activeFile || "File"}</strong>
              <p>Read-only. Chat explains this file; Save to Notes writes 01_Build/studies/learns.</p>
            </div>
          </div>
          <div className="editor-pane">
            <Editor
              height="100%"
              theme="vs-dark"
              value={code}
              path={activeFile || "workspace.txt"}
              options={{
                readOnly: true,
                minimap: { enabled: false },
                fontSize: 13,
                automaticLayout: true,
                wordWrap: "on",
              }}
            />
          </div>
        </main>

        {layout === "wide" ? (
          <PaneResizer
            axis="x"
            label="Resize chat"
            onDoubleClick={() => reset("chat")}
            onPointerDown={(event) => beginDrag("chat", event, shellBodyRef.current)}
          />
        ) : (
          <PaneResizer
            axis="y"
            label="Resize chat"
            onDoubleClick={() => reset("chatHeight")}
            onPointerDown={(event) => beginDrag("chatHeight", event, shellBodyRef.current)}
          />
        )}

        <section className={`chat-area panel${layout === "wide" ? "" : " chat-area-span"}`}>
          <div className="panel-header chat-header">
            <div>
              <strong>Learn</strong>
              <p>Chat writes a note. Save it into Content Notes.</p>
            </div>
            <div className="chat-controls">
              <select onChange={(event) => setSelectedModel(event.target.value)} value={selectedModel}>
                {(models.length ? models : [selectedModel || "qwen2.5-coder:0.5b"]).map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
              <button onClick={createNewSession} type="button">
                New chat
              </button>
            </div>
          </div>

          <div className="session-list">
            {sessions.map((session) => (
              <button
                className={session.id === sessionId ? "session-button active" : "session-button"}
                key={session.id}
                onClick={() => loadSession(session.id)}
                type="button"
              >
                {session.title}
              </button>
            ))}
          </div>

          <div className="messages">
            {messages.length === 0 ? (
              <div className="message assistant">
                1. Open a file on the left.
                {"\n"}2. Ask what it contains (the open file is sent with the question).
                {"\n"}3. Click Save to Notes under the answer → 01_Build/studies/learns/.
              </div>
            ) : null}
            {messages.map((message, index) => (
              <AssistantMessage
                key={message.id || `${message.role}-${index}`}
                message={message}
                notesSaveState={notesSaveState[message.id || message.text?.slice(0, 24)]}
                notesTrack={notesTrack}
                notesTracks={notesTracks}
                onNotesTrackChange={setNotesTrack}
                onSaveToNotes={saveAnswerToNotes}
              />
            ))}
            {loadingAgent ? (
              <div className="message assistant">
                {activityLog[activityLog.length - 1] || "Writing a note…"}
              </div>
            ) : null}
            <div ref={messagesEndRef} />
          </div>

          <div className="composer">
            {activeFile ? <p className="open-file-hint">Explaining: {activeFile}</p> : null}
            <div className="composer-input-wrap">
              <textarea
                onChange={(event) => setPrompt(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    submitPrompt();
                  }
                }}
                placeholder={
                  activeFile
                    ? `What does ${activeFile} contain?`
                    : "Open a file first, then ask what it contains."
                }
                rows={4}
                value={prompt}
              />
            </div>
            <button disabled={loadingAgent || !prompt.trim()} onClick={submitPrompt} type="button">
              {loadingAgent ? "Writing…" : "Ask"}
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

export default App;
