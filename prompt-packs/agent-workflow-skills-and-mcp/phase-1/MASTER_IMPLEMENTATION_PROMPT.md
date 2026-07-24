# Phase 1 Master Research Prompt

## Role

Act as the research coordinator. Execute only the read-only research ticket in
`task-manifest.yaml`; no MCP implementation is authorized in this phase.

## Objective

Make a decision-quality recommendation for whether and how `agent-workflow`
should expose an MCP server surface. Use primary sources and distinguish facts,
inferences, and recommendations.

## Source-of-truth hierarchy

Use current source first, then current tests/schemas, then verified references, then documentation and historical plans.

## Execution rules

1. Work read-only in a clean source view; create a worktree only if the
   operator wants the memo committed separately.
2. Use `agent-workflow launch` only if a durable research run is desired; no
   raw tmux lifecycle commands.
3. Record source baseline and prompt hash.
4. Enforce dependencies and writable paths.
5. Inspect stalled sessions in the foreground before interruption.
6. Do not merge implementation and independent phase review into the same unchecked delegation.

## Test policy

Add only tests required by explicit acceptance criteria or a demonstrated regression boundary. Prefer one semantic assertion over broad snapshots or repeated CLI help coverage.

## Completion

Require a cited memo and a decision review. Do not add dependencies or runtime
MCP code based on this phase alone.
