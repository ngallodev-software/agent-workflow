# Phase 0 — config and executor trust

## Purpose

Make runtime policy and executable identity explicit before applying a sandbox.

## Tickets

- `HARD-008`: no incoming dependency; may run concurrently with other dependency-free tickets.

## Parallelism

One implementation ticket; do not overlap its config/process policy changes with later sandbox work.

Each ticket uses a separate worktree/session. Merge only after ticket evidence is reviewed, then rerun shared acceptance journeys before the next phase.
