# Phase 1 — public-preview decision gate

## Purpose

Integrate all lanes and issue an explicit go/no-go decision; no new runtime features.

## Tickets

- `REL-004`: depends on `HARD-007`, `HARD-009`, `HARD-010`, `REL-003`.

## Parallelism

No parallel implementation. REL-004 is an independent release gate and may only make narrow release-blocking fixes.

Each ticket uses a separate worktree/session. Merge only after ticket evidence is reviewed, then rerun shared acceptance journeys before the next phase.
