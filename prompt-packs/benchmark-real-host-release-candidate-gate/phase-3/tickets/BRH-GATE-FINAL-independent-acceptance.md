# BRH-GATE-FINAL — Independent release-candidate acceptance

**Task type:** gate

Use `templates/FINAL_GATE_REPORT.md`. Verify archive/source hashes, rerun the smallest deterministic local gate, sample evidence from every evaluation domain, inspect any repair diff, confirm evaluator output is 100/100 with every required check passing, and verify no critical/high defect remains.

Decision must be exactly one of `accept`, `reject`, or `blocked`. Do not implement changes in this gate worktree. Publication readiness must be assessed separately unless a content-addressed publication runtime and required reviewer/repetition policy were actually used.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
