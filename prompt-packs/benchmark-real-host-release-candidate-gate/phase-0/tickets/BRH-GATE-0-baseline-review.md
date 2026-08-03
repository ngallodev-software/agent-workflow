# BRH-GATE-0 — Independent baseline gate

**Task type:** gate

Independently inspect BRH-001 and BRH-002 evidence. Rerun pack validation, evaluator self-test, one source/package parity check, and both read-only provider readiness commands. Do not implement repairs.

Accept only when the source/package baseline is clean and the host is genuinely ready for both subscription providers. Otherwise reject or block with the exact prerequisite.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
