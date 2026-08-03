# BRH-GATE-1 — Fast provider gate

**Task type:** gate

Independently inspect the Codex and Claude compact run evidence. Confirm the measurements come from sealed benchmark metrics, not manually estimated timing. Sample pane-monitor captures to prove in-run output changes and compare tmux snapshots to prove exactly two same-window panes and no extra sessions.

Accept only if both subscription providers pass every compact-run requirement. Missing provider access is a block, not a waiver.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
