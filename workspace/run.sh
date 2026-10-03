#!/usr/bin/env bash
# Hub on http://127.0.0.1:4040/
#   ./run.sh          # start (if needed) and open the browser
#   ./run.sh start    # start only, no browser
#   ./run.sh stop
#
# A browser bookmark of http://127.0.0.1:4040/ cannot start this script.
# Closing the last hub tab stops the server after a few seconds.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HUB="$ROOT/dashboard"
RUN="$HUB/.run"
URL="http://127.0.0.1:4040/"
mkdir -p "$RUN"

stop_port() {
  local p="$1"
  local pids
  pids="$(lsof -t -iTCP:"$p" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${pids:-}" ]]; then
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 0.2
  fi
}

hub_up() {
  curl -sf -o /dev/null --max-time 1 "${URL}auth/" 2>/dev/null
}

start_hub() {
  if hub_up; then
    return 0
  fi
  stop_port 4040
  (
    cd "$HUB"
    exec python3 serve.py
  ) >>"$RUN/hub.log" 2>&1 &
  echo $! >"$RUN/hub.pid"
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if hub_up; then
      return 0
    fi
    sleep 0.2
  done
  echo "Hub did not bind :4040 — see $RUN/hub.log" >&2
  return 1
}

start_leads() {
  # Content + Network dashboards (Vite :6175, API :6050)
  "$ROOT/leads/scripts/empever" start
}

stop_leads() {
  "$ROOT/leads/scripts/empever" stop || true
}

open_browser() {
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  elif command -v gio >/dev/null 2>&1; then
    gio open "$URL" >/dev/null 2>&1 || true
  fi
}

case "${1:-open}" in
stop)
  stop_leads
  stop_port 4040
  echo "Stopped $URL"
  ;;
start)
  start_hub
  start_leads
  echo "Hub: $URL"
  echo "Stop: $ROOT/run.sh stop  (or close the last browser tab)"
  ;;
lan)
  export ANSIF_HUB_HOST=0.0.0.0
  stop_port 4040
  start_hub
  start_leads
  echo "Hub on LAN: http://0.0.0.0:4040/  (phone on the same Wi-Fi)"
  hostname -I 2>/dev/null | awk '{print "  try http://"$1":4040/"}'
  echo "Stop: $ROOT/run.sh stop"
  ;;
open)
  start_hub
  start_leads
  open_browser
  echo "Opened $URL"
  echo "Close the last tab to stop, or: $ROOT/run.sh stop"
  ;;
*)
  echo "Usage: $0 [open|start|lan|stop]" >&2
  exit 1
  ;;
esac
