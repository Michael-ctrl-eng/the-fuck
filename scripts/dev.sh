#!/usr/bin/env bash
# Raqib dev preview: starts the FastAPI backend (port 8000, or $API_PORT)
# then the Vite dev server on $PORT (default 5173). Vite proxies /api to the API.
# POSIX-sh compatible (runs under `sh` in managed preview environments).
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${PORT:-5173}"

export VITE_API_PROXY="http://127.0.0.1:${API_PORT}"
export PORT="$WEB_PORT"

API_CMD=""
if [ -x "$ROOT/.venv/bin/python" ]; then
  API_CMD="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  API_CMD="python3"
else
  API_CMD="python"
fi

echo "[raqib] starting API on :${API_PORT} (${API_CMD})"
"$API_CMD" "$ROOT/api/run.py" --port "$API_PORT" --host 127.0.0.1 &
API_PID=$!

cleanup() {
  kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# wait for API readiness
for i in $(seq 1 60); do
  if curl -fsS -m 2 "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

cd "$ROOT"
exec bun run dev:web
