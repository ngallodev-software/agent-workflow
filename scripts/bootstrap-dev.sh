#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${AGENT_WORKFLOW_VENV:-$ROOT/.venv}"
PYTHON_BIN="${AGENT_WORKFLOW_DEV_PYTHON:-python3}"

if [[ ! -x "$VENV/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade --editable "$ROOT[dev]"
echo "development environment ready: $VENV/bin/python"
echo "run: $VENV/bin/python -m pytest -q"
echo "run: AGENT_WORKFLOW_PYTHON=$VENV/bin/python ./scripts/release-check.sh"
