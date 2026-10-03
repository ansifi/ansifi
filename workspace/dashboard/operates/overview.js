function qs(name) {
  return new URLSearchParams(location.search).get(name) || "";
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function monthLabel(month) {
  const parts = String(month || "").split("-");
  if (parts.length < 2) return month || "";
  const names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return names[Number(parts[1]) - 1] || parts[1];
}

function formatPct(n) {
  if (n === null || n === undefined || n === "") return "—";
  const v = Math.round(Number(n));
  if (Number.isNaN(v)) return "—";
  return v > 0 ? "+" + v + "%" : v + "%";
}

function pctKind(n) {
  if (n === null || n === undefined || Number(n) === 0 || Number.isNaN(Number(n))) return "flat";
  return Number(n) > 0 ? "up" : "down";
}

function paintPctBars(id, pcts, labels) {
  const nums = (pcts || []).map(function (n) {
    return n === null || n === undefined || n === "" ? null : Number(n);
  });
  if (!nums.length) nums.push(null);
  const mags = nums.map(function (n) {
    return n === null || Number.isNaN(n) ? 0 : Math.abs(n);
  });
  const max = Math.max.apply(null, mags.concat([1]));
  document.getElementById(id).innerHTML = nums
    .map(function (n, i) {
      const mag = n === null || Number.isNaN(n) ? 0 : Math.abs(n);
      const h = Math.max(8, (mag / max) * 100);
      const label = labels && labels[i] ? "<em>" + escapeHtml(labels[i]) + "</em>" : "";
      return (
        '<div class="bar ' +
        pctKind(n) +
        '" style="height:' +
        h +
        '%"><span>' +
        formatPct(n) +
        "</span>" +
        label +
        "</div>"
      );
    })
    .join("");
}

function paintCountBars(id, series, kind) {
  const nums = (series || []).map(function (n) {
    return Number(n) || 0;
  });
  if (!nums.length) nums.push(0);
  const max = Math.max.apply(null, nums.concat([1]));
  document.getElementById(id).innerHTML = nums
    .map(function (n) {
      const h = Math.max(8, (n / max) * 100);
      return '<div class="bar ' + (kind || "flat") + '" style="height:' + h + '%"></div>';
    })
    .join("");
}

fetch("/api/ai/home", { credentials: "same-origin" })
  .then(function (r) {
    if (r.status === 401) throw new Error("login_required");
    return r.json();
  })
  .then(function (data) {
    const wanted = qs("tenant");
    const clients = (data && data.clients) || [];
    const row =
      clients.find(function (c) {
        return c.id === wanted;
      }) ||
      clients[0] ||
      {};
    document.getElementById("title").textContent = row.name || wanted || "Admin client";
    const g = row.growth || {};
    const rev = row.revenue || {};
    const trend = rev.label || "steady";
    document.getElementById("lede").textContent =
      Number(row.nested_count || 0) +
      " nested desks · desks " +
      (g.direction || "flat") +
      " · billed " +
      trend +
      " · " +
      Number(row.invoice_count || 0) +
      " invoices since Apr. Figures on this page are percent change, not rupees.";
    const kind = rev.direction || "flat";
    const pctNow = rev.pct_label || formatPct(rev.pct_change);
    document.getElementById("rev-head").innerHTML =
      '<span class="trend ' +
      kind +
      '">' +
      escapeHtml(trend) +
      "</span>" +
      '<p class="rev-now">' +
      escapeHtml(pctNow) +
      " vs last month</p>" +
      '<p class="digest-lede">Sevendyne billed change, last six months (percent vs previous month).</p>';
    const months = rev.months || [];
    paintPctBars(
      "rev-bars",
      months.map(function (m) {
        return m.pct_change;
      }),
      months.map(function (m) {
        return monthLabel(m.month);
      })
    );
    const series = g.series && g.series.length ? g.series : [row.nested_count || 0];
    paintCountBars("bars", series, g.direction || "flat");
    const nested = row.nested || [];
    document.getElementById("nested").innerHTML = nested.length
      ? "<ul>" +
        nested
          .map(function (n) {
            return "<li>" + escapeHtml(n.name) + "</li>";
          })
          .join("") +
        "</ul>"
      : "<p class=\"digest-lede\">No nested desks.</p>";
    const posts = row.posts || {};
    document.getElementById("activity").innerHTML =
      "<p>Posts created " +
      Number(posts.created || 0) +
      ", sent " +
      Number(posts.sent || 0) +
      ", viewed " +
      Number(posts.viewed || 0) +
      ".</p><p>Open leads " +
      Number(row.leads_open || 0) +
      ".</p>";
  })
  .catch(function (err) {
    document.getElementById("lede").textContent = String(err.message || err);
  });
