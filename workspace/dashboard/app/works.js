(function () {
  const board = document.getElementById("board");
  const nextEl = document.getElementById("next");
  const howEl = document.getElementById("how");
  const hostEl = document.getElementById("host");
  let lane = "active";
  let data = null;

  function esc(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function itemsHtml(items, deskHref) {
    if (!items || !items.length) {
      return "<p class=\"empty\">Nothing on this list.</p>";
    }
    return items
      .map(function (item) {
        const href = (window.Works && window.Works.deskHref)
          ? window.Works.deskHref(deskHref || "/app/", { work: item.title })
          : (deskHref || "/app/");
        return (
          "<div class=\"item\"><span class=\"chip\">" +
          esc(item.status) +
          "</span><div><strong><a class=\"sec-link\" href=\"" +
          esc(href) +
          "\">" +
          esc(item.title) +
          "</a></strong>" +
          (item.detail ? "<p>" + esc(item.detail) + "</p>" : "") +
          (item.action ? "<p class=\"action\">" + esc(item.action) + "</p>" : "") +
          "</div></div>"
        );
      })
      .join("");
  }

  function paint() {
    if (!data) return;
    nextEl.textContent = data.next || "";
    howEl.textContent = data.publish_how || "";
    hostEl.textContent =
      (data.host === "localhost" ? "Server: this PC (localhost). Cloud after it works well." : "Server: " + data.host);
    const sections = data.sections || [];
    board.innerHTML = sections
      .map(function (sec) {
        const rows = lane === "planned" ? sec.planned : sec.active;
        if (!rows || !rows.length) return "";
        return (
          "<section><h2><a class=\"sec-link\" href=\"" +
          esc(sec.href || "/app/") +
          "\">" +
          esc(sec.title) +
          " · " +
          esc(sec.desk) +
          "</a></h2><p class=\"blurb\">" +
          esc(sec.blurb) +
          "</p>" +
          itemsHtml(rows, sec.href) +
          "</section>"
        );
      })
      .join("");
    if (!board.innerHTML) {
      board.innerHTML = "<p class=\"empty\" style=\"padding:1rem\">Nothing in " + esc(lane) + ".</p>";
    }
  }

  document.querySelectorAll(".lane").forEach(function (btn) {
    btn.addEventListener("click", function () {
      lane = btn.getAttribute("data-lane") || "active";
      document.querySelectorAll(".lane").forEach(function (b) {
        b.classList.toggle("is-on", b === btn);
      });
      paint();
    });
  });

  fetch("/api/works", { credentials: "same-origin" })
    .then(function (r) {
      if (r.status === 401) {
        location.href = "/auth/";
        return null;
      }
      return r.json();
    })
    .then(function (json) {
      if (!json || !json.ok) return;
      data = json;
      paint();
    })
    .catch(function () {
      nextEl.textContent = "Could not load work status.";
    });
})();
