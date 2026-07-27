#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -n "${AGENT_WORKFLOW_PYTHON:-}" ]]; then
  PYTHON_BIN="$AGENT_WORKFLOW_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3)"
fi
if ! "$PYTHON_BIN" -c 'import pytest' >/dev/null 2>&1; then
  echo "release checks require pytest in: $PYTHON_BIN" >&2
  echo "run scripts/bootstrap-dev.sh or set AGENT_WORKFLOW_PYTHON" >&2
  exit 2
fi

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONNOUSERSITE=1
export PIP_IGNORE_INSTALLED=1

cleanup_bytecode() {
  find src tests scripts -type d -name __pycache__ -prune -exec rm -rf {} +
}
trap cleanup_bytecode EXIT
cleanup_bytecode

bash -n scripts/bootstrap-dev.sh
"$PYTHON_BIN" scripts/audit-release-assets.py
"$PYTHON_BIN" -m compileall -q src tests scripts
bash -n install.sh uninstall.sh bin/agent-workflow scripts/*.sh
while IFS= read -r -d '' path; do
  bash -n "$path"
done < <(find templates src/agent_workflow/assets -type f -name '*.sh' -print0)
for path in scripts/hooks/agent-workflow-session-reminder scripts/hooks/codebase-memory-session-reminder scripts/hooks/rtk-session-reminder; do
  bash -n "$path"
done
"$PYTHON_BIN" -m pytest -q
"$PYTHON_BIN" -m agent_workflow pack validate examples/three-phase-pack
for pack in prompt-packs/*; do
  [[ -d "$pack" ]] || continue
  "$PYTHON_BIN" -m agent_workflow pack validate "$pack"
done
"$PYTHON_BIN" - <<'PY'
import json
from pathlib import Path
for path in Path('schemas').glob('*.json'):
    json.loads(path.read_text(encoding='utf-8'))
print('JSON schemas: valid syntax')
PY

echo "release checks passed"
