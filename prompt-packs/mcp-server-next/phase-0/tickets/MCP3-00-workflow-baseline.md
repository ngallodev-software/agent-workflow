# MCP3-00 — workflow baseline and MCP contract refresh

> **Execution prerequisite:** Do not execute this ticket until `HARD-004`, `HARD-005`, and `HARD-007` are accepted and integrated. `MCP-003` is the only backlog item owned by this pack.

## Goal

Identify the exact stable services and typed contracts MCP can reuse for workflow validation, launch, status, resume, routing
explanation, approvals, and aggregate receipt inspection.

## Writable paths

- `docs/MCP_SERVER.md`
- `src/agent_workflow/mcp/**`
- `tests/acceptance/**`
- `tests/invariants/**`
- `tests/future/**`
- this prompt pack

Do not change workflow semantics in this ticket.

## Required work

- Run workflow-focused tests and prompt-pack validation.
- Map each proposed MCP operation to one existing CLI/domain service.
- Remove any proposed tool that would require direct state-file access or a
  second scheduling/routing implementation.
- Define bounded typed requests/results and stable error mappings.
- Record the prerequisite workflow schema and service versions/digests.

## Acceptance evidence

- Every retained tool has one authoritative service mapping.
- No tool maps to tmux, shell strings, raw files, or mutable receipt internals.
- Installed-product parity journeys and any required security/idempotency matrices pass.

## Stop conditions

Stop if workflow services are incomplete, unstable, or usable only through CLI
argument parsing. Return the missing seam as a backlog item; do not duplicate it
inside MCP.
