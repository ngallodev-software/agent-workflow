# Phase 1 — preventative isolation and sensitive content

## Purpose

Implement the execution barrier and disclosure/retention controls in parallel on separate surfaces.

## Tickets

- `HARD-003`: depends on `HARD-008`.
- `HARD-006`: depends on `HARD-008`.

## Parallelism

Run HARD-003 and HARD-006 concurrently after HARD-008 is accepted.

Each ticket uses a separate worktree/session. Merge only after ticket evidence is reviewed, then rerun shared acceptance journeys before the next phase.
