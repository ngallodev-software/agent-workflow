# MAINT-003 — terminal completion inbox reconciliation

## Goal

Align the orchestrator registry/inbox installed journeys with terminal-by-default
task completion while preserving explicit `--keep-alive` reuse semantics.

## Defect

The installed inbox journeys still require a completed child to be
`idle_reusable` and require a first replay advance, contradicting MAINT-003's
accepted terminal default (`closed`). They fail with missing current
`idle_reusable` assignment evidence and `advanced == 0`.

## Required behavior

- Completed terminal children remain valid immutable sources for registry/inbox
  import and one bounded replay; importing them must not require a reusable
  assignment.
- Explicit `--keep-alive` remains the only route to `idle_reusable` reuse.
- Cursor/replay accounting must reflect durable unseen terminal evidence once,
  then remain idempotent.
- Add installed positive terminal and keep-alive journeys plus negative stale or
  missing assignment evidence coverage.

## Writable paths

Registry/inbox reconciliation and cursor code, focused tests/fixtures, and
directly related protocol documentation only.

## Acceptance evidence

- The installed inbox journey proves terminal completion imports and replays
  exactly once without an `idle_reusable` state.
- The installed keep-alive journey proves explicit reuse remains
  `idle_reusable`.
- Invariants reject missing sealed-receipt and stale assignment evidence.
- Pack validation and release-drift audit pass from the source checkout.

## Stop conditions

Do not restore implicit reuse, accept mutable status in place of durable
completion evidence, or weaken receipt/cursor idempotency checks.
