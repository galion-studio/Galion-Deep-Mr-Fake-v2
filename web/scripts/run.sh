#!/usr/bin/env bash
# Run the FastAPI app on port 8765 (override with PORT= or HOST=).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="${VENV:-$ROOT/web/.venv}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8765}"

if [[ ! -f "$ROOT/web/app.py" ]]; then
  echo "web/app.py is missing. The FastAPI app ships with the web MVP." >&2
  exit 1
fi

if [[ ! -x "$VENV/bin/uvicorn" ]]; then
  echo "uvicorn is not installed. Run: make install" >&2
  exit 1
fi

cd "$ROOT/web"
exec "$VENV/bin/uvicorn" app:app --reload --host "$HOST" --port "$PORT"
