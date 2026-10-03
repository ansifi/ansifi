#!/usr/bin/env bash
# GNOME dock PATH has no nvm/node — run the Electron ELF, not the node wrapper.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
LOG="${XDG_STATE_HOME:-$HOME/.local/state}/ansif-workspace/launch.log"
mkdir -p "$(dirname "$LOG")"
ELECTRON="$DIR/node_modules/electron/dist/electron"

if [[ ! -x "$ELECTRON" ]]; then
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [[ -s "$NVM_DIR/nvm.sh" ]]; then
    # shellcheck disable=SC1091
    . "$NVM_DIR/nvm.sh"
  fi
  export PATH="${NVM_BIN:-$HOME/.nvm/versions/node/v18.20.8/bin}:/usr/bin:/bin:${PATH:-}"
  echo "$(date -Is) installing electron" >>"$LOG"
  npm install --no-audit --no-fund --omit=optional >>"$LOG" 2>&1
fi

if [[ ! -x "$ELECTRON" ]]; then
  echo "$(date -Is) missing $ELECTRON" >>"$LOG"
  exit 1
fi

export DISPLAY="${DISPLAY:-:0}"
export ELECTRON_CACHE="${ELECTRON_CACHE:-$HOME/.cache/electron}"
echo "$(date -Is) exec $ELECTRON" >>"$LOG"
exec "$ELECTRON" . --class=AnsifWorkspace
