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

EVIDENCE_DIR="${AGENT_WORKFLOW_RELEASE_EVIDENCE_DIR:-$ROOT/build/release-evidence}"
JUNIT_PATH="$EVIDENCE_DIR/pytest-junit.xml"
mkdir -p "$EVIDENCE_DIR"
rm -f "$JUNIT_PATH"

cleanup_bytecode() {
  find src tests scripts -type d -name __pycache__ -prune -exec rm -rf {} +
}

generate_release_evidence() {
  local technical_exit_code="$1"
  local args=(
    --root "$ROOT"
    --output-dir "$EVIDENCE_DIR"
    --technical-exit-code "$technical_exit_code"
  )
  if [[ -f "$JUNIT_PATH" ]]; then
    args+=(--test-results "$JUNIT_PATH")
  fi
  if [[ -n "${AGENT_WORKFLOW_RELEASE_ARTIFACTS:-}" ]]; then
    local artifact
    IFS=':' read -r -a artifacts <<<"$AGENT_WORKFLOW_RELEASE_ARTIFACTS"
    for artifact in "${artifacts[@]}"; do
      [[ -n "$artifact" ]] && args+=(--artifact "$artifact")
    done
  fi
  if [[ "${AGENT_WORKFLOW_ENFORCE_RELEASE_BLOCKERS:-0}" == "1" ]]; then
    args+=(--enforce-blockers)
  fi
  "$PYTHON_BIN" scripts/release-evidence.py "${args[@]}"
}

on_exit() {
  local result="$?"
  trap - EXIT
  cleanup_bytecode
  generate_release_evidence "$result" >/dev/null || true
  exit "$result"
}
trap on_exit EXIT
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
# Dedicated acceptance fixtures must not inherit the coordinator's tmux pane;
# otherwise a nested tmux server can outlive the test and leave a completed
# fake executor projected as `running`.
env -u TMUX -u TMUX_PANE "$PYTHON_BIN" -m pytest -q --junitxml "$JUNIT_PATH"
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

trap - EXIT
cleanup_bytecode
set +e
generate_release_evidence 0
evidence_result=$?
set -e
if [[ "$evidence_result" -ne 0 ]]; then
  exit "$evidence_result"
fi

echo "technical release checks passed; durable evidence: $EVIDENCE_DIR/release-evidence.json"
