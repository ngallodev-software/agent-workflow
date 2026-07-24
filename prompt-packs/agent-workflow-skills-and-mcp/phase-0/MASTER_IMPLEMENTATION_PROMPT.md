# Phase 0 Master Implementation Prompt

## Role

Act as the phase coordinator. Execute or delegate only the tickets listed by
`task-manifest.yaml`. Complete preflight before P0-01.

## Objective

Make `agent-workflow` discoverable and operational to supported agents without
claiming that a host-native subagent is automatically a durable workflow run.

## Source-of-truth hierarchy

Use current source first, then current tests/schemas, then verified references, then documentation and historical plans.

## Execution rules

1. Create one clean worktree per writable ticket.
2. Launch qualifying delegations through `agent-workflow launch`; do not call
   raw tmux lifecycle commands. When the coordinator is in tmux, inspect the
   resulting visible pane; otherwise inspect the detached named session.
3. Record source baseline and prompt hash.
4. Enforce dependencies and writable paths.
5. Inspect stalled sessions in the foreground before interruption.
6. Do not merge implementation and independent phase review into the same unchecked delegation.

## Test policy

Add only tests required by explicit acceptance criteria or a demonstrated regression boundary. Prefer one semantic assertion over broad snapshots or repeated CLI help coverage.

## Completion

Require ticket completion reports, independently rerun phase gates, and
produce `PHASE_GATE_REPORT.md`. Do not begin Phase 1 implementation: it is a
research and decision artifact only.
