#!/usr/bin/env bash
# Ruff lint. Uses the default rule set in ruff.toml (no app rewrite required).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="${VENV:-$ROOT/web/.venv}"

if [[ ! -x "$VENV/bin/ruff" ]]; then
  echo "ruff is not installed. Run: make install" >&2
  exit 1
fi

cd "$ROOT"
exec "$VENV/bin/ruff" check --no-cache "$@"
