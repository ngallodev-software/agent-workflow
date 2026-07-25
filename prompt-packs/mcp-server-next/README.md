# mcp-server-next

## Purpose

Implement only the next authorized MCP mutation phase. The read-only local stdio adapter and shared read services already exist. This pack adds no new orchestrator and must wrap the same application services used by the CLI.

## Scope

The single phase covers:

1. service and contract baseline verification;
2. bounded idempotent mutation tools;
3. independent security and parity review.

The allowed tool candidates are pack validation, worktree creation, one bounded run launch, workflow validate/start/status/resume, and durable progress/ack/steer. A candidate must be omitted when its shared service, idempotency contract, or durable evidence mapping is not ready.

## Non-targets

No HTTP, MCP Tasks as lifecycle authority, arbitrary shell or paths, direct tmux controls, raw terminal capture, force kill, direct state-file mutation, alternate routing/scheduling, memory infrastructure, federation, or persona catalogs.

## Execution

Start with `phase-0/tickets/MCP3-00-workflow-baseline.md`. Read current source, `BACKLOG.md`, `docs/ARCHITECTURE.md`, `docs/MCP_SERVER.md`, `docs/OPERATIONS.md`, and `docs/TESTING.md`. Validate this pack before delegation:

```bash
agent-workflow pack validate prompt-packs/mcp-server-next
```
