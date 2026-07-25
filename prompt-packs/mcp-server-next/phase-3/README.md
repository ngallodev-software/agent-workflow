# Phase 3 — workflow-aware safe mutation adapter

## Objective

Add the remaining local-stdio mutation tools only after `workflow-foundations-next`
finishes through `WF-22`. MCP remains a thin adapter over stable CLI/domain
services; it does not own scheduling, workflow state, tmux, worktrees, routing,
or receipts.

## Required external prerequisite

- Canonical backlog task `WF-22` is complete.
- Workflow validate/launch/status/resume services and aggregate receipts exist.
- Existing single-run launch/control services remain authoritative.

## Tickets

1. `P3-00` — verify the workflow foundation and refresh MCP contracts.
2. `P3-01` — implement bounded workflow-aware and single-run mutation tools.
3. `P3-02` — independently review security, idempotency, evidence, and host behavior.

## Non-targets

No arbitrary workflow definition execution, raw shell or tmux control, direct
state-file mutation, bulk cross-run operations, force kill, HTTP transport,
MCP Tasks as lifecycle authority, or duplicated routing/scheduling logic.
