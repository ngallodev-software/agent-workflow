# BRH-001 — Source and package baseline

**Task type:** review/evidence

Validate archive checksum and inventory, record Python/OS/tool versions, establish a clean Git baseline if needed, install the candidate into an isolated environment outside the checkout, and prove source/package benchmark suite parity.

Run compilation, all invariant tests, release distribution/documentation/installer tests, release-asset audit, pack validation, evaluator self-test, built-in suite export, and exact source/export inventory comparison.

Reject unexpected source drift, package mirror mismatch, failing invariant/release gate, invalid prompt pack, or an installed command resolving to the source checkout when an outside installation is required.

Deliver baseline command transcripts, package metadata, source/archive hashes, test reports, and a task result.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
