# Phase 1 Master Implementation Prompt

## Role

Coordinate three parallel, non-destructive operator-interface tickets.

## Objective

Implement the cache/status renderer, popup/focus/preview, and opt-in integration surfaces without lifecycle mutation or managed-layout changes.


## Source-of-truth hierarchy

Use current source first, then accepted tests/schemas/decisions, then the canonical backlog, then pack references. Complete exact-worktree preflight before structural discovery or editing.

## Execution rules

1. Create one clean worktree per writable ticket.
2. Launch every delegation in a new named terminal session.
3. Record source baseline and prompt digest.
4. Enforce manifest dependencies and writable paths.
5. Inspect stalled sessions in the foreground before interruption.
6. Keep implementation and independent gate review separate.
7. Preserve all command output and exact exit codes.
8. Do not copy prior-art source without approved license provenance.

## Test policy

Prefer installed-product journeys for public behavior and compact invariants for ranking, sanitization, cache safety, and pane identity. Existing pane-identity journeys must continue to pass after every phase.

## Completion

Require strict completion handoff and `completion.json`, run `agent-workflow agent task-complete` exactly once, and let the runner collect and seal the run. Review writable scope, receipts, tests, docs, package data, and lifecycle records before integration.
