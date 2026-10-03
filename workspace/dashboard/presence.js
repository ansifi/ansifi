(function () {
  var id = "t" + Math.random().toString(36).slice(2) + Date.now().toString(36);
  function ping() {
    fetch("/api/presence?id=" + encodeURIComponent(id), {
      method: "POST",
      credentials: "same-origin",
    }).catch(function () {});
  }
  ping();
  setInterval(ping, 20000);
  window.addEventListener("pagehide", function () {
    navigator.sendBeacon("/api/presence/bye?id=" + encodeURIComponent(id));
  });
})();
