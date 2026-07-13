#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python3 -m compileall -q src
bash -n install.sh uninstall.sh bin/agent-workflow scripts/*.sh
find templates src/agent_workflow/assets -type f -name '*.sh' -print0 \
  | xargs -0 -r -n1 bash -n
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
