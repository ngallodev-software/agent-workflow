# BRH-006 — Real-provider cancellation and no-orphan gate

**Task type:** review/evidence

Use a disposable compact run. During active provider work, capture the target pane helper PID, PGID, and complete descendant set. Terminate or replace the owned pane helper through tmux. Capture process state until every pre-intervention PID is gone.

Verify the coordinator classifies the interrupted attempt as infrastructure failure, preserves evidence, and permits only the configured fresh paired retry. Prove the retry uses new worktrees/process identities and does not overlap the old provider process.

Reject if any old descendant remains, task failure is misclassified as infrastructure, the same worktrees are reused, or evidence is missing. Preserve the entire failed and retry lineage.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
