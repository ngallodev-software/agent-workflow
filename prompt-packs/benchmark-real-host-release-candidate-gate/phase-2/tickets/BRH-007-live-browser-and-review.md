# BRH-007 — Preserved live browser and blinded review

**Task type:** review/evidence

For the Codex and Claude compact runs, prove both arm applications remain reachable after automated scoring/reporting and after at least 60 seconds idle. Inspect the applications in a real browser at required viewports and exercise search, status/risk filters, sorting, detail interaction, export content, keyboard navigation, visible focus, empty/invalid states, reduced-motion behavior, and console/page errors.

Verify generated visual/accessibility evidence corresponds to the live URLs. Prepare blinded reviewer assignments and confirm treatment names/mappings are absent. Complete the configured development reviewer minimum without exposing private mappings, submit reviews, regenerate reports, and verify the sealed runs.

Record reviewer independence, active review time, any blocking defects, and post-submission mapping-integrity checks.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
