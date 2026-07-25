# P3-00 — workflow baseline and MCP contract refresh

## Goal

Prove that `WF-22` is complete and identify the exact stable services and typed
contracts MCP can reuse for workflow validation, launch, status, resume, routing
explanation, approvals, and aggregate receipt inspection.

## Writable paths

- `docs/MCP_SERVER_DECISION.md`
- `docs/MCP_SERVER_IMPLEMENTATION_REPORT.md`
- `src/agent_workflow/mcp/**`
- `tests/test_mcp_*.py`
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

- `WF-22` completion evidence is cited.
- Every retained tool has one authoritative service mapping.
- No tool maps to tmux, shell strings, raw files, or mutable receipt internals.
- Focused contract tests pass.

## Stop conditions

Stop if workflow services are incomplete, unstable, or usable only through CLI
argument parsing. Return the missing seam as a backlog item; do not duplicate it
inside MCP.
