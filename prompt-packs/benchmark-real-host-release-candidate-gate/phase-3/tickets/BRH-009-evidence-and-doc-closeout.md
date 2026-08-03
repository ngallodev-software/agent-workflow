# BRH-009 — Evidence, documentation, and closeout

**Task type:** review/evidence

Reconcile README, benchmark operations/implementation/spec, command reference, man page, correction backlog, canonical backlog, prompt-pack status, and final evidence. If real-host execution revealed a defect and repair, ensure tests/docs/source-package mirrors describe the corrected behavior.

Complete `handoff-evidence/eval-results.json`, hash every referenced evidence file, run the evaluator, and create a complete source/evidence archive with manifest and checksum. No check may be marked pass without referenced evidence.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
