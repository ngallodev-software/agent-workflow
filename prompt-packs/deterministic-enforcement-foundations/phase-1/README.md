# Phase 1 — immutable authority and MCP read boundary

## Purpose

Use the phase-0 controls to eliminate projection authority and close the current read-only MCP disclosure/path gaps.

## Tickets

- `HARD-004`: depends on `HARD-001`, `HARD-002`.
- `HARD-005`: depends on `HARD-002`.

## Parallelism

Run HARD-004 and HARD-005 concurrently after their declared dependencies are accepted.

Each ticket uses a separate worktree/session. Merge only after ticket evidence is reviewed, then rerun shared acceptance journeys before the next phase.
