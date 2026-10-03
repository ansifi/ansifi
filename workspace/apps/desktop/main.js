"use strict";

const { app, BrowserWindow, Menu, dialog, clipboard, shell } = require("electron");
const { spawn } = require("child_process");
const http = require("http");
const os = require("os");
const path = require("path");

const DEFAULT_WORKSPACE = "/home/ansif/works/04_Operate/Ansif/workspace";
const WORKSPACE = process.env.ANSIF_WORKSPACE || DEFAULT_WORKSPACE;
const RUN_SH = path.join(WORKSPACE, "run.sh");
const HUB = "http://127.0.0.1:4040/app/operate.html";
const PHONE_MDNS = "http://ansif-workspace.local:4040/";
const ICON = path.join(__dirname, "icon.png");
const LOADING = `data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html>
<html><head><meta charset="utf-8"><title>Ansif Workspace</title>
<style>
  html,body{margin:0;height:100%;background:#0c1118;color:#e8eef6;
    font:16px/1.4 Ubuntu,system-ui,sans-serif;display:flex;align-items:center;justify-content:center}
  p{opacity:.8}
</style></head>
<body><p>Starting servers…</p></body></html>`)}`;

app.setName("Ansif Workspace");
if (process.platform === "linux") {
  app.commandLine.appendSwitch("class", "AnsifWorkspace");
}

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {

function lanIp() {
  const skipName = /^(lo|docker|br-|veth|virbr|tun|vmnet|vboxnet|cni|flannel)/i;
  const scored = [];
  for (const [name, addrs] of Object.entries(os.networkInterfaces())) {
    if (skipName.test(name)) continue;
    for (const a of addrs || []) {
      if (!((a.family === "IPv4" || a.family === 4) && !a.internal)) continue;
      const ip = a.address;
      if (ip.startsWith("172.")) continue;
      let score = 0;
      if (/^w/i.test(name)) score += 10;
      if (ip.startsWith("192.168.29.")) score += 20;
      if (ip.startsWith("192.168.")) score += 5;
      scored.push({ ip, score });
    }
  }
  scored.sort((a, b) => b.score - a.score);
  return scored[0] ? scored[0].ip : "";
}

function lanUrl() {
  const ip = lanIp();
  return ip ? `http://${ip}:4040/` : PHONE_MDNS;
}

function phoneDetail() {
  return `${PHONE_MDNS}\n${lanUrl()}`;
}

function ping() {
  return new Promise((resolve) => {
    const req = http.get("http://127.0.0.1:4040/auth/", (res) => {
      res.resume();
      resolve(true);
    });
    req.on("error", () => resolve(false));
    req.setTimeout(1500, () => {
      req.destroy();
      resolve(false);
    });
  });
}

function runWorks(args) {
  return new Promise((resolve, reject) => {
    const child = spawn(RUN_SH, args, {
      cwd: WORKSPACE,
      stdio: ["ignore", "ignore", "pipe"],
    });
    let err = "";
    child.stderr.on("data", (chunk) => {
      err += chunk;
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve();
      else reject(new Error((err || `run.sh ${args.join(" ")}`).trim()));
    });
  });
}

async function waitHub(ms = 20000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    if (await ping()) return true;
    await new Promise((r) => setTimeout(r, 300));
  }
  return false;
}

let win = null;
let allowQuit = false;
let stopping = false;
const avahiKids = [];

function publishPhoneName() {
  stopPhoneName();
  const ip = lanIp();
  if (!ip) return;
  const spawnAvahi = (args) => {
    const child = spawn("avahi-publish", args, { stdio: "ignore" });
    child.on("error", () => {});
    avahiKids.push(child);
  };
  spawnAvahi(["-a", "-R", "ansif-workspace.local", ip]);
  spawnAvahi(["-s", "AnsifWorkspace", "_ansif-workspace._tcp", "4040"]);
}

function stopPhoneName() {
  while (avahiKids.length) {
    const child = avahiKids.pop();
    try {
      child.kill();
    } catch (_err) {
      /* already gone */
    }
  }
}

function copyPhoneUrl() {
  clipboard.writeText(PHONE_MDNS);
  if (!win) return;
  dialog.showMessageBox(win, {
    type: "info",
    title: "Phone URL",
    message: "Phone app uses this while the desktop app is running (same Wi-Fi).",
    detail: phoneDetail(),
  });
}

function createWindow() {
  win = new BrowserWindow({
    width: 1280,
    height: 860,
    title: "Ansif Workspace",
    icon: ICON,
    backgroundColor: "#0c1118",
    autoHideMenuBar: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.loadURL(LOADING);
  const local = (u) =>
    u.startsWith("http://127.0.0.1") ||
    u.startsWith("http://localhost") ||
    u.startsWith("http://ansif-workspace.local") ||
    u.startsWith("http://192.168.") ||
    u.startsWith("data:");
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (local(url)) return { action: "allow" };
    shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    if (!local(url)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });
  win.on("closed", () => {
    win = null;
  });
}

function focusWindow() {
  if (!win) return;
  if (win.isMinimized()) win.restore();
  win.show();
  win.focus();
}

function setMenu() {
  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      {
        label: "File",
        submenu: [
          { label: "Reload", accelerator: "CmdOrCtrl+R", click: () => win && win.reload() },
          {
            label: "Copy phone URL",
            click: () => copyPhoneUrl(),
          },
          {
            label: "Allow phone on Wi-Fi",
            click: async () => {
              try {
                await runWorks(["lan"]);
              } catch (err) {
                dialog.showErrorBox("Ansif Workspace", String(err.message || err));
                return;
              }
              await waitHub();
              publishPhoneName();
              copyPhoneUrl();
            },
          },
          { type: "separator" },
          { role: "quit" },
        ],
      },
      { role: "editMenu" },
      { role: "viewMenu" },
    ])
  );
}

app.on("second-instance", () => {
  focusWindow();
});

app.whenReady().then(async () => {
  if (!gotLock) return;
  setMenu();
  createWindow();
  try {
    await runWorks(["lan"]);
  } catch (err) {
    dialog.showErrorBox(
      "Ansif Workspace",
      `Could not start servers.\n${err.message || err}\nSee dashboard/.run/hub.log`
    );
    allowQuit = true;
    app.quit();
    return;
  }
  if (!(await waitHub())) {
    dialog.showErrorBox(
      "Ansif Workspace",
      "Hub did not start on http://127.0.0.1:4040/\nSee dashboard/.run/hub.log"
    );
    allowQuit = true;
    app.quit();
    return;
  }
  publishPhoneName();
  if (win) win.loadURL(HUB);
});

app.on("window-all-closed", () => {
  app.quit();
});

process.on("SIGINT", () => app.quit());
process.on("SIGTERM", () => app.quit());

app.on("before-quit", (event) => {
  if (allowQuit || stopping) return;
  event.preventDefault();
  stopping = true;
  stopPhoneName();
  runWorks(["stop"])
    .catch(() => {})
    .finally(() => {
      allowQuit = true;
      app.quit();
    });
});
}
