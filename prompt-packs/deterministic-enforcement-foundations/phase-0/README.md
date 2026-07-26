# Phase 0 — bounded execution and artifact integrity

## Purpose

Build the two independent foundations that every later security control depends on.

## Tickets

- `HARD-001`: no incoming dependency; may run concurrently with other dependency-free tickets.
- `HARD-002`: no incoming dependency; may run concurrently with other dependency-free tickets.

## Parallelism

Run HARD-001 and HARD-002 concurrently. Their primary writable surfaces are process execution versus pack/path/schema integrity.

Each ticket uses a separate worktree/session. Merge only after ticket evidence is reviewed, then rerun shared acceptance journeys before the next phase.
