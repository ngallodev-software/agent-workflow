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
source_repo="$root/source"
pack="$root/pack"
policy="$root/job-policy.json"
mkdir -p "$source_repo/src"

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

agent-workflow --json pack import-openspec   "$source_repo" add-rate-limit "$pack" --job-policy "$policy"   > "$root/import.json"

agent-workflow --json pack validate "$pack" --verify-checksums   > "$root/pack-validation.json"

python - "$root/import.json" "$pack" <<'PY'
import json
import pathlib
import sys

imported = json.loads(pathlib.Path(sys.argv[1]).read_text())
pack = pathlib.Path(sys.argv[2])
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

export XDG_STATE_HOME="$root/state"
export XDG_DATA_HOME="$root/data"
export XDG_CACHE_HOME="$root/cache"
export XDG_CONFIG_HOME="$root/config"

prompt="$pack/phase-0/tickets/openspec-add-rate-limit-1-1.md"
agent-workflow --json agent-run prepare   openspec-upstream-smoke "$source_repo" "$prompt"   --pack "$pack"   --job jobs/openspec-add-rate-limit-1-1.json   --worker-mode external --interactive -- /bin/true   > "$root/prepared.json"

python - "$root/prepared.json" "$XDG_STATE_HOME" <<'PY'
import json
import pathlib
import sys

prepared = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert prepared["status"] == "prepared"
run = pathlib.Path(sys.argv[2]) / "agent-workflow" / "runs" / "openspec-upstream-smoke"
binding = json.loads((run / "job-binding.json").read_text())
assert binding["schema"] == "agent-workflow/job-binding/v2"
assert "bundle_provenance" not in binding
assert binding["scope"]["writable_trees"] == ["src"]
assert (run / "jobs" / "source-specification.json").is_file()
PY

echo "OpenSpec 1.13.2 Phase-0 upstream compatibility smoke passed"
