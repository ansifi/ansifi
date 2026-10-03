const { app, BrowserWindow, dialog, ipcMain, Menu, shell } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const FRONTEND_DIST = path.join(ROOT, "frontend", "dist");
const VENV_PYTHON = path.join(ROOT, ".venv", "bin", "python");
const BACKEND_PORT = Number(process.env.CODING_AGENT_BACKEND_PORT || 8006);
const UI_PORT = Number(process.env.CODING_AGENT_UI_PORT || 5176);
const API_BASE = `http://127.0.0.1:${BACKEND_PORT}`;
const UI_BASE = `http://127.0.0.1:${UI_PORT}`;

let mainWindow = null;
let backendProcess = null;
let staticServer = null;

const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

function resolvePython() {
  if (fs.existsSync(VENV_PYTHON)) {
    return VENV_PYTHON;
  }
  return "python3";
}

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const request = http.get(url, (response) => {
      let body = "";
      response.on("data", (chunk) => {
        body += chunk;
      });
      response.on("end", () => {
        if (response.statusCode && response.statusCode >= 200 && response.statusCode < 300) {
          resolve(body);
          return;
        }
        reject(new Error(`Request failed: ${response.statusCode}`));
      });
    });
    request.on("error", reject);
    request.setTimeout(1500, () => {
      request.destroy(new Error("Request timed out"));
    });
  });
}

function httpJsonRequest(targetUrl, method, payload) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify(payload);
    const parsed = new URL(targetUrl);
    const request = http.request(
      {
        hostname: parsed.hostname,
        port: parsed.port,
        path: parsed.pathname,
        method,
        headers: {
          "Content-Type": "application/json",
          "Content-Length": Buffer.byteLength(body),
        },
      },
      (response) => {
        let raw = "";
        response.on("data", (chunk) => {
          raw += chunk;
        });
        response.on("end", () => {
          if (response.statusCode && response.statusCode >= 200 && response.statusCode < 300) {
            try {
              resolve(JSON.parse(raw));
            } catch (error) {
              reject(error);
            }
            return;
          }
          reject(new Error(raw || `Request failed: ${response.statusCode}`));
        });
      }
    );
    request.on("error", reject);
    request.write(body);
    request.end();
  });
}

async function waitForBackend(maxAttempts = 60) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      await httpGet(`${API_BASE}/health`);
      return;
    } catch (error) {
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  }
  throw new Error("Backend did not become ready in time.");
}

function startBackend() {
  const python = resolvePython();
  backendProcess = spawn(
    python,
    ["-m", "uvicorn", "backend.app:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)],
    {
      cwd: ROOT,
      env: {
        ...process.env,
        CODING_AGENT_API_BASE: API_BASE,
        CORS_ALLOW_ORIGINS: `${UI_BASE},http://127.0.0.1:5176,http://localhost:5176`,
      },
      stdio: ["ignore", "pipe", "pipe"],
    }
  );

  backendProcess.stdout.on("data", (chunk) => {
    process.stdout.write(`[backend] ${chunk}`);
  });
  backendProcess.stderr.on("data", (chunk) => {
    process.stderr.write(`[backend] ${chunk}`);
  });
}

async function ensureBackend() {
  try {
    await waitForBackend(3);
    return;
  } catch (error) {
    startBackend();
    await waitForBackend();
  }
}

function startStaticServer() {
  if (!fs.existsSync(path.join(FRONTEND_DIST, "index.html"))) {
    throw new Error("Frontend build not found. Run ./scripts/desktop-start once to build it.");
  }

  return new Promise((resolve, reject) => {
    staticServer = http.createServer((request, response) => {
      const requestPath = decodeURIComponent((request.url || "/").split("?")[0]);
      let filePath = path.join(FRONTEND_DIST, requestPath === "/" ? "index.html" : requestPath);

      if (!filePath.startsWith(FRONTEND_DIST)) {
        response.writeHead(403);
        response.end("Forbidden");
        return;
      }

      if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        filePath = path.join(FRONTEND_DIST, "index.html");
      }

      const extension = path.extname(filePath);
      const contentType = MIME_TYPES[extension] || "application/octet-stream";
      response.writeHead(200, { "Content-Type": contentType });
      fs.createReadStream(filePath).pipe(response);
    });

    staticServer.on("error", reject);
    staticServer.listen(UI_PORT, "127.0.0.1", () => resolve());
  });
}

function notifyWorkspaceChanged(payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("workspace:changed", payload);
  }
}

async function pickFolderAndOpen() {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ["openDirectory"],
    title: "Open Folder",
  });
  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true };
  }

  const payload = await httpJsonRequest(`${API_BASE}/api/workspace/open-folder`, "POST", {
    path: result.filePaths[0],
  });
  notifyWorkspaceChanged(payload);
  return payload;
}

async function pickWorkspaceAndOpen() {
  const result = await dialog.showOpenDialog(mainWindow, {
    filters: [{ name: "Workspace Files", extensions: ["code-workspace", "json"] }],
    properties: ["openFile"],
    title: "Open Workspace",
  });
  if (result.canceled || result.filePaths.length === 0) {
    return { canceled: true };
  }

  const payload = await httpJsonRequest(`${API_BASE}/api/workspace/open-workspace`, "POST", {
    path: result.filePaths[0],
  });
  notifyWorkspaceChanged(payload);
  return payload;
}

function buildApplicationMenu() {
  const template = [
    {
      label: "File",
      submenu: [
        {
          label: "Open Folder...",
          accelerator: "CmdOrCtrl+O",
          click: () => {
            pickFolderAndOpen().catch((error) => {
              dialog.showErrorBox("Open Folder", error.message);
            });
          },
        },
        {
          label: "Open Workspace...",
          accelerator: "CmdOrCtrl+Shift+O",
          click: () => {
            pickWorkspaceAndOpen().catch((error) => {
              dialog.showErrorBox("Open Workspace", error.message);
            });
          },
        },
        { type: "separator" },
        {
          label: "Refresh Project",
          accelerator: "CmdOrCtrl+R",
          click: () => {
            notifyWorkspaceChanged({ refreshed: true });
          },
        },
        { type: "separator" },
        { role: "quit" },
      ],
    },
    {
      label: "Edit",
      submenu: [
        { role: "undo" },
        { role: "redo" },
        { type: "separator" },
        { role: "cut" },
        { role: "copy" },
        { role: "paste" },
        { role: "selectAll" },
      ],
    },
    {
      label: "View",
      submenu: [{ role: "reload" }, { role: "toggledevtools" }, { type: "separator" }, { role: "togglefullscreen" }],
    },
    {
      label: "Help",
      submenu: [
        {
          label: "Docs",
          click: () => {
            shell.openPath(path.join(ROOT, "docs"));
          },
        },
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: "Coding Agent",
    backgroundColor: "#0f172a",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.loadURL(UI_BASE);
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function stopChildProcesses() {
  if (staticServer) {
    staticServer.close();
    staticServer = null;
  }

  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill("SIGTERM");
    backendProcess = null;
  }
}

async function bootDesktopApp() {
  try {
    buildApplicationMenu();
    await ensureBackend();
    await startStaticServer();
    createWindow();
  } catch (error) {
    dialog.showErrorBox(
      "Coding Agent",
      `${error.message}\n\nMake sure dependencies are installed:\n./scripts/install\n./scripts/desktop-start`
    );
    app.quit();
  }
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.focus();
    }
  });

  app.whenReady().then(bootDesktopApp);

  ipcMain.handle("workspace:open-folder", pickFolderAndOpen);
  ipcMain.handle("workspace:open-workspace", pickWorkspaceAndOpen);

  app.on("window-all-closed", () => {
    stopChildProcesses();
    if (process.platform !== "darwin") {
      app.quit();
    }
  });

  app.on("before-quit", () => {
    stopChildProcesses();
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      bootDesktopApp();
    }
  });
}
