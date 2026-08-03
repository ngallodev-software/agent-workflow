# BRH-008 — Lifecycle restart and cleanup safety

**Task type:** review/evidence

Using preserved compact runs, prove default cleanup leaves apps/worktrees intact. Stop and restart live applications, verify both readiness URLs and blinded label mappings, and record whether ports/URLs remain stable or are truthfully refreshed.

Then run explicit cleanup with `--stop-live-apps --remove-worktrees`. Prove all live processes are gone before worktree removal, only run-owned panes are closed, arm worktrees/branches are removed, coordinator/run evidence remains, and `benchmark verify` still passes. Repeat stop/cleanup to prove idempotent truthful results.

A teardown failure must preserve panes/worktrees and fail closed; do not force-remove evidence to pass this gate.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
