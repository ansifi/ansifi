(function () {
  const appId = document.body.getAttribute("data-app") || "analysis";
  const titleEl = document.getElementById("title");
  const ledeEl = document.getElementById("lede");
  const summaryEl = document.getElementById("summary");
  const treeEl = document.getElementById("tree");
  const dashRow = document.getElementById("dash-row");

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function statusHtml(items) {
    if (!items || !items.length) return "<p class=\"muted\">Nothing listed.</p>";
    return (
      "<ul class=\"status-list\">" +
      items
        .map(function (item) {
          return (
            "<li class=\"status-row kind-" +
            esc(item.kind || "") +
            "\"><span class=\"status-mark\">" +
            esc(item.status || "") +
            "</span><div><strong>" +
            esc(item.title || "") +
            "</strong>" +
            (item.detail ? "<p>" + esc(item.detail) + "</p>" : "") +
            "</div></li>"
          );
        })
        .join("") +
      "</ul>"
    );
  }

  function openDash(dashId) {
    try {
      if (window.top && window.top !== window) {
        window.top.postMessage({ type: "workspace-open-dash", id: dashId }, "*");
        return;
      }
    } catch (err) {}
    const fallback = {
      "analysis-dash": "/app/analysis.html",
      "content-dash": "/app/content.html",
      "network-dash": "/app/network.html",
      operate: "/app/operate.html",
    };
    location.href = fallback[dashId] || "/";
  }

  function dashButton(r) {
    const dashId = r.id === "operate" ? "operate" : r.id + "-dash";
    return (
      "<button type=\"button\" class=\"open-dash\" data-dash=\"" +
      esc(dashId) +
      "\">" +
      esc(r.dashboard_label || "Open " + r.title + " dashboard") +
      "</button>"
    );
  }

  function bindDash(root) {
    (root || document).querySelectorAll(".open-dash").forEach(function (btn) {
      btn.addEventListener("click", function () {
        openDash(btn.getAttribute("data-dash"));
      });
    });
  }

  function paint(reports) {
    const list = Array.isArray(reports) ? reports : reports ? [reports] : [];
    if (appId !== "automate" && list.length === 1) {
      const r = list[0];
      if (titleEl) titleEl.textContent = r.title + " — " + r.desk;
      if (ledeEl) ledeEl.textContent = r.now;
      if (summaryEl) summaryEl.textContent = r.summary;
      if (dashRow) dashRow.innerHTML = dashButton(r);
      if (treeEl) treeEl.innerHTML = statusHtml(r.items);
      bindDash(document);
      return;
    }
    if (titleEl) titleEl.textContent = "Automate — work status";
    if (ledeEl) {
      ledeEl.textContent =
        "Status of Analysis, Content, Network, and Operate. Open each dashboard from here.";
    }
    if (summaryEl) {
      summaryEl.textContent = list
        .map(function (r) {
          return r.summary;
        })
        .join(" · ");
    }
    if (dashRow) {
      dashRow.innerHTML = list.map(dashButton).join(" ");
    }
    if (treeEl) {
      treeEl.innerHTML = list
        .map(function (r) {
          return (
            "<article class=\"block\"><h2>" +
            esc(r.title) +
            "</h2><p>" +
            esc(r.summary) +
            "</p>" +
            dashButton(r) +
            statusHtml(r.items) +
            "</article>"
          );
        })
        .join("");
    }
    bindDash(document);
  }

  fetch("/api/desk-reports" + (appId === "automate" ? "" : "?app=" + encodeURIComponent(appId)), {
    credentials: "same-origin",
  })
    .then(function (r) {
      return r.json();
    })
    .then(function (data) {
      paint(data.reports || data.report);
    })
    .catch(function (err) {
      if (summaryEl) summaryEl.textContent = String(err);
    });
})();
