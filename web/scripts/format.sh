#!/usr/bin/env bash
# Format with Ruff's formatter (Black-compatible: 88 columns, double quotes).
# CHECK=1 runs in check mode and does not write files.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="${VENV:-$ROOT/web/.venv}"

if [[ ! -x "$VENV/bin/ruff" ]]; then
  echo "ruff is not installed. Run: make install" >&2
  exit 1
fi

cd "$ROOT"
args=(format --no-cache)
if [[ "${CHECK:-}" == "1" ]]; then
  args+=(--check)
fi

exec "$VENV/bin/ruff" "${args[@]}" "$@"
