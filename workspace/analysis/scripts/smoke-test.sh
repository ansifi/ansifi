#!/usr/bin/env bash
set -euo pipefail

API="${CODING_AGENT_API_BASE:-http://127.0.0.1:8006}"
PASS=0
FAIL=0
SKIP=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }
skip() { echo "  SKIP: $1"; SKIP=$((SKIP + 1)); }

check_http() {
  local name="$1"
  local method="$2"
  local url="$3"
  local data="${4:-}"
  local expect="${5:-200}"

  if [ "$method" = "GET" ]; then
    code=$(curl -s -o /tmp/coding_agent_smoke_body.json -w "%{http_code}" "$url")
  else
    code=$(curl -s -o /tmp/coding_agent_smoke_body.json -w "%{http_code}" -X "$method" -H "Content-Type: application/json" -d "$data" "$url")
  fi

  if [ "$code" = "$expect" ]; then
    pass "$name (HTTP $code)"
    return 0
  fi
  fail "$name (expected HTTP $expect, got $code) — $(head -c 200 /tmp/coding_agent_smoke_body.json)"
  return 1
}

echo "=== Coding Agent Smoke Test ==="
echo "API: $API"
echo

echo "[1] Health & features"
check_http "GET /health" GET "$API/health"
if python3 -c "import json; d=json.load(open('/tmp/coding_agent_smoke_body.json')); assert d.get('status')=='ok' and 'features' in d" 2>/dev/null; then
  pass "health payload has status + features"
else
  fail "health payload invalid"
fi

echo
echo "[2] Models"
check_http "GET /api/models" GET "$API/api/models"

echo
echo "[3] Workspace tree"
check_http "GET /api/tree" GET "$API/api/tree"
if python3 -c "import json; d=json.load(open('/tmp/coding_agent_smoke_body.json')); assert 'entries' in d and 'workspace' in d" 2>/dev/null; then
  pass "tree payload has workspace + entries"
else
  fail "tree payload invalid"
fi

echo
echo "[4] File read"
check_http "GET /api/file" GET "$API/api/file?path=solutions/grafana/README.md"
if python3 -c "import json; d=json.load(open('/tmp/coding_agent_smoke_body.json')); c=d.get('content',''); assert 'grafana' in c.lower()" 2>/dev/null; then
  pass "solutions/grafana/README.md content readable"
else
  fail "solutions/grafana/README.md missing — is workspace 01_Build?"
fi

echo
echo "[5] File write"
TEST_FILE="solutions/grafana/smoke_test_$$.txt"
check_http "PUT /api/file" PUT "$API/api/file" "{\"path\":\"$TEST_FILE\",\"content\":\"smoke test ok\"}"
check_http "verify written file" GET "$API/api/file?path=$TEST_FILE"
rm -f "/home/ansif/works/01_Build/$TEST_FILE" 2>/dev/null || true

echo
echo "[6] Command execution"
check_http "POST /api/command/run" POST "$API/api/command/run" '{"command":"pwd"}'
if python3 -c "import json; d=json.load(open('/tmp/coding_agent_smoke_body.json')); assert d.get('result',{}).get('exit_code')==0" 2>/dev/null; then
  pass "pwd exit 0"
else
  fail "command execution result unexpected"
fi

echo
echo "[7] Sessions"
check_http "POST /api/sessions" POST "$API/api/sessions" '{"title":"Smoke test session"}'
SESSION_ID=$(python3 -c "import json; print(json.load(open('/tmp/coding_agent_smoke_body.json'))['session']['id'])" 2>/dev/null || echo "")
if [ -n "$SESSION_ID" ]; then
  pass "session created: $SESSION_ID"
  check_http "GET /api/sessions" GET "$API/api/sessions"
  check_http "GET /api/sessions/{id}" GET "$API/api/sessions/$SESSION_ID"
else
  fail "session creation returned no id"
fi

echo
echo "[8] Git"
GIT_CODE=$(curl -s -o /tmp/coding_agent_smoke_body.json -w "%{http_code}" "$API/api/git/status")
if [ "$GIT_CODE" = "200" ]; then
  pass "GET /api/git/status"
  check_http "GET /api/git/diff" GET "$API/api/git/diff"
else
  skip "git status (workspace may not be a git repo, HTTP $GIT_CODE)"
fi

echo
echo "[9] Open folder API"
WORKSPACE_ROOT="$(cd "$(dirname "$0")/.." && pwd)/workspace"
check_http "POST /api/workspace/open-folder" POST "$API/api/workspace/open-folder" "{\"path\":\"$WORKSPACE_ROOT\"}"

echo
echo "[10] Agent execute (requires Ollama)"
AVAILABLE_MODEL=$(python3 -c "import json; d=json.load(open('/tmp/coding_agent_smoke_body.json')); print((d.get('models') or [''])[0])" 2>/dev/null || echo "")
if [ -z "$AVAILABLE_MODEL" ] && [ -f /tmp/coding_agent_models.json ]; then
  AVAILABLE_MODEL=$(python3 -c "import json; d=json.load(open('/tmp/coding_agent_models.json')); m=d.get('models') or []; print(m[0] if m else '')")
fi
curl -s "$API/api/models" -o /tmp/coding_agent_models.json
AVAILABLE_MODEL=$(python3 -c "import json; d=json.load(open('/tmp/coding_agent_models.json')); m=d.get('models') or []; print(m[0] if m else '')")
AGENT_BODY="{\"prompt\":\"List files in the workspace and reply with the count only.\",\"session_id\":\"$SESSION_ID\",\"model\":\"$AVAILABLE_MODEL\"}"
AGENT_CODE=$(curl -s -o /tmp/coding_agent_smoke_body.json -w "%{http_code}" --max-time 180 -X POST \
  -H "Content-Type: application/json" \
  -d "$AGENT_BODY" \
  "$API/api/agent/execute")
if [ -z "$AVAILABLE_MODEL" ]; then
  skip "agent execute (no Ollama models installed — run: ollama pull qwen2.5-coder:0.5b)"
elif [ "$AGENT_CODE" = "200" ]; then
  if python3 -c "import json; d=json.load(open('/tmp/coding_agent_smoke_body.json')); assert d.get('status')=='success' and d.get('result',{}).get('reply')" 2>/dev/null; then
    pass "agent execute returned a reply"
  else
    fail "agent execute response invalid"
  fi
else
  skip "agent execute (HTTP $AGENT_CODE — is Ollama running with qwen2.5-coder:14b?)"
fi

echo
echo "[11] Agent stream (requires Ollama)"
STREAM_OUT="/tmp/coding_agent_smoke_stream.txt"
STREAM_BODY="{\"prompt\":\"Reply with the word READY only.\",\"model\":\"$AVAILABLE_MODEL\"}"
if [ -z "$AVAILABLE_MODEL" ]; then
  skip "agent stream (no Ollama models installed)"
elif curl -s -o "$STREAM_OUT" -w "%{http_code}" --max-time 180 -X POST \
  -H "Content-Type: application/json" \
  -d "$STREAM_BODY" \
  "$API/api/agent/stream" | grep -q 200; then
  if grep -q '"type": "assistant"' "$STREAM_OUT" || grep -q '"type": "done"' "$STREAM_OUT"; then
    pass "agent stream returned events"
  else
    fail "agent stream missing expected events"
  fi
else
  skip "agent stream request failed"
fi

echo
echo "[12] Desktop UI static server"
UI_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5176/ 2>/dev/null || echo "000")
if [ "$UI_CODE" = "200" ]; then
  pass "desktop UI on :5176"
else
  skip "desktop UI not running on :5176 (start with ./scripts/desktop-start)"
fi

echo
echo "[13] Frontend production build"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$ROOT/frontend/dist/index.html" ]; then
  pass "frontend dist exists"
else
  fail "frontend dist missing — run: npm run build --prefix frontend"
fi

echo
echo "=== Summary ==="
echo "PASS: $PASS"
echo "FAIL: $FAIL"
echo "SKIP: $SKIP"
echo

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
