#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$ROOT/.run"
if command -v lsof >/dev/null 2>&1; then
  old="$(lsof -t -iTCP:4040 -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$old" ]]; then kill $old 2>/dev/null || true; sleep 0.2; fi
fi
exec python3 "$ROOT/serve.py"
