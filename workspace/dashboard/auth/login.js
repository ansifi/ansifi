(function () {
  var form = document.getElementById("empever-login-form");
  var err = document.getElementById("empever-login-error");
  var userEl = document.getElementById("empever-user");
  var passEl = document.getElementById("empever-pass");
  var known = { csr: 1, geoxyz: 1, quantyf: 1, ovt: 1, crossdock: 1, dummy_client: 1 };

  function tenantId() {
    var parts = (location.pathname || "/").split("/").filter(Boolean);
    var first = (parts[0] || "").toLowerCase();
    return known[first] ? first : "";
  }

  function destFor(user) {
    if (tenantId()) return (user && user.home) || homeUrl();
    return "/app/operate.html";
  }

  var brand = "Ansif Workspace";
  var titleEl = document.getElementById("login-title");
  var markEl = document.querySelector(".login-mark");
  if (titleEl) titleEl.textContent = brand;
  if (markEl) markEl.textContent = brand.charAt(0);
  document.title = brand + " — sign in";
  fetch("/api/tenant", { credentials: "same-origin" })
    .then(function (r) {
      return r.ok ? r.json() : null;
    })
    .then(function (data) {
      if (!data || !data.ok) return;
      var title = "Ansif Workspace";
      if (titleEl) titleEl.textContent = title;
      if (markEl) markEl.textContent = "A";
      document.title = title + " — sign in";
    })
    .catch(function () {});

  function showError(msg) {
    if (!err) return;
    err.hidden = !msg;
    err.textContent = msg || "";
  }

  fetch("/api/auth/me", { credentials: "same-origin" })
    .then(function (r) {
      return r.ok ? r.json() : null;
    })
    .then(function (data) {
      if (!data || !data.ok) return;
      var user = data.user || {};
      window.location.href = destFor(user);
    })
    .catch(function () {});

  if (!form) return;
  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    showError("");
    var btn = form.querySelector("button[type='submit']");
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Signing in…";
    }
    fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        username: (userEl && userEl.value) || "",
        password: (passEl && passEl.value) || "",
      }),
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        if (res.ok && res.data && res.data.ok) {
          var user = res.data.user || {};
          window.location.href = destFor(user);
          return;
        }
        showError((res.data && res.data.error) || "Invalid username or password");
        if (btn) {
          btn.disabled = false;
          btn.textContent = "Sign in";
        }
      })
      .catch(function () {
        showError("Sign in failed. Try again.");
        if (btn) {
          btn.disabled = false;
          btn.textContent = "Sign in";
        }
      });
  });
})();
