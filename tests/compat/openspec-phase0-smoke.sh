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

if [[ -n "${OPENSPEC_SMOKE_EVIDENCE_DIR:-}" ]]; then
  mkdir -p "$OPENSPEC_SMOKE_EVIDENCE_DIR"
  root="$(mktemp -d "$OPENSPEC_SMOKE_EVIDENCE_DIR/run.XXXXXX")"
else
  root="$(mktemp -d)"
  trap 'rm -rf "$root"' EXIT
fi
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

- [x] 1.0 Preserve the existing source module
- [ ] 1.1 Add the limiter under src/ and verify the Python source compiles with `python3 -m compileall -q src`
- [ ] 1.2 Add a bounded response helper under src/ and verify the Python source compiles with `python3 -m compileall -q src`
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
    "writable_paths": ["src/rate_limiter.py", "src/rate_response.py"],
    "writable_trees": [],
    "disposable_trees": ["src/__pycache__"]
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

python - "$root/import.json" "$pack" "$root/pack-validation.json" "$source_repo" <<'PY'
import hashlib
import json
import pathlib
import sys

imported = json.loads(pathlib.Path(sys.argv[1]).read_text())
pack = pathlib.Path(sys.argv[2])
assert json.loads(pathlib.Path(sys.argv[3]).read_text())["ok"] is True
assert imported["provider"] == "openspec@1.13.2"
assert imported["legacy_specgen_required"] is False
assert imported["tasks"] == ["openspec-add-rate-limit-1-1", "openspec-add-rate-limit-1-2"]
jobs = [json.loads((pack / "jobs" / f"{task_id}.json").read_text()) for task_id in imported["tasks"]]
assert [job["source_specification"]["task_refs"] for job in jobs] == [[item] for item in imported["tasks"]]
assert jobs[0]["source_specification"]["sha256"] == jobs[1]["source_specification"]["sha256"]
assert jobs[0]["job_id"] != jobs[1]["job_id"]
assert {path.stem for path in (pack / "jobs").glob("*.json")} == set(imported["tasks"])
prompts = []
receipt = json.loads((pack / "source-specification.json").read_text())
source = pathlib.Path(sys.argv[4])
for task, job in zip(receipt["task_map"][1:], jobs):
    assert job["schema"] == "agent-workflow/native-job/v2"
    assert "bundle_provenance" not in job
    assert job["scope"] == {
        "writable_paths": ["src/rate_limiter.py", "src/rate_response.py"],
        "writable_trees": [], "disposable_trees": ["src/__pycache__"],
    }
    assert [command["id"] for command in job["acceptance_commands"]] == ["compile-src"]
    location = task["source"]
    line = (source / location["path"]).read_text().splitlines()[location["line"] - 1]
    assert line == "- [ ] " + task["description"]
    assert location["text_sha256"] == hashlib.sha256((line + "\n").encode()).hexdigest()
    assert task["description_sha256"] == hashlib.sha256(task["description"].encode()).hexdigest()
    prompt = (pack / job["prompt_path"]).read_text()
    assert task["description"] in prompt
    prompts.append(prompt)
assert prompts[0] != prompts[1]
PY

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
code = ("def response():\n    return 429\n" if sys.argv[4].endswith("rate_response.py")
        else "def allow(count, limit):\n    return count < limit\n")
Path(sys.argv[4]).write_text(code, encoding="utf-8")
subprocess.run(["git", "add", "--", sys.argv[4]], check=True)
subprocess.run(["git", "commit", "-m", "implement " + sys.argv[5]], check=True)
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
run_task() {
  local index="$1" task_id="$2" run_id="openspec-upstream-smoke-$1"
  local worktree="$root/worktree-$1" output="$3"
  git -C "$source_repo" worktree add --detach "$worktree" "$source_revision" >/dev/null
  agent-workflow --json agent-run prepare "$run_id" "$worktree" \
    "$pack/phase-0/tickets/$task_id.md" --pack "$pack" --job "jobs/$task_id.json" \
    --tier low --worker-mode external --interactive -- python3 "$worker" \
    "$(command -v agent-workflow)" "$run_id" "$root/finish-$1.json" "$output" "$task_id" \
    > "$root/prepared-$1.json"
  agent-workflow --json agent-run bind-external "$run_id" phase0-fixture worker > "$root/bound-$1.json"
  agent-workflow --json agent-run start-external "$run_id" phase0-fixture worker --generation 1 > "$root/started-$1.json"
  python - "$XDG_STATE_HOME" "$worktree" "$run_id" <<'PYWORKER'
import json
import os
import pathlib
import subprocess
import sys

run = pathlib.Path(sys.argv[1]) / "agent-workflow/runs" / sys.argv[3]
command = json.loads((run / "command.json").read_text())
subprocess.run(command["argv"], cwd=sys.argv[2], env=os.environ, check=True, timeout=60)
PYWORKER
  agent-workflow --json agent-run external-exit "$run_id" --generation 1 \
    --actor phase0-host --reason "Observed fixture process exit zero" > "$root/exited-$1.json"
  agent-workflow --json agent-run finalize "$run_id" > "$root/finalized-$1.json"
  agent-workflow --json agent-run review "$run_id" --actor phase0-host \
    --reason "Phase-0 compatibility smoke host review" > "$root/review-$1.json"
  agent-workflow --json agent-run accept "$run_id" --actor phase0-host \
    --reason "Phase-0 compatibility smoke accepted" > "$root/accept-$1.json"
  agent-workflow --json agent-run summary "$run_id" > "$root/summary-$1.json"
  [[ -z "$(git -C "$worktree" status --short --untracked-files=all)" ]]
  [[ "$(git -C "$worktree" diff "$source_revision"..HEAD --name-only)" == "$output" ]]
}

run_task 1 openspec-add-rate-limit-1-1 src/rate_limiter.py
python - "$XDG_STATE_HOME" "$root" <<'PYSEAL'
import pathlib
import shutil
import subprocess
import sys
from agent_workflow.receipts import verify_seal_details
run = pathlib.Path(sys.argv[1]) / "agent-workflow/runs/openspec-upstream-smoke-1"
_, digest = verify_seal_details(run)
assert len(digest) == 64
assert not (run.parent / "openspec-upstream-smoke-2").exists()
pathlib.Path(sys.argv[2], "task-a-seal.txt").write_text(digest)
root = pathlib.Path(sys.argv[2])
source = root / "source"
dirty = root / "dirty-worktree"
subprocess.run(["git", "-C", str(source), "worktree", "add", "--detach", str(dirty), "HEAD"],
               check=True, capture_output=True)
(dirty / "src/dirty.py").write_text("DIRTY = True\n")
task_id = "openspec-add-rate-limit-1-2"
for label, worktree, extra, reason in (
    ("wrong-ticket", source, ["--ticket", "openspec-add-rate-limit-1-1"], "--ticket disagrees with native job"),
    ("dirty-source", dirty, [], "source worktree must be clean"),
    ("advanced-source", root / "worktree-1", [], "revision does not match frozen OpenSpec import"),
):
    run_id = f"openspec-rejected-{label}"
    result = subprocess.run([
        shutil.which("agent-workflow"), "--json", "agent-run", "prepare", run_id,
        str(worktree), str(root / "pack/phase-0/tickets" / f"{task_id}.md"),
        "--pack", str(root / "pack"), "--job", f"jobs/{task_id}.json",
        *extra, "--tier", "low", "--worker-mode", "external", "--interactive", "--", "python3",
    ], text=True, capture_output=True)
    (root / f"{label}.stdout").write_text(result.stdout)
    (root / f"{label}.stderr").write_text(result.stderr)
    assert result.returncode == 2, result.stdout + result.stderr
    assert reason in result.stderr, result.stdout + result.stderr
    assert not (run.parent / run_id).exists()
PYSEAL
run_task 2 openspec-add-rate-limit-1-2 src/rate_response.py

python - "$XDG_STATE_HOME" "$root" "$source_repo" "$pack" "$source_revision" <<'PY'
import json
import hashlib
import pathlib
import subprocess
import sys

state = pathlib.Path(sys.argv[1])
root = pathlib.Path(sys.argv[2])
source = pathlib.Path(sys.argv[3])
pack = pathlib.Path(sys.argv[4])
source_revision = sys.argv[5]
import_receipt = json.loads((pack / "source-specification.json").read_text())
task_ids = ["openspec-add-rate-limit-1-1", "openspec-add-rate-limit-1-2"]
assert [item["agent_workflow_task_id"] for item in import_receipt["task_map"]] == [
    "openspec-add-rate-limit-1-0", *task_ids
]
assert [item["done_at_import"] for item in import_receipt["task_map"]] == [True, False, False]
jobs = [json.loads((pack / "jobs" / f"{task_id}.json").read_text()) for task_id in task_ids]
assert len({job["job_id"] for job in jobs}) == 2
assert [job["source_specification"]["task_refs"] for job in jobs] == [[item] for item in task_ids]
assert len({job["source_specification"]["sha256"] for job in jobs}) == 1
artifacts = {item["path"]: item["sha256"] for item in import_receipt["artifacts"]}
tasks_path = f"openspec/changes/add-rate-limit/tasks.md"
assert artifacts[tasks_path] == hashlib.sha256((source / tasks_path).read_bytes()).hexdigest()
task_map = {item["agent_workflow_task_id"]: item for item in import_receipt["task_map"]}
assert task_map[task_ids[0]]["source"]["text_sha256"] != task_map[task_ids[1]]["source"]["text_sha256"]
before = json.loads(pathlib.Path(root / "openspec-before.json").read_text())
after = {
    path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in sorted((source / "openspec").rglob("*")) if path.is_file()
}
assert after == before
digests = []
source_commits = []
from agent_workflow.receipts import verify_seal_details
for index, task_id in enumerate(task_ids, 1):
    run_id = f"openspec-upstream-smoke-{index}"
    run = state / "agent-workflow" / "runs" / run_id
    prepared = json.loads(pathlib.Path(root / f"prepared-{index}.json").read_text())
    binding = json.loads((run / "job-binding.json").read_text())
    receipt_bytes = (run / "jobs" / "source-specification.json").read_bytes()
    receipt = json.loads(receipt_bytes)
    job = jobs[index - 1]
    finish = json.loads(pathlib.Path(root / f"finish-{index}.json").read_text())
    summary = json.loads(pathlib.Path(root / f"summary-{index}.json").read_text())
    assert prepared["status"] == "prepared" and prepared["worker_mode"] == "external"
    assert binding["schema"] == "agent-workflow/job-binding/v2" and "bundle_provenance" not in binding
    assert binding["agent_run_id"] == run_id
    assert binding["job_id"] == binding["ticket_id"] == task_id
    assert binding["worktree"] == str(root / f"worktree-{index}")
    assert binding["source_specification"]["task_refs"] == [task_id]
    assert binding["scope"] == job["scope"]
    assert binding["scope"]["writable_trees"] == []
    assert receipt["schema"] == "agent-workflow/source-specification-import/v1"
    assert receipt["repository"]["dirty"] is False and receipt["repository"]["revision"] == source_revision
    assert receipt_bytes == (pack / "source-specification.json").read_bytes()
    assert hashlib.sha256(receipt_bytes).hexdigest() == job["source_specification"]["sha256"]
    assert finish["fast_path"] and finish["state"] == "finalized"
    assert finish["verification"][0]["id"] == "compile-src" and finish["verification"][0]["ok"]
    assert summary["execution"]["status"] == "completed" and summary["completion"]["result"] == "completed"
    assert summary["review"]["state"] == "reviewed" and summary["acceptance"]["state"] == "accepted"
    output = ["src/rate_limiter.py", "src/rate_response.py"][index - 1]
    assert (root / f"worktree-{index}" / output).is_file()
    source_commits.append(subprocess.run(
        ["git", "-C", str(root / f"worktree-{index}"), "rev-parse", "HEAD"],
        text=True, capture_output=True, check=True,
    ).stdout.strip())
    sealed, digest = verify_seal_details(run)
    assert sealed["agent_run_id"] == run_id
    digests.append(digest)
    sealed_artifacts = {item["path"]: item["sha256"] for item in sealed["artifacts"]}
    assert "jobs/source-specification.json" in sealed_artifacts
    assert {"completion.json", "collections/completion.json"} <= set(sealed_artifacts)
    assert "external-worker-exit.json" in sealed_artifacts and "process-result.json" not in sealed_artifacts
    assert any(path.startswith("verification/") for path in sealed_artifacts)
    assert sealed_artifacts["jobs/source-specification.json"] == hashlib.sha256(receipt_bytes).hexdigest()
    completion = json.loads((run / "completion.json").read_text())
    assert completion["agent_run_id"] == run_id and completion["ticket_id"] == task_id
    assert completion["base_revision"] == source_revision
    assert completion["head_revision"] == source_commits[-1] != source_revision
    assert completion["changed_files"] == [output]
    criterion = next(item for item in completion["criteria"] if item["id"] == "source-compiles")
    assert criterion["result"] == "pass"
    assert any("acceptance-command:compile-src; ok=True" in item for item in criterion["evidence"])
assert digests[0] != digests[1]
assert source_commits[0] != source_commits[1]
assert digests[0] == pathlib.Path(root / "task-a-seal.txt").read_text()
assert not pathlib.Path(root / "openspec-calls.log").read_text().strip()
PY

[[ -z "$(git -C "$source_repo" status --short --untracked-files=all)" ]]
[[ "$(git -C "$source_repo" rev-parse HEAD)" == "$source_revision" ]]
[[ -z "$(git -C "$source_repo" diff "$source_revision"..HEAD --name-only)" ]]

echo "OpenSpec 1.13.2 Phase-0 upstream compatibility smoke passed (two independently accepted jobs)"
[[ -z "${OPENSPEC_SMOKE_EVIDENCE_DIR:-}" ]] || echo "Evidence preserved: $root"
