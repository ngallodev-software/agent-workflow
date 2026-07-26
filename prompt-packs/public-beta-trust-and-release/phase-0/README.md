# Phase 0 — trust, drift, supply chain, and compatibility

## Purpose

Run four independent public-beta preparation lanes after the technical hardening foundations are accepted.

## Tickets

- `HARD-007`: no incoming dependency; may run concurrently with other dependency-free tickets.
- `HARD-009`: no incoming dependency; may run concurrently with other dependency-free tickets.
- `HARD-010`: no incoming dependency; may run concurrently with other dependency-free tickets.
- `REL-003`: no incoming dependency; may run concurrently with other dependency-free tickets.

## Parallelism

Run HARD-007, HARD-009, HARD-010, and REL-003 concurrently in separate worktrees/environments.

Each ticket uses a separate worktree/session. Merge only after ticket evidence is reviewed, then rerun shared acceptance journeys before the next phase.
