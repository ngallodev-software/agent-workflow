#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

cleanup_bytecode() {
  find src tests scripts -type d -name __pycache__ -prune -exec rm -rf {} +
}
trap cleanup_bytecode EXIT
cleanup_bytecode

python3 scripts/audit-release-assets.py --write-manifest
python3 scripts/audit-release-assets.py
python3 -m compileall -q src tests scripts
bash -n install.sh uninstall.sh bin/agent-workflow scripts/*.sh
while IFS= read -r -d '' path; do
  bash -n "$path"
done < <(find templates src/agent_workflow/assets -type f -name '*.sh' -print0)
python3 -m unittest discover -s tests -v
python3 -m agent_workflow pack validate examples/three-phase-pack
python3 - <<'PY'
import json
from pathlib import Path
for path in Path('schemas').glob('*.json'):
    json.loads(path.read_text(encoding='utf-8'))
print('JSON schemas: valid syntax')
PY

echo "release checks passed"
