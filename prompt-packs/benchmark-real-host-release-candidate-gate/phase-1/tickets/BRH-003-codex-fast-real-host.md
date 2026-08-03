# BRH-003 — Codex compact real-host run

**Task type:** review/evidence

Execute one fresh `priority-picker-fast-v1` development-policy run with `codex-subscription.json` and no `OPENAI_API_KEY`.

Capture before/during/after tmux evidence. Prove exactly two new panes in the invoking window, no detached benchmark session, stable arm pane IDs, visible changing output in both panes, valid provider usage evidence, each model phase at or below 150 seconds, paired model critical path below 180 seconds, and terminal `awaiting_human_review` with two ready live applications.

Do not perform human review or destructive cleanup in this ticket. Preserve the apps, panes, worktrees, and run evidence for BRH-007/008.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
