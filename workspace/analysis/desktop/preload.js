const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("codingAgentDesktop", {
  apiBase: process.env.CODING_AGENT_API_BASE || "http://127.0.0.1:8006",
  isDesktop: true,
  openFolder: () => ipcRenderer.invoke("workspace:open-folder"),
  openWorkspace: () => ipcRenderer.invoke("workspace:open-workspace"),
  onWorkspaceChanged: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on("workspace:changed", listener);
    return () => ipcRenderer.removeListener("workspace:changed", listener);
  },
});
