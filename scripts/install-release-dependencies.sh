#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON_BIN="${AGENT_WORKFLOW_RELEASE_PYTHON:-python}"
# release/dependency-lock.json is the single authority for VCS-only source pins.

read_lock_field() {
  local field="$1"
  "$PYTHON_BIN" - "$field" <<'PY'
import json
from pathlib import Path
import sys

field = sys.argv[1]
lock = json.loads(Path("release/dependency-lock.json").read_text(encoding="utf-8"))
package = next(
    (item for item in lock["packages"] if item["name"] == "agent-workflow-comparative-eval"),
    None,
)
if package is None:
    raise SystemExit("release dependency lock is missing agent-workflow-comparative-eval")
value = package.get(field)
if not isinstance(value, str) or not value:
    raise SystemExit(f"comparative-eval lock entry is missing {field}")
print(value)
PY
}

COMPARATIVE_EVAL_VERSION="$(read_lock_field version)"
COMPARATIVE_EVAL_REVISION="$(read_lock_field source_revision)"

"$PYTHON_BIN" - "$COMPARATIVE_EVAL_REVISION" <<'PY'
import re
import sys

revision = sys.argv[1]
if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
    raise SystemExit(f"invalid comparative-eval source revision: {revision!r}")
PY

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install \
  'setuptools>=61' 'pytest>=8,<10' 'jsonschema>=4.18,<5' \
  'PyYAML>=6.0.3,<7' 'mcp==1.28.1' 'build>=1.2,<2' \
  'specgen-agent-workflow-contracts @ https://github.com/ngallodev-software/agent-workflow-spec-contracts/releases/download/v0.2.1/specgen_agent_workflow_contracts-0.2.1-py3-none-any.whl#sha256=d254a0b13f2fd1de732dab2abd33da35db9ea365b50b3214e92308fea79d85c2' \
  "agent-workflow-comparative-eval @ git+https://github.com/ngallodev-software/agent-workflow-comparative-eval.git@${COMPARATIVE_EVAL_REVISION}"

"$PYTHON_BIN" - "$COMPARATIVE_EVAL_VERSION" "$COMPARATIVE_EVAL_REVISION" <<'PY'
from importlib import metadata
import sys

expected_version, revision = sys.argv[1:]
observed = metadata.version("agent-workflow-comparative-eval")
if observed != expected_version:
    raise SystemExit(
        "comparative-eval source revision "
        f"{revision} installed version {observed}; release lock expects {expected_version}"
    )
print(f"comparative-eval release dependency: {observed} @ {revision}")
PY
