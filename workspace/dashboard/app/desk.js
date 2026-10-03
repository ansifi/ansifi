(function () {
  const page = document.body.getAttribute("data-page") || "";
  const W = window.Works || {};
  const esc = W.esc || function (s) { return String(s || ""); };
  const fetchJSON = W.fetchJSON;
  const focus = W.getFocus ? W.getFocus() : { work: "", note: "", path: "" };

  let work = focus.work || "";
  const history = [];

  function jump(label, page, extra) {
    extra = extra || {};
    const href = W.deskHref ? W.deskHref(page, extra) : page;
    const clear = extra.work === "" ? " data-clear=\"1\"" : "";
    return (
      "<a class=\"jump\"" +
      clear +
      " href=\"" +
      esc(href) +
      "\">" +
      esc(label) +
      "</a>"
    );
  }

  function itemHtml(item) {
    return (
      "<div class=\"item" +
      (item.hit ? " is-on" : "") +
      "\"><span class=\"chip\">" +
      esc(item.status || item.kind || item.label || "") +
      "</span><div><strong>" +
      esc(item.title || item.name || "") +
      "</strong>" +
      (item.detail || item.snippet || item.path
        ? "<p>" + esc(item.detail || item.snippet || item.path) + "</p>"
        : "") +
      (item.action ? "<p class=\"action\">" + esc(item.action) + "</p>" : "") +
      linksHtml(item) +
      "</div></div>"
    );
  }

  function linksHtml(item) {
    const bits = [];
    if (item.url) {
      bits.push("<a class=\"ext\" href=\"" + esc(item.url) + "\" target=\"_blank\" rel=\"noopener\">Open</a>");
    }
    if (item.contact && String(item.contact).indexOf("@") >= 0) {
      bits.push(
        "<a class=\"ext\" href=\"mailto:" +
          esc(item.contact) +
          "\">Mail " +
          esc(item.contact) +
          "</a>"
      );
    }
    if (item.from && String(item.from).indexOf("@") >= 0) {
      const m = String(item.from).match(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i);
      if (m) {
        bits.push("<a class=\"ext\" href=\"mailto:" + esc(m[0]) + "\">Reply</a>");
      }
    }
    (item.jumps || []).forEach(function (j) {
      bits.push(jump(j.label, j.page, j.extra));
    });
    return bits.length ? "<p class=\"links\">" + bits.join(" ") + "</p>" : "";
  }

  function paintList(title, blurb, items) {
    if (!items || !items.length) return "";
    return (
      "<section><h2>" +
      esc(title) +
      "</h2>" +
      (blurb ? "<p class=\"blurb\">" + esc(blurb) + "</p>" : "") +
      items.map(itemHtml).join("") +
      "</section>"
    );
  }

  function focusBar(id, verb) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!work) {
      el.textContent = verb;
      return;
    }
    el.innerHTML =
      "On <strong>" +
      esc(work) +
      "</strong> · " +
      jump("Clear", location.pathname, { work: "", note: "" });
  }

  function analysis() {
    const chips = document.getElementById("work-chips");
    const log = document.getElementById("chat-log");
    const form = document.getElementById("chat-form");
    const input = document.getElementById("chat-input");
    const noteForm = document.getElementById("note-form");
    const noteTitle = document.getElementById("note-title");
    const noteBody = document.getElementById("note-body");
    const noteStatus = document.getElementById("note-status");

    function selectWork(title) {
      work = title || "";
      if (W.setFocus) W.setFocus({ work: work });
      chips.querySelectorAll(".chip-btn").forEach(function (b) {
        b.classList.toggle("is-on", b.getAttribute("data-work") === work);
      });
      if (noteTitle && work) noteTitle.value = work;
      focusBar("how", "Ask about a work, then save a note into 02_Content/Notes.");
    }

    fetchJSON("/api/works").then(function (data) {
      if (!data) return;
      const sec = (data.sections || []).find(function (s) { return s.id === "build"; });
      const rows = sec ? sec.active.concat(sec.planned || []) : [];
      chips.innerHTML = rows
        .map(function (item) {
          return "<button type=\"button\" class=\"chip-btn\" data-work=\"" + esc(item.title) + "\">" + esc(item.title) + "</button>";
        })
        .join("");
      chips.querySelectorAll(".chip-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          selectWork(btn.getAttribute("data-work") || "");
        });
      });
      if (work) selectWork(work);
    });

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
      const full = work ? work + ": " + prompt : prompt;
      input.value = "";
      addLine("me", full);
      history.push({ role: "user", text: full });
      fetchJSON("/api/desk-chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: full, desk: "analysis", history: history.slice(-8) }),
      }).then(function (out) {
        const text = (out && out.text) || "No reply.";
        addLine("bot", text);
        history.push({ role: "bot", text: text });
        if (noteBody && !noteBody.value) noteBody.value = text;
      });
    });

    noteForm.addEventListener("submit", function (ev) {
      ev.preventDefault();
      fetchJSON("/api/works/note", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: noteTitle.value,
          body: noteBody.value,
          work: work,
        }),
      }).then(function (out) {
        if (out && out.ok) {
          if (W.setFocus) W.setFocus({ work: work, note: out.title || noteTitle.value, path: out.path });
          noteStatus.innerHTML =
            "Saved " +
            esc(out.path) +
            " · " +
            jump("Open in Content", "/app/content.html", { work: work, note: out.title || "" });
          noteBody.value = "";
        } else {
          noteStatus.textContent = (out && out.error) || "Could not save.";
        }
      });
    });
  }

  function content() {
    focusBar("how", "Nothing auto-publishes. Open a draft, then paste by hand.");
    fetchJSON("/api/works/contents").then(function (data) {
      if (!data) return;
      const pub = document.getElementById("publish");
      const board = document.getElementById("board");
      if (!work && data.how) {
        const how = document.getElementById("how");
        if (how) how.textContent = data.how;
      }
      pub.innerHTML = (data.publish || [])
        .map(function (p) {
          return "<a class=\"ext\" href=\"" + esc(p.url) + "\" target=\"_blank\" rel=\"noopener\">Post on " + esc(p.name) + "</a>";
        })
        .join(" ");
      const notes = (data.notes || []).map(function (n) {
        const hit = W.matchesWork ? W.matchesWork(n, work) : true;
        return Object.assign({}, n, {
          hit: work && hit,
          jumps: [
            { label: "Chat in Analysis", page: "/app/analysis.html", extra: { work: n.work || work || n.title } },
            { label: "Find signals", page: "/app/network.html", extra: { work: n.work || work || n.title } },
          ],
        });
      });
      const drafts = (data.drafts || []).map(function (d) {
        return Object.assign({}, d, {
          hit: work && W.matchesWork && W.matchesWork(d, work),
          jumps: [
            { label: "Find signals", page: "/app/network.html", extra: { work: work || d.title } },
          ],
        });
      });
      const shownNotes = work ? notes.filter(function (n) { return n.hit; }) : notes;
      const shownDrafts = work ? drafts.filter(function (d) { return d.hit; }) : drafts;
      board.innerHTML =
        paintList("Notes from Analysis", "02_Content/Notes/ — same files the hub card reads.", shownNotes.length ? shownNotes : notes.slice(0, 8)) +
        paintList("Drafts ready to paste", "02_Content/Posts/drafts/", shownDrafts.length ? shownDrafts : drafts) +
        (data.live && data.live.length
          ? paintList("Live", "Published log", data.live)
          : "<section><h2>Live</h2><p class=\"empty\">None yet. Paste a draft on Dev.to / Medium / Hashnode by hand.</p></section>");
    });
  }

  function network() {
    const st = document.getElementById("mail-status");
    fetchJSON("/api/works/network").then(function (data) {
      if (!data) return;
      st.innerHTML = work
        ? "Signals for <strong>" + esc(work) + "</strong> · " + jump("Clear", "/app/network.html", { work: "", note: "" })
        : data.connected
          ? data.mailbox + " · " + data.unseen + " unread"
          : (data.error || "Inbox not connected");
      const board = document.getElementById("board");
      const emails = (data.emails || []).map(function (e) {
        const item = {
          title: e.title,
          status: e.label,
          detail: [e.from, e.when].filter(Boolean).join(" · "),
          from: e.from,
          jumps: [{ label: "Open Content", page: "/app/content.html", extra: { work: work } }],
        };
        item.hit = work && W.matchesWork && W.matchesWork(item, work);
        return item;
      });
      const signals = (data.signals || []).map(function (s) {
        const item = {
          title: s.title,
          status: s.source || "web",
          detail: s.snippet,
          url: s.url,
          contact: s.contact,
          jumps: [
            { label: "Related notes", page: "/app/content.html", extra: { work: work || s.title } },
            { label: "Chat this", page: "/app/analysis.html", extra: { work: work || s.title } },
          ],
        };
        item.hit = work && W.matchesWork && W.matchesWork(Object.assign({ snippet: s.snippet, source: s.source }, item), work);
        return item;
      });
      const sources = (data.sources || []).map(function (s) {
        return { title: s.label, status: "board", url: s.url };
      });
      const people = (data.people || []).map(function (p) {
        return {
          title: p.name,
          status: p.status || "lead",
          detail: [p.problem, p.bill_via].filter(Boolean).join(" · "),
          url: p.url,
          contact: p.contact,
        };
      });
      const web = work ? signals.filter(function (s) { return s.hit; }) : signals;
      const mail = work ? emails.filter(function (e) { return e.hit; }) : emails;
      board.innerHTML =
        paintList("Inbox signals", "Mailbox is read-only. Nothing is sent from here.", mail.length ? mail : emails) +
        paintList("Content-related boards", "Click a URL. Same pain as the notes you post.", web.length ? web : signals) +
        paintList("Look here", "Redmine / Rails / Qt boards tied to Content experience.", sources) +
        paintList("Named people", "Empty until someone shows interest.", people);
    });
  }

  function operate() {
    let lane = "active";
    let sec = null;
    const board = document.getElementById("board");
    function paint() {
      if (!sec) return;
      const rows = (lane === "planned" ? sec.planned : sec.active).map(function (item) {
        return Object.assign({}, item, {
          jumps: [{ label: "Build work", page: "/app/analysis.html", extra: { work: item.title } }],
        });
      });
      board.innerHTML = paintList(sec.title + " · " + sec.desk, sec.blurb, rows);
    }
    document.querySelectorAll("[data-lane]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        lane = btn.getAttribute("data-lane") || "active";
        document.querySelectorAll("[data-lane]").forEach(function (b) {
          b.classList.toggle("is-on", b === btn);
        });
        paint();
      });
    });
    fetchJSON("/api/works").then(function (data) {
      if (!data) return;
      sec = (data.sections || []).find(function (s) { return s.id === "business"; });
      paint();
    });
  }

  if (page === "analysis") analysis();
  if (page === "content") content();
  if (page === "network") network();
  if (page === "operate") operate();
})();
