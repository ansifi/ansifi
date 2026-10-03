/*
 * Hub home: Analysis, Content, Network reports. Automate reads all three.
 * Operate is not a Workspace app — Sevendyne / Empever / Axxxx teams run it.
 */
const KNOWN_TENANTS = {
  csr: true,
  geoxyz: true,
  quantyf: true,
  ovt: true,
  crossdock: true,
  dummy_client: true,
};

function tenantFromPath() {
  const parts = (location.pathname || "/").split("/").filter(Boolean);
  const first = (parts[0] || "").toLowerCase();
  return KNOWN_TENANTS[first] ? first : "";
}

function tenantHeaders() {
  const t = tenantFromPath();
  return t ? { "X-Empever-Tenant": t } : {};
}

function homePath() {
  const t = tenantFromPath();
  return t ? "/" + t + "/" : "/";
}

function authPath() {
  const t = tenantFromPath();
  return (t ? "/" + t : "") + "/auth/";
}

const WORKSPACE_BRAND = "Ansif Workspace";

{
  const brandEl = document.querySelector(".brand strong");
  if (brandEl) brandEl.textContent = WORKSPACE_BRAND;
  const markEl = document.querySelector(".brand .mark");
  if (markEl) markEl.textContent = "A";
  document.title = WORKSPACE_BRAND;
}

function appName() {
  const el = document.querySelector(".brand strong");
  return (el && el.textContent.trim()) || WORKSPACE_BRAND;
}

function applyBrand(data) {
  if (!data) return;
  const title = WORKSPACE_BRAND;
  const mark = "A";
  const strong = document.querySelector(".brand strong");
  const markEl = document.querySelector(".brand .mark");
  if (strong) strong.textContent = title;
  if (markEl) markEl.textContent = mark;
  if (!openAppId) document.title = title + " — " + (data.client || clientName);
}

const HASH_TO_ID = {
  analysis: "analysis",
  coding: "analysis",
  content: "content",
  network: "network",
  leads: "content",
  automate: "automate",
  "analysis-dash": "analysis-dash",
  "content-dash": "content-dash",
  "network-dash": "network-dash",
  operate: "operate",
};

const home = document.getElementById("home");
const stage = document.getElementById("stage");
const frame = document.getElementById("frame");
const back = document.getElementById("back");
const current = document.getElementById("current");
const grid = document.getElementById("grid");
const reportGrid = document.getElementById("report-grid");
const deskReportsEl = document.getElementById("desk-reports");
const automateEl = document.getElementById("automate");
const refreshBtn = document.getElementById("refresh");
const ledeEl = document.getElementById("lede");
const sessionNameEl = document.getElementById("session-name");
const sessionSwitch = document.getElementById("session-switch");
const sessionLogout = document.getElementById("session-logout");
const sessionDialog = document.getElementById("session-dialog");
const sessionForm = document.getElementById("session-form");
const sessionSave = document.getElementById("session-save");
const sessionInput = document.getElementById("session-input");
const sessionLede = document.getElementById("session-lede");
const accountsEl = document.getElementById("accounts");
const accountsBody = document.getElementById("accounts-body");
const digestEl = document.getElementById("digest");
const digestGroups = document.getElementById("digest-groups");
const digestLede = document.getElementById("digest-lede");
const digestApproveAll = document.getElementById("digest-approve-all");
const postsStatusBody = document.getElementById("posts-status-body");
const repliesStatusBody = document.getElementById("replies-status-body");
const operatesStatusBody = document.getElementById("operates-status-body");
const platformHealthEl = document.getElementById("platform-health");
const platformHealthBody = document.getElementById("platform-health-body");
const cockpitEl = document.getElementById("cockpit");
const kpiRow = document.getElementById("kpi-row");
const postBoard = document.getElementById("post-board");
const leadBoard = document.getElementById("lead-board");
const clientBoard = document.getElementById("client-board");
const clientBoardLede = document.getElementById("client-board-lede");

const POLL_MS = 15000;

let openAppId = "";
let lastStatus = {};
let clientName = "Ansif Workspace";
let clientId = "sevendyne";
let isAdmin = false;
let isSuperAdmin = false;
let desk = "client";
let portalUsername = "";
let availableClients = [
  { id: "sevendyne", name: "Ansif Workspace", crm_subdir: "default", payroll_db: "sevendyne" },
  { id: "dummy_client", name: "Dummy client", crm_subdir: "dummy_client", payroll_db: "dummy_client" },
];
let workspaceAccounts = [];
let digestState = null;
let homeDesk = null;

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function operatesOnlyDesk() {
  return true;
}

function appsFor(_name) {
  return [
    {
      id: "operate",
      title: "Operate",
      blurb: "Ansif personal profile, GEO.XYZ under Sevendyne payroll, books and tax.",
      url: "/app/operate.html",
      hash: "operate",
    },
    {
      id: "home",
      title: "Operate",
      url: "/app/operate.html",
      hash: "works",
    },
  ];
}

function paintClientOptions() {
  if (!sessionInput) return;
  sessionInput.innerHTML = "";
  availableClients.forEach(function (row) {
    const opt = document.createElement("option");
    opt.value = row.id;
    opt.textContent = row.name;
    if (row.id === clientId || row.name === clientName) opt.selected = true;
    sessionInput.appendChild(opt);
  });
}

function applySession(data) {
  if (!data) return;
  if (Array.isArray(data.clients) && data.clients.length) {
    availableClients = data.clients
      .filter(function (row) {
        return row && row.id && row.name;
      })
      .map(function (row) {
        return {
          id: String(row.id),
          name: String(row.name),
          crm_subdir: String(row.crm_subdir || row.id),
          payroll_db: String(row.payroll_db || row.id),
        };
      });
  }
  if (data.current) clientId = String(data.current);
  if (data.name) clientName = data.name;
  if (data.brand) {
    applyBrand(data);
  }
  if (Object.prototype.hasOwnProperty.call(data, "is_admin")) {
    isAdmin = !!data.is_admin;
  }
  if (Object.prototype.hasOwnProperty.call(data, "is_super_admin")) {
    isSuperAdmin = !!data.is_super_admin;
  }
  if (data.desk) desk = String(data.desk);
  else desk = isAdmin ? "admin" : "client";
  if (data.portal_username) portalUsername = String(data.portal_username);
  else if (data.username) portalUsername = String(data.username);
  if (Array.isArray(data.accounts)) {
    workspaceAccounts = data.accounts.filter(function (row) {
      return row && row.username && row.password;
    });
  }
}

function accountRowHtml(row) {
  const user = escapeHtml(row.username);
  const canDelete = row.desk !== "admin";
  return (
    "<tr data-username=\"" +
    user +
    "\"><td class=\"col-name\">" +
    escapeHtml(row.name || row.username) +
    "</td><td class=\"col-user\">" +
    user +
    "</td><td class=\"col-pass\">" +
    escapeHtml(row.password) +
    "</td><td><a class=\"row-action\" data-act=\"login\" href=\"#login-" +
    user +
    "\">Login</a></td><td><button type=\"button\" class=\"row-action\" data-act=\"edit\">Edit</button></td><td><button type=\"button\" class=\"row-action\" data-act=\"update\" disabled>Update</button></td><td>" +
    (canDelete
      ? "<button type=\"button\" class=\"row-action row-delete\" data-act=\"delete\">Delete</button>"
      : "") +
    "</td></tr>"
  );
}

function paintAccounts() {
  if (!accountsEl || !accountsBody) return;
  if (operatesOnlyDesk() || isSuperAdmin || !isAdmin || !workspaceAccounts.length) {
    accountsEl.hidden = true;
    return;
  }
  accountsEl.hidden = false;
  accountsBody.innerHTML = workspaceAccounts.map(accountRowHtml).join("");
}

const DIGEST_GROUPS = [
  ["notes", "Notes"],
  ["posts", "Posts"],
  ["network", "Network"],
  ["operates", "Operates"],
];

function jobActionsHtml(job) {
  const id = String(job.id);
  const payroll = job.is_payroll;
  const pending = job.status === "pending" || job.status === "edited";
  if (!pending) {
    if (payroll && job.status === "approved") {
      return (
        '<button type="button" class="digest-btn" data-job="' +
        id +
        '" data-act="send-payroll">Send payroll</button>'
      );
    }
    return '<span class="digest-status">' + escapeHtml(job.status) + "</span>";
  }
  return (
    '<button type="button" class="digest-btn" data-job="' +
    id +
    '" data-act="approve">Approve</button>' +
    '<button type="button" class="digest-btn" data-job="' +
    id +
    '" data-act="edit">Edit</button>' +
    '<button type="button" class="digest-btn" data-job="' +
    id +
    '" data-act="skip">Skip</button>' +
    '<button type="button" class="digest-btn" data-job="' +
    id +
    '" data-act="snooze">Snooze</button>' +
    (payroll ? '<span class="digest-status">Payroll — not in Approve all</span>' : "")
  );
}

function paintDigest() {
  if (!digestEl) return;
  if (isSuperAdmin || operatesOnlyDesk()) {
    digestEl.hidden = true;
    return;
  }
  digestEl.hidden = false;
  if (!digestState || !digestState.digest) {
    if (digestGroups) digestGroups.innerHTML = "<p class=\"digest-empty\">Loading today’s drafts…</p>";
    return;
  }
  const jobs = digestState.jobs || {};
  if (digestGroups) {
    digestGroups.innerHTML = DIGEST_GROUPS.map(function (pair) {
      const key = pair[0];
      const label = pair[1];
      const rows = jobs[key] || [];
      const items = rows.length
        ? rows
            .map(function (job) {
              return (
                '<article class="digest-row" data-id="' +
                escapeHtml(String(job.id)) +
                '"><div><strong>' +
                escapeHtml(job.title || job.jobable_type) +
                '</strong><p>' +
                escapeHtml((job.body || "").slice(0, 280)) +
                '</p></div><div class="digest-row-actions">' +
                jobActionsHtml(job) +
                "</div></article>"
              );
            })
            .join("")
        : '<p class="digest-empty">Nothing pending.</p>';
      return "<section class=\"digest-group\"><h3>" + label + "</h3>" + items + "</section>";
    }).join("");
  }
  if (postsStatusBody) {
    const posts = digestState.posts || [];
    postsStatusBody.innerHTML = posts.length
      ? posts
          .map(function (post) {
            if (post.manual || !post.metrics) {
              return (
                "<p>" +
                escapeHtml(post.platform_name || post.title || "Post") +
                " — posted manually, no data</p>"
              );
            }
            const m = post.metrics;
            return (
              "<p>" +
              escapeHtml(post.platform_name || "Post") +
              " — " +
              Number(m.views || 0) +
              " views, " +
              Number(m.reactions || 0) +
              " reactions, " +
              Number(m.comments_count || 0) +
              " comments</p>"
            );
          })
          .join("")
      : "<p class=\"digest-empty\">No published posts yet.</p>";
  }
  if (repliesStatusBody) {
    const r = digestState.replies || {};
    repliesStatusBody.innerHTML =
      "<p>" +
      Number(r.needs_action || 0) +
      " need a reply — " +
      Number(r.known_contact || 0) +
      " known contacts, " +
      Number(r.lead_candidate || 0) +
      " lead candidates.</p>";
  }
  if (operatesStatusBody) {
    const o = digestState.operates || {};
    const inv = o.invoices || {};
    const pay = o.payslips || {};
    operatesStatusBody.innerHTML =
      "<p>Invoices this month — draft " +
      Number(inv.draft || 0) +
      ", pending " +
      Number(inv.pending || 0) +
      ", sent " +
      Number(inv.sent || 0) +
      ".</p><p>Payslips this month — created " +
      Number(pay.created || pay.draft || 0) +
      ", sent " +
      Number(pay.sent || 0) +
      ". Send payroll is a separate action.</p><p class=\"digest-open\">Open Operates App →</p>";
  }
}

function paintPlatformHealth() {
  if (!platformHealthEl) return;
  platformHealthEl.hidden = true;
}

function loadDigest() {
  if (isSuperAdmin) {
    return fetch("/api/ai/health", { credentials: "same-origin", headers: tenantHeaders() })
      .then(requireLogin)
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        digestState = data && data.ok ? data : null;
        paintPlatformHealth();
      })
      .catch(function () {
        digestState = null;
        paintPlatformHealth();
      });
  }
  if (operatesOnlyDesk()) {
    if (digestEl) digestEl.hidden = true;
    if (platformHealthEl) platformHealthEl.hidden = true;
    return Promise.resolve();
  }
  return fetch("/api/ai/digest", { credentials: "same-origin", headers: tenantHeaders() })
    .then(requireLogin)
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      digestState = data && data.ok ? data : null;
      paintDigest();
    })
    .catch(function () {
      digestState = null;
      paintDigest();
    });
}

function sparkSvg(series, kind) {
  const nums = (series || []).map(function (n) {
    return Number(n) || 0;
  });
  if (!nums.length) nums.push(0);
  const w = 120;
  const h = 36;
  const max = Math.max.apply(null, nums.concat([1]));
  const step = nums.length > 1 ? w / (nums.length - 1) : w;
  const pts = nums
    .map(function (n, i) {
      const x = i * step;
      const y = h - 4 - (n / max) * (h - 8);
      return x.toFixed(1) + "," + y.toFixed(1);
    })
    .join(" ");
  return (
    '<svg class="spark ' +
    escapeHtml(kind || "") +
    '" viewBox="0 0 ' +
    w +
    " " +
    h +
    '" width="' +
    w +
    '" height="' +
    h +
    '" aria-hidden="true"><polyline fill="none" stroke="currentColor" stroke-width="2" points="' +
    pts +
    '"/></svg>'
  );
}

function openDesk(kind, extra) {
  const apps = appsFor(clientName);
  const analysis = apps.find(function (a) {
    return a.id === "coding";
  });
  const leads = apps.find(function (a) {
    return a.id === "leads";
  });
  const operates = apps.find(function (a) {
    return a.id === "payroll";
  });
  if (kind === "post" && analysis) {
    const id = extra && extra.id ? "&post=" + encodeURIComponent(extra.id) : "";
    openApp(Object.assign({}, analysis, { url: analysis.url + id }));
    return;
  }
  if (kind === "lead" && leads) {
    openApp(leads);
    return;
  }
  if (kind === "client") {
    if (!operates) return;
    // Super admin: percent overview only. Tenant admin: this firm's Django Operates desk.
    if (isSuperAdmin) {
      const tenant = extra && extra.id ? extra.id : clientId;
      openApp(
        Object.assign({}, operates, {
          url: "/operates/overview.html?tenant=" + encodeURIComponent(tenant),
        })
      );
      return;
    }
    openApp(operates);
  }
}

function paintCockpit() {
  if (!cockpitEl) return;
  if (operatesOnlyDesk()) {
    cockpitEl.hidden = true;
    return;
  }
  cockpitEl.hidden = false;
  const data = homeDesk || {};
  const k = data.kpis || {};
  if (kpiRow) {
    const cells = [
      ["Posts created", Number(k.posts_created || 0), "post", ""],
      ["Sent", Number(k.posts_sent || 0), "post", ""],
      ["Viewed", Number(k.posts_viewed || 0), "post", ""],
      ["Responded", Number(k.posts_responded || 0), "lead", ""],
      ["Leads open", Number(k.leads_open || 0), "lead", ""],
      isSuperAdmin
        ? ["Admin clients", Number(k.admin_clients || 0), "client", ""]
        : ["Nested desks", Number(k.nested_clients || 0), "client", ""],
      [
        "Billed change",
        k.revenue_pct || "—",
        "client",
        k.revenue_trend || "steady",
        k.revenue_direction || "flat",
      ],
    ];
    kpiRow.innerHTML = cells
      .map(function (cell) {
        const trend = cell[3]
          ? '<em class="' + escapeHtml(cell[4] || "") + '">' + escapeHtml(cell[3]) + "</em>"
          : "";
        return (
          '<button type="button" class="kpi" data-open="' +
          cell[2] +
          '"><span>' +
          escapeHtml(cell[0]) +
          "</span><strong>" +
          escapeHtml(String(cell[1])) +
          "</strong>" +
          trend +
          "</button>"
        );
      })
      .join("");
  }
  if (postBoard) {
    const posts = data.posts || [];
    postBoard.innerHTML = posts.length
      ? posts
          .map(function (row) {
            return (
              '<button type="button" class="board-row" data-open="post" data-id="' +
              escapeHtml(String(row.id)) +
              '"><span class="board-title">' +
              escapeHtml(row.title || "Post") +
              '</span><span class="board-meta">' +
              escapeHtml(row.status || "draft") +
              " · " +
              Number(row.views || 0) +
              " views · " +
              Number(row.responses || 0) +
              " replies</span></button>"
            );
          })
          .join("")
      : '<p class="digest-empty">No stories yet. Refresh after the daily run, or open Analysis to write one.</p>';
  }
  if (leadBoard) {
    const leads = data.leads || [];
    leadBoard.innerHTML = leads.length
      ? leads
          .map(function (row) {
            return (
              '<button type="button" class="board-row" data-open="lead" data-id="' +
              escapeHtml(String(row.id)) +
              '"><span class="board-title">' +
              escapeHtml(row.title || "Lead") +
              '</span><span class="board-meta">' +
              escapeHtml(row.kind || "email") +
              (row.known ? " · known contact" : " · lead candidate") +
              "</span></button>"
            );
          })
          .join("")
      : '<p class="digest-empty">No open replies. New threads and comments land here.</p>';
  }
  if (clientBoardLede) {
    clientBoardLede.textContent = isSuperAdmin
      ? "SaaS admin firms and nested desks. Click a row for the Operates percent graph — rupee totals stay off this page."
      : "Open this firm’s Operates App to check invoices and payroll this month. Nested desks stay listed here.";
  }
  if (clientBoard) {
    const clients = data.clients || [];
    clientBoard.innerHTML = clients.length
      ? clients
          .map(function (row) {
            const g = row.growth || {};
            const rev = row.revenue || {};
            const nested = (row.nested || [])
              .map(function (n) {
                return escapeHtml(n.name);
              })
              .join(", ");
            return (
              '<button type="button" class="board-row" data-open="client" data-id="' +
              escapeHtml(row.id) +
              '"><span class="board-title">' +
              escapeHtml(row.name || row.id) +
              '</span><span class="board-meta">' +
              escapeHtml(rev.pct_label || "—") +
              " · " +
              escapeHtml(rev.label || "steady") +
              " · " +
              Number(row.invoice_count || 0) +
              " invoices · " +
              Number(row.nested_count || 0) +
              " nested" +
              (nested ? " — " + nested : "") +
              "</span>" +
              sparkSvg(rev.series || g.series, rev.direction || g.direction) +
              "</button>"
            );
          })
          .join("")
      : '<p class="digest-empty">No admin clients on this desk.</p>';
  }
}

function loadHomeDesk() {
  if (operatesOnlyDesk()) {
    if (cockpitEl) cockpitEl.hidden = true;
    return Promise.resolve();
  }
  return fetch("/api/ai/home", { credentials: "same-origin", headers: tenantHeaders() })
    .then(requireLogin)
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      homeDesk = data && data.ok ? data : null;
      paintCockpit();
    })
    .catch(function () {
      homeDesk = null;
      paintCockpit();
    });
}

function postJobAction(jobId, act, body) {
  return fetch("/api/ai/jobs/" + jobId + "/" + act, {
    method: "POST",
    credentials: "same-origin",
    headers: Object.assign({ "Content-Type": "application/json" }, tenantHeaders()),
    body: JSON.stringify(body || {}),
  })
    .then(requireLogin)
    .then(function (r) {
      return r.json();
    })
    .then(function () {
      return loadDigest().then(loadHomeDesk);
    });
}

function startAccountEdit(tr) {
  if (!tr || tr.dataset.editing === "1") return;
  const name = (tr.querySelector(".col-name") && tr.querySelector(".col-name").textContent) || "";
  const pass = (tr.querySelector(".col-pass") && tr.querySelector(".col-pass").textContent) || "";
  tr.dataset.editing = "1";
  tr.querySelector(".col-name").innerHTML = '<input data-field="name" value="' + escapeHtml(name) + '">';
  tr.querySelector(".col-pass").innerHTML = '<input data-field="password" value="' + escapeHtml(pass) + '">';
  const updateBtn = tr.querySelector('[data-act="update"]');
  if (updateBtn) updateBtn.disabled = false;
}

function loginWorkspaceAccount(username) {
  return fetch("/api/accounts/login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: username }),
  })
    .then(requireLogin)
    .then(function (r) {
      return r.json().then(function (data) {
        return { ok: r.ok, data: data };
      });
    })
    .then(function (res) {
      if (!res.ok || !res.data || !res.data.ok) throw new Error("login failed");
      const user = res.data.user || {};
      window.location.href = user.home || homePath();
    });
}

function updateWorkspaceAccount(tr) {
  const username = tr && tr.dataset.username;
  if (!username) return Promise.resolve();
  const nameEl = tr.querySelector('[data-field="name"]');
  const passEl = tr.querySelector('[data-field="password"]');
  const name = nameEl ? nameEl.value : "";
  const password = passEl ? passEl.value : "";
  return fetch("/api/accounts", {
    method: "PATCH",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: username, name: name, password: password }),
  })
    .then(requireLogin)
    .then(function (r) {
      if (!r.ok) throw new Error("update failed");
      return r.json();
    })
    .then(function (data) {
      const saved = data.account || {};
      workspaceAccounts = workspaceAccounts.map(function (row) {
        if (row.username !== username) return row;
        return {
          name: saved.name || name || row.name,
          username: saved.username || row.username,
          password: saved.password || password || row.password,
          tenant: saved.tenant || row.tenant,
          desk: row.desk,
        };
      });
      paintAccounts();
    });
}

function deleteWorkspaceAccount(username) {
  if (!username) return Promise.resolve();
  if (!window.confirm("Delete this workspace account?")) return Promise.resolve();
  return fetch("/api/accounts", {
    method: "DELETE",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: username }),
  })
    .then(requireLogin)
    .then(function (r) {
      if (!r.ok) throw new Error("delete failed");
      workspaceAccounts = workspaceAccounts.filter(function (row) {
        return row.username !== username;
      });
      paintAccounts();
    });
}

function sessionRoleLabel() {
  if (isSuperAdmin) return "super_admin";
  if (isAdmin) return "admin";
  return clientName;
}

function statusHtml(items) {
  if (!items || !items.length) return "";
  return (
    '<ul class="status-list">' +
    items
      .map(function (item) {
        return (
          '<li class="status-row kind-' +
          escapeHtml(item.kind || "") +
          '"><span class="status-mark">' +
          escapeHtml(item.status || "") +
          "</span><div><strong>" +
          escapeHtml(item.title || "") +
          "</strong>" +
          (item.detail
            ? '<p>' + escapeHtml(item.detail) + "</p>"
            : "") +
          "</div></li>"
        );
      })
      .join("") +
    "</ul>"
  );
}

function paintDeskReports(reports) {
  if (!reportGrid) return;
  const apps = appsFor(clientName);
  reportGrid.innerHTML = (reports || [])
    .map(function (r) {
      return (
        '<article class="report-card">' +
        '<button type="button" class="report-title" data-app="' +
        escapeHtml(r.id) +
        '"><div class="desk">' +
        escapeHtml(r.desk) +
        "</div><h3>" +
        escapeHtml(r.title) +
        "</h3></button><p>" +
        escapeHtml(r.summary) +
        "</p>" +
        statusHtml(r.items) +
        '<button type="button" class="open-dash" data-dash="' +
        escapeHtml(r.id) +
        '">' +
        escapeHtml(r.dashboard_label || "Open " + r.title) +
        "</button></article>"
      );
    })
    .join("");
  reportGrid.querySelectorAll(".report-title").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const app = apps.find(function (a) {
        return a.id === btn.getAttribute("data-app");
      });
      if (app) openApp(app);
    });
  });
  reportGrid.querySelectorAll(".open-dash").forEach(function (btn) {
    btn.addEventListener("click", function (ev) {
      ev.stopPropagation();
      const app = apps.find(function (a) {
        return a.id === btn.getAttribute("data-dash");
      });
      if (app) openApp(app);
    });
  });
  reportGrid.querySelectorAll(".status-row").forEach(function (row) {
    row.style.cursor = "pointer";
    row.addEventListener("click", function (ev) {
      ev.stopPropagation();
      const title = row.querySelector("strong");
      const card = row.closest(".report-card");
      const appBtn = card && card.querySelector(".report-title");
      const desk = appBtn ? appBtn.getAttribute("data-app") : "";
      const name = (title && title.textContent) || "";
      focusWork(name);
      const app = apps.find(function (a) {
        return a.id === desk;
      });
      if (app) openApp(app, withFocus(app.url, name));
      else askAbout(name, desk);
    });
  });
}

function loadDeskReports() {
  fetch("/api/desk-reports", { credentials: "same-origin", headers: tenantHeaders() })
    .then(function (r) {
      if (!r.ok) throw new Error("reports failed");
      return r.json();
    })
    .then(function (data) {
      paintDeskReports(data.reports || []);
    })
    .catch(function () {
      if (reportGrid) reportGrid.innerHTML = "<p class=\"digest-lede\">Could not read the work folders.</p>";
    });
}

const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatChips = document.getElementById("chat-chips");
const chatAsk = document.getElementById("chat-ask");
const chatJob = document.getElementById("chat-job");
let chatDesk = "operate";
let chatBusy = false;
let chatGen = 0;

function setChatDesk(desk) {
  chatDesk = desk || "";
  if (!chatChips) return;
  chatChips.querySelectorAll(".chip").forEach(function (btn) {
    btn.classList.toggle("is-on", (btn.getAttribute("data-desk") || "") === chatDesk);
  });
}

function setChatBusy(on) {
  chatBusy = !!on;
  if (chatForm) chatForm.classList.toggle("is-busy", chatBusy);
  if (chatAsk) chatAsk.disabled = chatBusy;
  if (chatJob) chatJob.disabled = chatBusy;
  if (chatInput) chatInput.disabled = chatBusy;
}

function appendChat(role, text, typing) {
  if (!chatLog) return null;
  const div = document.createElement("div");
  div.className = "chat-msg " + (role === "user" ? "user" : "bot") + (typing ? " is-typing" : "");
  const who = document.createElement("span");
  who.className = "who";
  who.textContent = role === "user" ? "You" : "Desk";
  const body = document.createElement("span");
  body.className = "txt";
  body.textContent = text || "";
  div.appendChild(who);
  div.appendChild(body);
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  return { wrap: div, body: body };
}

function typeChat(text) {
  const full = String(text || "No answer.");
  const node = appendChat("bot", "", true);
  if (!node) return Promise.resolve();
  return new Promise(function (resolve) {
    let i = 0;
    function tick() {
      const step = full[i] === " " ? 3 : 1;
      i = Math.min(full.length, i + step);
      node.body.textContent = full.slice(0, i);
      chatLog.scrollTop = chatLog.scrollHeight;
      if (i < full.length) {
        setTimeout(tick, 16);
      } else {
        node.wrap.classList.remove("is-typing");
        resolve();
      }
    }
    tick();
  });
}

function chatHistory() {
  if (!chatLog) return [];
  return Array.prototype.slice.call(chatLog.querySelectorAll(".chat-msg"), -8)
    .filter(function (el) {
      return !el.classList.contains("is-typing");
    })
    .map(function (el) {
      const body = el.querySelector(".txt");
      return {
        role: el.classList.contains("user") ? "user" : "bot",
        text: ((body && body.textContent) || "").trim(),
      };
    })
    .filter(function (row) {
      return !!row.text;
    });
}

function sendChat(prompt, asJob) {
  const text = String(prompt || "").trim();
  if (!text || chatBusy) return;
  const gen = ++chatGen;
  appendChat("user", text);
  if (chatInput) chatInput.value = "";
  setChatBusy(true);
  const waiting = appendChat("bot", "", true);
  const body = {
    prompt: asJob ? "run job: " + text : text,
    desk: chatDesk,
    history: chatHistory(),
  };
  fetch("/api/desk-chat", {
    method: "POST",
    credentials: "same-origin",
    headers: Object.assign({ "Content-Type": "application/json" }, tenantHeaders()),
    body: JSON.stringify(body),
  })
    .then(requireLogin)
    .then(function (r) {
      return r.text().then(function (raw) {
        var data = {};
        try {
          data = raw ? JSON.parse(raw) : {};
        } catch (e) {
          throw new Error("desk_chat_bad_json");
        }
        if (!r.ok && !data.text) {
          throw new Error("desk_chat_http");
        }
        return data;
      });
    })
    .then(function (data) {
      if (waiting && waiting.wrap && waiting.wrap.parentNode) {
        waiting.wrap.parentNode.removeChild(waiting.wrap);
      }
      return typeChat((data && data.text) || "No answer.").then(function () {
        if (data && data.open) {
          const app = appsFor(clientName).find(function (a) {
            return a.id === data.open;
          });
          if (app) openApp(app);
        }
      });
    })
    .catch(function (err) {
      if (waiting && waiting.wrap && waiting.wrap.parentNode) {
        waiting.wrap.parentNode.removeChild(waiting.wrap);
      }
      if (err && err.message === "login_required") return;
      return typeChat("Could not reach the desk chat. Refresh home and ask again.");
    })
    .then(function () {
      if (gen !== chatGen) return;
      setChatBusy(false);
      if (chatInput) chatInput.focus();
    });
}

function askAbout(title, desk) {
  if (desk) setChatDesk(desk);
  const q = "What is the status of " + String(title || "this work") + "?";
  sendChat(q, false);
}

if (chatChips) {
  chatChips.addEventListener("click", function (ev) {
    const btn = ev.target.closest("[data-desk]");
    if (!btn) return;
    setChatDesk(btn.getAttribute("data-desk") || "");
  });
}
if (chatForm) {
  chatForm.addEventListener("submit", function (ev) {
    ev.preventDefault();
    sendChat(chatInput && chatInput.value, false);
  });
}
if (chatInput) {
  chatInput.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter" && !ev.shiftKey) {
      ev.preventDefault();
      sendChat(chatInput.value, false);
    }
  });
}
if (chatJob) {
  chatJob.addEventListener("click", function () {
    const text = (chatInput && chatInput.value) || (chatDesk ? "run job on " + chatDesk : "run job");
    sendChat(text, true);
  });
}
if (chatLog && !chatLog.childElementCount) {
  const gen = ++chatGen;
  setChatBusy(true);
  typeChat("Hi. Ask what’s on disk, a status card, or what Sevendyne is.").then(function () {
    if (gen !== chatGen) return;
    setChatBusy(false);
    if (chatInput) chatInput.focus();
  });
}

function paintSession() {
  document.body.classList.toggle("client-desk", operatesOnlyDesk());
  // if (sessionNameEl) sessionNameEl.textContent = sessionRoleLabel();
  // if (sessionSwitch) sessionSwitch.hidden = !(isSuperAdmin && availableClients.length > 1);
  if (sessionLede) {
    sessionLede.textContent = isSuperAdmin
      ? "Switch SaaS workspaces. Operates does not open tenant invoices or payroll."
      : "Switch among this firm's client desks.";
  }
  if (sessionDialog && !sessionDialog.open) paintClientOptions();
  paintAccounts();
  if (digestEl) digestEl.hidden = true;
  if (platformHealthEl) platformHealthEl.hidden = true;
  if (cockpitEl) cockpitEl.hidden = true;
  if (deskReportsEl) deskReportsEl.hidden = false;
  if (ledeEl) {
    ledeEl.hidden = false;
    ledeEl.textContent =
      "Ansif personal Operate desk. GEO.XYZ under Sevendyne payroll. Books and tax working papers. Analysis, Content, and Network are hidden for now.";
  }
}

function focusWork(work) {
  try {
    sessionStorage.setItem(
      "works.focus",
      JSON.stringify({ work: work || "", note: "", path: "" })
    );
  } catch (err) {}
}

function withFocus(url, work) {
  const u = new URL(url, location.origin);
  let w = work || "";
  if (!w) {
    try {
      w = (JSON.parse(sessionStorage.getItem("works.focus") || "{}") || {}).work || "";
    } catch (err) {
      w = "";
    }
  }
  if (w) u.searchParams.set("work", w);
  return u.pathname + u.search;
}

function showHome() {
  document.body.classList.remove("app-open");
  home.hidden = false;
  stage.hidden = true;
  back.hidden = true;
  frame.removeAttribute("src");
  openAppId = "";
  current.textContent = "";
  document.title = appName() + " — " + clientName;
  history.replaceState(null, "", homePath());
}

function openApp(app, href) {
  document.body.classList.add("app-open");
  home.hidden = true;
  stage.hidden = false;
  back.hidden = false;
  openAppId = app.id;
  frame.src = href || withFocus(app.url);
  current.textContent = app.title;
  document.title = appName() + " — " + app.title;
  history.replaceState(null, "", homePath() + "#/" + app.hash);
}

function paintAutomate(_up) {
  if (automateEl) automateEl.hidden = true;
}

function codingStatus(status) {
  const ui = status.coding_ui;
  const api = status.coding_api;
  if (ui === true && api === true) {
    return { up: true, text: "Running" };
  }
  if (ui === true && api === false) {
    return { up: false, text: "UI up, API down" };
  }
  if (ui === false && api === true) {
    return { up: false, text: "API up, UI down" };
  }
  if (ui === false || api === false) {
    return { up: false, text: "Not running" };
  }
  return { up: null, text: "Checking…" };
}

function appStatus(app, status) {
  if (app.id === "coding") {
    return codingStatus(status);
  }
  const up = status[app.id] || (app.id === "payroll" ? status.payroll : null);
  if (up === true) {
    return { up: true, text: "Running" };
  }
  if (up === false) {
    return { up: false, text: "Not running" };
  }
  return { up: null, text: "Checking…" };
}

function render(status) {
  lastStatus = status || lastStatus || {};
  paintSession();
  if (grid) {
    grid.innerHTML = "";
    grid.hidden = true;
  }
  if (refreshBtn) refreshBtn.hidden = false;
  if (ledeEl) ledeEl.hidden = false;
  if (automateEl) automateEl.hidden = true;
  paintAutomate(true);
  loadDeskReports();
}

function applyHash() {
  const id = (location.hash || "").replace(/^#\/?/, "");
  if (!id) {
    showHome();
    return;
  }
  const resolved = HASH_TO_ID[id] || id;
  const app = appsFor(clientName).find(function (a) {
    return a.id === resolved;
  });
  if (app) {
    openApp(app);
    return;
  }
  showHome();
}

function requireLogin(res) {
  if (res.status === 401) {
    window.location.href = authPath();
    return Promise.reject(new Error("login_required"));
  }
  return res;
}

function loadSession() {
  return fetch("/api/session", { credentials: "same-origin", headers: tenantHeaders() })
    .then(requireLogin)
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      applySession(data);
      if (data && data.ok && !data.is_admin && data.slug) {
        var here = tenantFromPath();
        if (here !== data.slug) {
          window.location.replace("/" + data.slug + "/");
          return;
        }
      }
    })
    .catch(function (err) {
      if (err && err.message === "login_required") throw err;
      clientName = WORKSPACE_BRAND;
      clientId = "sevendyne";
      isAdmin = false;
    })
    .then(function () {
      paintSession();
    });
}

function saveSession(id) {
  return fetch("/api/session", {
    method: "PUT",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current: id }),
  })
    .then(requireLogin)
    .then(function (r) {
      if (!r.ok) throw new Error("save failed");
      return r.json();
    })
    .then(function (data) {
      applySession(data);
      const slug = String(data.slug || "").replace(/^\/+|\/+$/g, "");
      const dest = slug ? "/" + slug + "/" : "/";
      const here = (location.pathname || "/").replace(/\/+$/, "") || "/";
      const there = dest.replace(/\/+$/, "") || "/";
      if (here !== there) {
        window.location.href = dest;
        return;
      }
      render(lastStatus);
      if (openAppId) {
        const app = appsFor(clientName).find(function (row) {
          return row.id === openAppId;
        });
        if (app) openApp(app);
      }
    });
}

function loadStatus(opts) {
  const openOnLoad = opts && opts.openHash;
  const quiet = opts && opts.quiet;
  if (refreshBtn && !quiet) {
    refreshBtn.disabled = true;
    refreshBtn.textContent = "Checking…";
  }
  return fetch("/api/status", { credentials: "same-origin" })
    .then(requireLogin)
    .then(function (r) {
      return r.json();
    })
    .then(function (status) {
      render(status);
      if (openOnLoad) applyHash();
    })
    .catch(function (err) {
      if (err && err.message === "login_required") throw err;
      render({});
      if (openOnLoad) applyHash();
    })
    .then(function () {
      if (refreshBtn && !quiet) {
        refreshBtn.disabled = false;
        refreshBtn.textContent = "Refresh status";
      }
    });
}

function openSessionDialog() {
  paintClientOptions();
  if (!sessionDialog) return;
  if (typeof sessionDialog.showModal === "function") {
    sessionDialog.showModal();
  } else {
    sessionDialog.setAttribute("open", "");
  }
}

back.addEventListener("click", showHome);
window.addEventListener("hashchange", applyHash);

function loginAsClient() {
  const id = (sessionInput && sessionInput.value ? sessionInput.value : "").trim();
  if (!id) return;
  saveSession(id).then(function () {
    if (sessionDialog && typeof sessionDialog.close === "function") {
      sessionDialog.close();
    }
  });
}

// if (sessionSwitch) {
//   sessionSwitch.addEventListener("click", openSessionDialog);
// }

if (accountsBody) {
  accountsBody.addEventListener("click", function (ev) {
    const actEl = ev.target.closest("[data-act]");
    if (!actEl || !accountsBody.contains(actEl)) return;
    const tr = actEl.closest("tr");
    const username = tr && tr.dataset.username;
    const act = actEl.getAttribute("data-act");
    if (act === "login") {
      ev.preventDefault();
      loginWorkspaceAccount(username);
      return;
    }
    if (act === "edit") {
      startAccountEdit(tr);
      return;
    }
    if (act === "update") {
      updateWorkspaceAccount(tr);
      return;
    }
    if (act === "delete") {
      deleteWorkspaceAccount(username);
    }
  });
}

if (sessionLogout) {
  sessionLogout.addEventListener("click", function () {
    fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }).finally(function () {
      window.location.href = authPath();
    });
  });
}

if (sessionSave) {
  sessionSave.addEventListener("click", loginAsClient);
}

if (sessionForm) {
  sessionForm.addEventListener("submit", function (ev) {
    ev.preventDefault();
    loginAsClient();
  });
}

if (refreshBtn) {
  refreshBtn.addEventListener("click", function () {
    loadStatus();
  });
}

if (digestGroups) {
  digestGroups.addEventListener("click", function (ev) {
    const btn = ev.target.closest("[data-act][data-job]");
    if (!btn || !digestGroups.contains(btn)) return;
    const jobId = btn.getAttribute("data-job");
    const act = btn.getAttribute("data-act");
    if (act === "edit") {
      const row = btn.closest(".digest-row");
      const current = row && row.querySelector("p") ? row.querySelector("p").textContent : "";
      const next = window.prompt("Edit draft", current || "");
      if (next == null) return;
      postJobAction(jobId, "edit", { body: next });
      return;
    }
    postJobAction(jobId, act);
  });
}

if (digestApproveAll) {
  digestApproveAll.addEventListener("click", function () {
    const digestId = digestState && digestState.digest && digestState.digest.id;
    if (!digestId) return;
    fetch("/api/ai/digest/" + digestId + "/approve-all", {
      method: "POST",
      credentials: "same-origin",
      headers: Object.assign({ "Content-Type": "application/json" }, tenantHeaders()),
      body: "{}",
    })
      .then(requireLogin)
      .then(function () {
        return loadDigest().then(loadHomeDesk);
      });
  });
}

if (cockpitEl) {
  cockpitEl.addEventListener("click", function (ev) {
    const btn = ev.target.closest("[data-open]");
    if (!btn || !cockpitEl.contains(btn) || btn.disabled) return;
    openDesk(btn.getAttribute("data-open"), { id: btn.getAttribute("data-id") });
  });
}

const operatesStatus = document.getElementById("operates-status");
if (operatesStatus) {
  operatesStatus.addEventListener("click", function () {
    openDesk("client");
  });
}

const tabOperate = document.getElementById("tab-operate");
if (tabOperate) {
  tabOperate.addEventListener("click", function (ev) {
    ev.preventDefault();
    const planned = document.getElementById("planned-tab");
    if (planned) planned.removeAttribute("open");
    showHome();
  });
}

window.addEventListener("message", function (ev) {
  if (!ev.data) return;
  if (ev.data.type === "workspace-open-app") {
    const app = appsFor(clientName).find(function (a) {
      return a.id === ev.data.id;
    }) || { id: ev.data.id || "home", title: "Works", url: "/app/", hash: "works" };
    openApp(app, ev.data.href);
    return;
  }
  if (ev.data.type !== "workspace-open-dash") return;
  const app = appsFor(clientName).find(function (a) {
    return a.id === ev.data.id;
  });
  if (app) openApp(app);
});

loadSession()
  .then(function () {
    document.body.classList.remove("booting");
    return loadStatus({ openHash: true });
  })
  .catch(function (err) {
    if (err && err.message === "login_required") return;
    document.body.classList.remove("booting");
  });
setInterval(function () {
  if (document.body.classList.contains("app-open")) {
    return;
  }
  loadStatus({ quiet: true });
}, POLL_MS);
