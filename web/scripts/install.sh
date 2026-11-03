#!/usr/bin/env bash
# Create web/.venv and install runtime + dev dependencies.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
VENV="${VENV:-$ROOT/web/.venv}"

if [[ ! -f "$ROOT/web/requirements.txt" ]]; then
  echo "web/requirements.txt is missing. The FastAPI app ships with the web MVP (web/app.py)." >&2
  exit 1
fi

if [[ ! -x "$VENV/bin/python" ]]; then
  rm -rf "$VENV"
  if ! "$PYTHON" -m venv "$VENV"; then
    echo "Could not create $VENV." >&2
    echo "On Debian/Ubuntu install the venv package (sudo apt install python3-venv) and retry." >&2
    exit 1
  fi
fi

pip_args=(-r "$ROOT/web/requirements.txt" -r "$ROOT/requirements-dev.txt")
# Pytest pins live in web/requirements-dev.txt when that suite is in the checkout.
if [[ -f "$ROOT/web/requirements-dev.txt" ]]; then
  pip_args+=(-r "$ROOT/web/requirements-dev.txt")
fi

"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install "${pip_args[@]}"

echo "Installed into $VENV"
echo "Next: make run    or    web/scripts/run.sh"
