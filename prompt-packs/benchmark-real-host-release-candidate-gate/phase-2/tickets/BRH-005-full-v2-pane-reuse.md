# BRH-005 — Full v2 multi-phase pane reuse

**Task type:** review/evidence

Run one fresh development-policy `priority-picker-v2` benchmark using an authenticated subscription executor. Monitor pane bindings through all three model phases.

Prove the same two pane IDs remain bound to `control_raw` and `workflow_full` across every phase, no third arm pane or detached session appears, provider output remains visible, and the automated pipeline reaches preserved live review.

This ticket validates multi-phase topology; it does not need to meet the compact suite's three-minute target.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
