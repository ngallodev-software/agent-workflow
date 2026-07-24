# Agent-workflow skill integration and MCP decision

## Purpose

Fix P0 BKL-006 so agents can discover and operate `agent-workflow`, then
perform a separate, evidence-backed MCP-server decision study. Phase 0 is the
only code phase. Phase 1 is research only and must not add MCP runtime code.

## Source baseline

`/lump/apps/agent-workflow`, `master`, release `0.1.6`, reviewed 2026-07-23.
The checkout and supplied source archive are authoritative when they differ
from a historical reference.

## Phase map

| Phase | Objective | Complexity | Exit dependency |
|---|---|---|---|
| 0 | P0 skill/CLI/runbook integration | Medium | Current skill and installer behavior. |
| 1 | MCP SDK/framework/client research and decision | Medium | Phase 0 evidence plus primary sources. |

## Universal delegation rules

- Execute every ticket in a fresh named terminal session.
- Use an isolated worktree unless the ticket is explicitly read-only.
- Read required references and current source before editing.
- Follow writable-path restrictions.
- Do not add tests without naming the contract or failure they protect.
- Stop when source contradicts the ticket in a way that could overwrite newer architecture.
- Produce a ticket completion report and preserve all command output.
- Do not treat a host-native subagent as an `agent-workflow` run unless an
  explicit bridge invokes the CLI and records receipts.
- Use `agent-workflow launch` rather than raw tmux commands. A valid current
  tmux context creates a visible pane; otherwise the CLI creates a detached
  named session.

## How to execute

See `EXECUTION_PROTOCOL.md`, `DELEGATION_RUNBOOK.md`, and each phase README.
Start with Phase 0. Phase 1 produces only the decision artifact specified by
its ticket; do not implement MCP based on unreviewed research.
