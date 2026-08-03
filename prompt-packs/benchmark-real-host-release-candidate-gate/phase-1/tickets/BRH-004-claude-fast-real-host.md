# BRH-004 — Claude compact real-host run

**Task type:** review/evidence

Execute one fresh `priority-picker-fast-v1` development-policy run with `claude-subscription.json` and no `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN`.

Apply the same topology, visibility, timing, usage, run-state, and preservation checks as BRH-003. Record the Claude executor/model/authentication identity separately. Never pool or compare this run as though it were the Codex cohort.

Preserve apps, panes, worktrees, and run evidence for later review and cleanup.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
