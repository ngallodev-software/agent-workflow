#!/usr/bin/env bash
set -euo pipefail

expected_openspec="1.13.2"
observed_openspec="$(openspec --version)"
[[ "$observed_openspec" == "$expected_openspec" ]] || {
  echo "expected OpenSpec $expected_openspec, got $observed_openspec" >&2
  exit 1
}

python - <<'PY'
try:
    import specgen_contracts  # noqa: F401
except ModuleNotFoundError:
    pass
else:
    raise SystemExit("Phase-0 upstream smoke must run without specgen_contracts installed")
PY

root="$(mktemp -d)"
trap 'rm -rf "$root"' EXIT
export XDG_STATE_HOME="$root/state"
export XDG_DATA_HOME="$root/data"
export XDG_CACHE_HOME="$root/cache"
export XDG_CONFIG_HOME="$root/config"
source_repo="$root/source"
pack="$root/pack"
policy="$root/job-policy.json"
mkdir -p "$source_repo/src"
printf '__pycache__/\n' > "$source_repo/.gitignore"

git -C "$source_repo" init -q
git -C "$source_repo" config user.email "ci@example.invalid"
git -C "$source_repo" config user.name "Agent-Workflow CI"
printf 'VALUE = 1\n' > "$source_repo/src/placeholder.py"

(
  cd "$source_repo"
  openspec init --tools none >/dev/null
  openspec new change add-rate-limit --schema spec-driven >/dev/null
)

change="$source_repo/openspec/changes/add-rate-limit"
mkdir -p "$change/specs/rate-limiting"

cat > "$change/proposal.md" <<'EOF'
# Proposal

## Why

Burst traffic needs a deterministic bounded behavior so callers receive a stable response instead of exhausting service capacity.

## What Changes

- Add a request-rate limiting capability with an observable rejection behavior for bursts.

## Capabilities

### New Capabilities

- `rate-limiting`: Defines bounded request-rate behavior and the observable response when a burst exceeds the limit.

### Modified Capabilities

None.

## Impact

- Adds implementation under `src/`.
- Adds a new public behavior contract for rate limiting.
EOF

cat > "$change/specs/rate-limiting/spec.md" <<'EOF'
# Spec Delta

## Purpose

Defines deterministic request throttling behavior so callers can rely on a stable response when traffic exceeds an explicit service limit.

## ADDED Requirements

### Requirement: Burst requests are rate limited
The system SHALL reject requests that exceed the configured request-rate limit.

#### Scenario: Burst exceeds the limit
- **WHEN** request volume exceeds the configured limit
- **THEN** the system returns a rate-limit response
EOF

cat > "$change/design.md" <<'EOF'
# Design

## Context

The fixture has a small Python source tree and no existing limiter.

## Goals / Non-Goals

**Goals:**
- Add a deterministic rate-limit implementation seam.

**Non-Goals:**
- Do not change OpenSpec planning artifacts during execution.

## Decisions

Use a small source-local implementation so the writable execution boundary can be limited to `src/`.

## Risks / Trade-offs

A fixture implementation is intentionally minimal; the integration test validates the planning-to-execution boundary rather than production rate-limit behavior.
EOF

cat > "$change/tasks.md" <<'EOF'
# Tasks

## 1. Implementation

- [ ] 1.1 Add the limiter under src/ and verify the Python source compiles with `python3 -m compileall -q src`
EOF

git -C "$source_repo" add -A
git -C "$source_repo" commit -qm "add qualified openspec fixture"
source_revision="$(git -C "$source_repo" rev-parse HEAD)"

(
  cd "$source_repo"
  openspec validate add-rate-limit --strict --json --no-interactive > "$root/upstream-validation.json"
)

cat > "$policy" <<'EOF'
{
  "scope": {
    "writable_paths": [],
    "writable_trees": ["src"],
    "disposable_trees": []
  },
  "acceptance_commands": [
    {
      "id": "compile-src",
      "argv": ["python3", "-m", "compileall", "-q", "src"],
      "cwd": ".",
      "timeout_seconds": 60,
      "result_format": "exit-code",
      "junit_path": null
    }
  ],
  "criteria": [
    {
      "id": "source-compiles",
      "description": "Changed Python source compiles.",
      "acceptance_command_ids": ["compile-src"]
    }
  ],
  "review_requirement": {
    "required": false,
    "independent": false
  }
}
EOF

if ! agent-workflow --json pack import-openspec \
  "$source_repo" add-rate-limit "$pack" --job-policy "$policy" \
  > "$root/import.json"; then
  diagnostic_root="${XDG_STATE_HOME:-$HOME/.local/state}/agent-workflow/diagnostics/unexpected"
  if [[ -d "$diagnostic_root" ]]; then
    echo "Agent-Workflow unexpected diagnostics:" >&2
    find "$diagnostic_root" -maxdepth 1 -type f -name '*.json' -print -exec cat {} \; >&2 || true
  fi
  exit 1
fi

python - "$source_repo" "$root/openspec-before.json" <<'PY'
import hashlib
import json
import pathlib
import sys

repo = pathlib.Path(sys.argv[1])
snapshot = {
    path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted((repo / "openspec").rglob("*")) if path.is_file()
}
pathlib.Path(sys.argv[2]).write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
PY

shim="$root/no-openspec"
mkdir -p "$shim"
cat > "$shim/openspec" <<'SHIM'
#!/usr/bin/env bash
set -eu
printf '%s\n' "$*" >> "__LOG_PATH__"
echo "openspec is unavailable after import" >&2
exit 97
SHIM
sed -i "s|__LOG_PATH__|$root/openspec-calls.log|" "$shim/openspec"
chmod +x "$shim/openspec"
ln -s "$(command -v python3)" "$shim/python3"
export PATH="$shim:$PATH"
export OPENSPEC_SHIM_LOG="$root/openspec-calls.log"
if openspec --phase0-sentinel >"$root/shim.stdout" 2>"$root/shim.stderr"; then
  echo "OpenSpec shim did not fail closed" >&2
  exit 1
fi
grep -q -- '--phase0-sentinel' "$OPENSPEC_SHIM_LOG"
: > "$OPENSPEC_SHIM_LOG"

agent-workflow --json pack validate "$pack" --verify-checksums > "$root/pack-validation.json"

python - "$root/import.json" "$pack" "$root/pack-validation.json" <<'PY'
import json
import pathlib
import sys

imported = json.loads(pathlib.Path(sys.argv[1]).read_text())
pack = pathlib.Path(sys.argv[2])
assert json.loads(pathlib.Path(sys.argv[3]).read_text())["ok"] is True
assert imported["provider"] == "openspec@1.13.2"
assert imported["legacy_specgen_required"] is False
assert imported["tasks"] == ["openspec-add-rate-limit-1-1"]
job = json.loads(
    (pack / "jobs" / "openspec-add-rate-limit-1-1.json").read_text()
)
assert job["schema"] == "agent-workflow/native-job/v2"
assert "bundle_provenance" not in job
assert job["scope"]["writable_trees"] == ["src"]
assert "openspec" not in json.dumps(job["scope"])
PY

prompt="$pack/phase-0/tickets/openspec-add-rate-limit-1-1.md"
worker="$root/worker.py"
cat > "$worker" <<'PY'
#!/usr/bin/env python3
import sys
import json
import shutil
import subprocess
from pathlib import Path

assert Path(shutil.which("openspec")).resolve() == (
    Path(shutil.which("python3")).parent / "openspec"
).resolve()
Path("src/rate_limiter.py").write_text(
    "def allow(count, limit):\n"
    "    return count < limit\n",
    encoding="utf-8",
)
subprocess.run(["git", "add", "--", "src/rate_limiter.py"], check=True)
subprocess.run(["git", "commit", "-m", "add minimal rate limiter"], check=True)
finished = subprocess.run(
    [sys.argv[1], "--json", "agent", "finish",
     sys.argv[2], "--result", "completed"],
    check=True, text=True, capture_output=True,
)
finish_value = json.loads(finished.stdout)
assert finish_value["state"] == "finalized"
assert finish_value["fast_path"] is True
assert finish_value["verification"][0]["id"] == "compile-src"
assert finish_value["verification"][0]["ok"] is True
Path(sys.argv[3]).write_text(
    finished.stdout, encoding="utf-8"
)
PY
agent-workflow --json agent-run prepare openspec-upstream-smoke "$source_repo" "$prompt" \
  --pack "$pack" --job jobs/openspec-add-rate-limit-1-1.json \
  --tier low --worker-mode external --interactive -- python3 "$worker" \
  "$(command -v agent-workflow)" openspec-upstream-smoke "$root/finish-result.json" > "$root/prepared.json"

agent-workflow --json agent-run bind-external openspec-upstream-smoke phase0-fixture worker > "$root/bound.json"
agent-workflow --json agent-run start-external openspec-upstream-smoke phase0-fixture worker \
  --generation 1 > "$root/started.json"
python - "$XDG_STATE_HOME" "$source_repo" <<'PYWORKER'
import json
import os
import pathlib
import subprocess
import sys

run = pathlib.Path(sys.argv[1]) / "agent-workflow/runs/openspec-upstream-smoke"
command = json.loads((run / "command.json").read_text())
subprocess.run(command["argv"], cwd=sys.argv[2], env=os.environ, check=True, timeout=60)
PYWORKER
agent-workflow --json agent-run external-exit openspec-upstream-smoke --generation 1 \
  --actor phase0-host --reason "Observed fixture process exit zero" > "$root/exited.json"
agent-workflow --json agent-run finalize openspec-upstream-smoke > "$root/finalized.json"
agent-workflow --json agent-run review openspec-upstream-smoke --actor phase0-host \
  --reason "Phase-0 compatibility smoke host review" > "$root/review.json"
agent-workflow --json agent-run accept openspec-upstream-smoke --actor phase0-host \
  --reason "Phase-0 compatibility smoke accepted" > "$root/accept.json"
agent-workflow --json agent-run summary openspec-upstream-smoke > "$root/summary.json"

python - "$root/prepared.json" "$XDG_STATE_HOME" "$root" "$source_repo" "$pack" "$source_revision" <<'PY'
import json
import hashlib
import pathlib
import sys

prepared = json.loads(pathlib.Path(sys.argv[1]).read_text())
root = pathlib.Path(sys.argv[3])
source = pathlib.Path(sys.argv[4])
pack = pathlib.Path(sys.argv[5])
source_revision = sys.argv[6]
run = pathlib.Path(sys.argv[2]) / "agent-workflow" / "runs" / "openspec-upstream-smoke"
binding = json.loads((run / "job-binding.json").read_text())
receipt = json.loads((run / "jobs" / "source-specification.json").read_text())
import_receipt = json.loads((pack / "source-specification.json").read_text())
job = json.loads((pack / "jobs" / "openspec-add-rate-limit-1-1.json").read_text())
finished = json.loads(pathlib.Path(root / "finish-result.json").read_text())
summary = json.loads(pathlib.Path(root / "summary.json").read_text())
assert prepared["status"] == "prepared"
assert prepared["worker_mode"] == "external"
assert binding["schema"] == "agent-workflow/job-binding/v2"
assert "bundle_provenance" not in binding
assert binding["scope"]["writable_trees"] == ["src"]
assert receipt["schema"] == "agent-workflow/source-specification-import/v1"
assert receipt["repository"]["dirty"] is False
assert receipt["repository"]["revision"] == source_revision
receipt_bytes = (run / "jobs" / "source-specification.json").read_bytes()
assert receipt_bytes == (pack / "source-specification.json").read_bytes()
assert hashlib.sha256(receipt_bytes).hexdigest() == job["source_specification"]["sha256"]
artifacts = {item["path"]: item["sha256"] for item in import_receipt["artifacts"]}
tasks_path = f"openspec/changes/add-rate-limit/tasks.md"
assert artifacts[tasks_path] == hashlib.sha256((source / tasks_path).read_bytes()).hexdigest()
task = import_receipt["task_map"][0]
source_line = "- [ ] 1.1 Add the limiter under src/ and verify the Python source compiles with `python3 -m compileall -q src`"
description = "1.1 Add the limiter under src/ and verify the Python source compiles with `python3 -m compileall -q src`"
assert task["source"]["text_sha256"] == hashlib.sha256((source_line + "\n").encode()).hexdigest()
assert task["description_sha256"] == hashlib.sha256(description.encode()).hexdigest()
assert finished["fast_path"] is True
assert finished["verification"][0]["id"] == "compile-src"
assert finished["verification"][0]["ok"] is True
assert finished["state"] == "finalized"
assert summary["execution"]["status"] == "completed"
assert summary["completion"]["result"] == "completed"
assert summary["review"]["state"] == "reviewed"
assert summary["acceptance"]["state"] == "accepted"
before = json.loads(pathlib.Path(root / "openspec-before.json").read_text())
after = {
    path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted((source / "openspec").rglob("*")) if path.is_file()
}
assert after == before
assert (source / "src" / "rate_limiter.py").is_file()
assert not pathlib.Path(root / "openspec-calls.log").read_text().strip()
from agent_workflow.receipts import verify_seal_details
sealed, digest = verify_seal_details(run)
assert len(digest) == 64
sealed_artifacts = {item["path"]: item["sha256"] for item in sealed["artifacts"]}
assert "jobs/source-specification.json" in sealed_artifacts
assert {"completion.json", "collections/completion.json"} <= set(sealed_artifacts)
assert "external-worker-exit.json" in sealed_artifacts
assert "process-result.json" not in sealed_artifacts
assert any(path.startswith("verification/") for path in sealed_artifacts)
assert sealed_artifacts["jobs/source-specification.json"] == hashlib.sha256(receipt_bytes).hexdigest()
completion = json.loads((run / "completion.json").read_text())
assert any(
    item["id"] == "source-compiles" and item["result"] == "pass"
    for item in completion["criteria"]
)
criterion = next(item for item in completion["criteria"] if item["id"] == "source-compiles")
assert any("acceptance-command:compile-src; ok=True" in item for item in criterion["evidence"])
PY

[[ -z "$(git -C "$source_repo" status --short --untracked-files=all)" ]]
[[ "$(git -C "$source_repo" diff "$source_revision"..HEAD --name-only)" == "src/rate_limiter.py" ]]

echo "OpenSpec 1.13.2 Phase-0 upstream compatibility smoke passed"
