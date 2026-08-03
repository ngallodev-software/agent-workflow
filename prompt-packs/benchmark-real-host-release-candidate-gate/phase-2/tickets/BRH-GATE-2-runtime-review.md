# BRH-GATE-2 — Runtime, cancellation, browser, and review gate

**Task type:** gate

Independently inspect BRH-005 through BRH-007. Sample raw process snapshots, pane captures, HTTP probes, browser evidence, assignments, submitted reviews, reports, and manifests. The reviewer must not rely on implementation-author summaries.

Reject static-only tmux proof, final-only output, unreachable live URLs, treatment leakage, missing visual evidence, surviving canceled processes, or unverified reports.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
