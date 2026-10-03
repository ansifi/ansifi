(function () {
  const W = window.Works || {};
  const esc = W.esc || function (s) { return String(s || ""); };
  const fetchJSON = W.fetchJSON;
  const history = [];

  function chat() {
    const log = document.getElementById("chat-log");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");
    if (!form) return;
    function addLine(who, text) {
      const div = document.createElement("div");
      div.className = "bubble " + who;
      div.textContent = text;
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
    }
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      const prompt = (input.value || "").trim();
      if (!prompt) return;
      input.value = "";
      addLine("me", prompt);
      history.push({ role: "user", text: prompt });
      fetchJSON("/api/desk-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt, desk: "operate", history: history.slice(-8) }),
      }).then(function (out) {
        const text = (out && out.text) || "No reply.";
        addLine("bot", text);
        history.push({ role: "bot", text: text });
      });
    });
  }

  function inr(v) {
    const n = Number(v || 0);
    if (Number.isNaN(n)) return String(v || "0");
    return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }

  function paintBooks(data) {
    if (!data) return;
    window._books = data;
    const how = document.getElementById("books-how");
    if (how) {
      how.textContent =
        (data.how || "") +
        " " +
        (data.fy_label || ("Year " + data.year)) +
        " · " +
        (data.from || "") +
        " to " +
        (data.to || "") +
        " · " +
        (data.entry_count || 0) +
        " rows.";
    }
    const chips = document.getElementById("year-chips");
    chips.innerHTML = (data.years || [])
      .map(function (y) {
        const on = String(y) === String(data.year) ? " is-on" : "";
        return "<button type=\"button\" class=\"chip-btn" + on + "\" data-year=\"" + y + "\">FY " + (y - 1) + "–" + String(y).slice(2) + "</button>";
      })
      .join("");
    chips.querySelectorAll("[data-year]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        fetchJSON("/api/works/books?year=" + btn.getAttribute("data-year")).then(paintBooks);
      });
    });
    const kpis = document.getElementById("kpis");
    kpis.innerHTML =
      "<div class=\"kpi\"><span>Credits</span><strong>" + esc(inr(data.credits)) + "</strong></div>" +
      "<div class=\"kpi\"><span>Debits</span><strong>" + esc(inr(data.debits)) + "</strong></div>" +
      "<div class=\"kpi\"><span>Interest</span><strong>" + esc(inr(data.interest)) + "</strong></div>" +
      "<div class=\"kpi\"><span>Salary</span><strong>" + esc(inr(data.salary)) + "</strong></div>" +
      "<div class=\"kpi\"><span>Tax / TDS</span><strong>" + esc(inr(data.tax)) + "</strong></div>";
    const sel = document.getElementById("acct-filter");
    const keep = sel.value;
    sel.innerHTML =
      "<option value=\"\">All accounts</option>" +
      (data.accounts || [])
        .map(function (a) {
          return "<option value=\"" + esc(a.id) + "\">" + esc(a.label) + "</option>";
        })
        .join("");
    if (keep) sel.value = keep;
    const cats = document.getElementById("cat-board");
    cats.innerHTML = (data.categories || [])
      .map(function (c) {
        return "<div class=\"item\"><span class=\"chip\">" + esc(c.id) + "</span><div><strong>" + esc(c.label) + "</strong><p>₹ " + esc(inr(c.amount)) + "</p></div></div>";
      })
      .join("");
    paintLedger(data, sel.value);
  }

  function paintLedger(data, accountId) {
    const labels = data.category_labels || [];
    const opts = labels
      .map(function (c) {
        return "<option value=\"" + esc(c.id) + "\">" + esc(c.label) + "</option>";
      })
      .join("");
    const rows = (data.entries || []).filter(function (r) {
      return !accountId || r.account_id === accountId;
    });
    const table = document.getElementById("ledger");
    table.innerHTML =
      "<thead><tr><th>Date</th><th>Meaning</th><th>Credit</th><th>Debit</th><th>Category</th></tr></thead><tbody>" +
      rows
        .map(function (r) {
          return (
            "<tr data-hash=\"" +
            esc(r.dedupe_hash) +
            "\"><td>" +
            esc(r.txn_date) +
            "</td><td>" +
            esc(r.friendly_memo || r.particulars) +
            "</td><td>" +
            esc(inr(r.deposit)) +
            "</td><td>" +
            esc(inr(r.withdrawal)) +
            "</td><td><select data-cat>" +
            opts +
            "</select></td></tr>"
          );
        })
        .join("") +
      "</tbody>";
    table.querySelectorAll("select[data-cat]").forEach(function (sel) {
      const want = (data.entries || []).find(function (e) {
        return e.dedupe_hash === sel.closest("tr").getAttribute("data-hash");
      });
      if (want) sel.value = want.category || "unset";
      sel.addEventListener("change", function () {
        const tr = sel.closest("tr");
        fetchJSON("/api/works/books/row", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ hash: tr.getAttribute("data-hash"), category: sel.value }),
        });
      });
    });
  }

  function books() {
    fetchJSON("/api/works/books").then(paintBooks);
    const form = document.getElementById("upload-form");
    const status = document.getElementById("upload-status");
    const acct = document.getElementById("acct-filter");
    acct.addEventListener("change", function () {
      if (window._books) paintLedger(window._books, acct.value);
    });
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      const file = document.getElementById("stmt-file").files[0];
      if (!file) {
        status.textContent = "Choose a PDF or Excel statement first.";
        return;
      }
      const body = new FormData();
      body.append("statement_pdf", file, file.name);
      status.textContent = "Reading…";
      fetch("/api/works/books/upload", { method: "POST", credentials: "same-origin", body: body })
        .then(function (r) { return r.json(); })
        .then(function (out) {
          if (out && out.ok) {
            status.textContent = "Stored " + out.new_rows + " new rows from " + (out.account || file.name);
            fetchJSON("/api/works/books").then(paintBooks);
          } else {
            status.textContent = (out && out.error) || "Could not parse.";
          }
        })
        .catch(function () {
          status.textContent = "Upload failed.";
        });
    });
  }

  function compliance() {
    const root = document.getElementById("compliance");
    fetchJSON("/api/works/compliance").then(function (data) {
      if (!data) return;
      root.innerHTML = (data.modules || [])
        .map(function (m) {
          return (
            "<article class=\"mod\"><h3>" +
            esc(m.title) +
            "</h3><p class=\"blurb\">" +
            esc(m.status) +
            " · " +
            esc(m.mode) +
            "</p><p>" +
            esc(m.what) +
            "</p></article>"
          );
        })
        .join("");
    });
  }

  chat();
  books();
  compliance();
})();
