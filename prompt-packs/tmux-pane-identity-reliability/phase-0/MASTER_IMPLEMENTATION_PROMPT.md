# Phase 0 Master Implementation Prompt

## Role

Act as the phase coordinator. Execute or delegate only the tickets listed by `task-manifest.yaml`.

## Objective

Implement `PROC-006`: remove mutable shared-window pane positions from the
tmux identity/control path. The fix must be narrow, backwards-aware, and
evidence-first.

## Source-of-truth hierarchy

Use current source first, then current tests/schemas, then verified references, then documentation and historical plans.

Before structural discovery or editing, complete the exact-worktree
`WORKTREE_PREFLIGHT.md` procedure and generate a full codebase-memory index for
that worktree. Record its project identity and node/edge counts in the handoff.

## Execution rules

1. Create one clean worktree per writable ticket.
2. Launch every delegation in a new named terminal session.
3. Record source baseline and prompt hash.
4. Enforce dependencies and writable paths.
5. Inspect stalled sessions in the foreground before interruption.
6. Do not merge implementation and independent phase review into the same unchecked delegation.
7. Start implementation tickets interactively. Exploration/review tickets are non-interactive by default; at pane capacity, require an explicit close-idle, structured non-interactive, or cancel decision.

## Test policy

Add only tests required by explicit acceptance criteria or a demonstrated regression boundary. Prefer one semantic assertion over broad snapshots or repeated CLI help coverage.

## Completion

Require the strict completion handoff and `completion.json`, run
`agent-workflow agent task-complete` exactly once, exit the interactive executor
cleanly, and let the runner collect and seal the run. The reviewer must inspect
the sealed completion/final receipt, writable scope, tests, and lifecycle
records before accepting the ticket.
