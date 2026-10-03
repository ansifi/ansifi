(function (w) {
  const KEY = "works.focus";
  const DESK_ID = {
    "/app/": "home",
    "/app/index.html": "home",
    "/app/analysis.html": "analysis",
    "/app/content.html": "content",
    "/app/network.html": "network",
    "/app/operate.html": "operate",
  };

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fetchJSON(url, opts) {
    return fetch(url, Object.assign({ credentials: "same-origin" }, opts || {})).then(function (r) {
      if (r.status === 401) {
        location.href = "/auth/";
        return null;
      }
      return r.json();
    });
  }

  function readStored() {
    try {
      return JSON.parse(sessionStorage.getItem(KEY) || "{}") || {};
    } catch (err) {
      return {};
    }
  }

  function getFocus() {
    const q = new URLSearchParams(location.search);
    const stored = readStored();
    const focus = {
      work: (q.get("work") || stored.work || "").trim(),
      note: (q.get("note") || stored.note || "").trim(),
      path: stored.path || "",
    };
    if (q.get("work") || q.get("note")) setFocus(focus);
    return focus;
  }

  function setFocus(partial) {
    const cur = readStored();
    const next = {
      work: partial.work !== undefined ? String(partial.work || "").trim() : cur.work || "",
      note: partial.note !== undefined ? String(partial.note || "").trim() : cur.note || "",
      path: partial.path !== undefined ? String(partial.path || "") : cur.path || "",
    };
    try {
      sessionStorage.setItem(KEY, JSON.stringify(next));
    } catch (err) {}
    return next;
  }

  function deskIdFromHref(href) {
    const path = String(href || "").split("?")[0] || "/app/";
    return DESK_ID[path] || "home";
  }

  function deskHref(page, extra) {
    extra = extra || {};
    const f = Object.assign({}, getFocus(), extra);
    const u = new URL(page || "/app/", location.origin);
    if (f.work) u.searchParams.set("work", f.work);
    else u.searchParams.delete("work");
    if (f.note) u.searchParams.set("note", f.note);
    else u.searchParams.delete("note");
    return u.pathname + u.search;
  }

  function inHubFrame() {
    try {
      return window.top && window.top !== window;
    } catch (err) {
      return false;
    }
  }

  function goDesk(page, extra) {
    extra = extra || {};
    if (Object.keys(extra).length) setFocus(extra);
    const href = deskHref(page, extra);
    if (inHubFrame()) {
      window.top.postMessage(
        { type: "workspace-open-app", id: deskIdFromHref(href), href: href },
        "*"
      );
      return;
    }
    location.href = href;
  }

  function matchesWork(item, work) {
    if (!work) return true;
    const needle = work.toLowerCase();
    const bits = [item.work, item.title, item.name, item.detail, item.snippet, item.path, item.source];
    return bits.some(function (b) {
      return b && String(b).toLowerCase().indexOf(needle) >= 0;
    });
  }

  document.addEventListener("click", function (ev) {
    const a = ev.target.closest("a[href^='/app']");
    if (!a || a.classList.contains("ext") || a.getAttribute("target") === "_blank") return;
    ev.preventDefault();
    const u = new URL(a.getAttribute("href") || "/app/", location.origin);
    const extra = {};
    if (a.getAttribute("data-clear")) {
      extra.work = "";
      extra.note = "";
    } else {
      if (u.searchParams.has("work")) extra.work = u.searchParams.get("work");
      if (u.searchParams.has("note")) extra.note = u.searchParams.get("note");
    }
    goDesk(u.pathname + u.hash, extra);
  });

  w.Works = {
    esc: esc,
    fetchJSON: fetchJSON,
    getFocus: getFocus,
    setFocus: setFocus,
    deskHref: deskHref,
    goDesk: goDesk,
    matchesWork: matchesWork,
    inHubFrame: inHubFrame,
  };
})(window);
