# Command matrix

Commands assume the repository root, an activated virtual environment, and a real tmux pane.

## Install and local validation

```bash
python -m pip install -e '.[dev,benchmark-visual]'
python -m playwright install chromium
python -m compileall -q src
pytest -q tests/invariants
pytest -q tests/release/test_distribution.py tests/release/test_documentation_sync.py tests/release/test_release_installers.py
python scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/benchmark-real-host-release-candidate-gate
python prompt-packs/benchmark-real-host-release-candidate-gate/evals/evaluate_handoff.py --self-test
```

## Export fast suite

```bash
rm -rf /tmp/aw-fast-suite
agent-workflow benchmark suite-export /tmp/aw-fast-suite --benchmark-id priority-picker-fast-v1
```

## Codex subscription preflight

```bash
unset OPENAI_API_KEY
codex login status
agent-workflow benchmark auth-check /tmp/aw-fast-suite/executors/codex-subscription.json
agent-workflow benchmark readiness /tmp/aw-fast-suite/benchmark-spec.json \
  --executor /tmp/aw-fast-suite/executors/codex-subscription.json \
  --policy /tmp/aw-fast-suite/policies/development.json
```

## Claude subscription preflight

```bash
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN
claude auth status
agent-workflow benchmark auth-check /tmp/aw-fast-suite/executors/claude-subscription.json
agent-workflow benchmark readiness /tmp/aw-fast-suite/benchmark-spec.json \
  --executor /tmp/aw-fast-suite/executors/claude-subscription.json \
  --policy /tmp/aw-fast-suite/policies/development.json
```

## Create and plan a run

```bash
agent-workflow benchmark fixture-create /tmp/aw-fast-suite/benchmark-spec.json /tmp/aw-fast-fixture-<provider>
agent-workflow benchmark plan /tmp/aw-fast-suite/benchmark-spec.json \
  --executor /tmp/aw-fast-suite/executors/<provider>-subscription.json \
  --policy /tmp/aw-fast-suite/policies/development.json \
  --repo /tmp/aw-fast-fixture-<provider> \
  --run-id <run-id>
```

The `plan` command prints the run-plan path. Record it as `PLAN`.

## Monitor and execute

```bash
EVIDENCE=handoff-evidence/runs/<run-id>
mkdir -p "$EVIDENCE"
python prompt-packs/benchmark-real-host-release-candidate-gate/scripts/capture_tmux_snapshot.py \
  --output "$EVIDENCE/tmux-before.json"
python prompt-packs/benchmark-real-host-release-candidate-gate/scripts/monitor_benchmark_panes.py \
  --plan "$PLAN" --output-dir "$EVIDENCE/pane-monitor" &
MONITOR_PID=$!
agent-workflow benchmark run "$PLAN" | tee "$EVIDENCE/run-command.txt"
wait "$MONITOR_PID"
python prompt-packs/benchmark-real-host-release-candidate-gate/scripts/capture_tmux_snapshot.py \
  --output "$EVIDENCE/tmux-after.json"
agent-workflow benchmark status "$PLAN" | tee "$EVIDENCE/status.json"
agent-workflow benchmark verify "$PLAN" | tee "$EVIDENCE/verify.json"
```

## Human review

```bash
agent-workflow benchmark review "$PLAN" --reviewer reviewer-01 | tee "$EVIDENCE/review-assignment.json"
# Complete the generated review template without viewing the private mapping.
agent-workflow benchmark review "$PLAN" --reviewer reviewer-01 --input completed-review.json
agent-workflow benchmark report "$PLAN"
agent-workflow benchmark verify "$PLAN"
```

## Lifecycle and cleanup

```bash
agent-workflow benchmark cleanup "$PLAN" | tee "$EVIDENCE/cleanup-preserve.json"
agent-workflow benchmark live-stop "$PLAN" | tee "$EVIDENCE/live-stop.json"
agent-workflow benchmark live-start "$PLAN" | tee "$EVIDENCE/live-restart.json"
agent-workflow benchmark cleanup "$PLAN" --stop-live-apps --remove-worktrees \
  | tee "$EVIDENCE/cleanup-destructive.json"
agent-workflow benchmark verify "$PLAN" | tee "$EVIDENCE/verify-after-cleanup.json"
```
