# MCP3-01 — workflow-aware safe mutation tools

> **Execution prerequisite:** Do not execute this ticket until `HARD-004`, `HARD-005`, and `HARD-007` are accepted and integrated. `MCP-003` is the only backlog item owned by this pack.

## Goal

Add the minimal remaining stdio MCP mutation tools by wrapping authoritative
services shared with the CLI.

## Required surface

- `pack_validate`
- `worktree_create`
- single-run `launch`
- workflow `validate`, `launch`, `status`, and `resume`
- `progress`, `ack`, and `steer`

A tool may be omitted when MCP3-00 proves its service contract is not ready.

## Safety and evidence requirements

- Structured arguments only; no raw command or shell string.
- Configured repository, pack, worktree, and state roots only.
- Caller idempotency keys for mutating operations.
- Durable action/result identifiers returned from authoritative records.
- Workflow launch invokes the workflow scheduler, whose child nodes invoke the
  existing launch service.
- Routing explanations are observational; policy enforcement remains server-side.
- Workflow status exposes allowlisted summaries and receipt references, not raw
  state files or child terminal capture.
- Steering returns `pending` until correlated acknowledgement proves a stronger
  state.

## Writable paths

- `src/agent_workflow/mcp/**`
- shared service modules only when both CLI and MCP use the seam
- installed-product MCP journeys and narrowly scoped invariant matrices
- command/reference documentation and release manifest

## Acceptance evidence

- CLI/service and MCP parity tests cover every tool.
- Duplicate idempotency keys replay the original result; mismatched reuse fails.
- Restart tests prove committed actions remain discoverable.
- Traversal, symlink, oversized input/output, invalid transition, and policy
  denial tests pass.
- No destructive, HTTP, raw terminal, arbitrary file, or force-kill surface.

## Stop conditions

Stop rather than implement a tool when its authoritative service is absent, its
idempotency contract is undefined, or its durable evidence cannot be correlated.
Do not compensate with direct file mutation, subprocess calls, or MCP-local state.
