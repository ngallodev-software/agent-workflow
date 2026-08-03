#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
OUT=${1:-"$ROOT/handoff-evidence/local-gates"}
mkdir -p "$OUT"
cd "$ROOT"
run() {
  local name=$1; shift
  printf 'COMMAND:' >"$OUT/$name.command.txt"; printf ' %q' "$@" >>"$OUT/$name.command.txt"; printf '\n' >>"$OUT/$name.command.txt"
  set +e
  "$@" >"$OUT/$name.stdout.txt" 2>"$OUT/$name.stderr.txt"
  rc=$?
  set -e
  printf '%s\n' "$rc" >"$OUT/$name.exit-code.txt"
  if [[ $rc -ne 0 ]]; then echo "$name failed with $rc" >&2; return "$rc"; fi
}
run compileall python -m compileall -q src
run invariants pytest -q tests/invariants
run release pytest -q tests/release/test_distribution.py tests/release/test_documentation_sync.py tests/release/test_release_installers.py
run release-audit python scripts/audit-release-assets.py
run pack-validate agent-workflow pack validate prompt-packs/benchmark-real-host-release-candidate-gate
run evaluator-self-test python prompt-packs/benchmark-real-host-release-candidate-gate/evals/evaluate_handoff.py --self-test
printf 'local gates complete: %s\n' "$OUT"
