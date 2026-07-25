# mcp-server-next

## Purpose

Maintain the optional local-stdio MCP adapter without creating a second
orchestrator. Phases 0 through 2 cover the completed research, shared read
services, and bounded read-only server. Phase 3 is the remaining safe mutation
surface and is intentionally blocked until the complete workflow foundation
prompt pack finishes through canonical backlog task `WF-22`.

The workflow foundation is implemented first because MCP must wrap stable
workflow, routing, lifecycle, approval, and receipt services. It must not invent
parallel state machines or reinterpret workflow files itself.

## Source baseline

The companion source archive is a filtered snapshot of the `agent-workflow`
checkout prepared 2026-07-24 at release 0.1.8. Current extracted source remains
authoritative when it differs from this pack.

## Phase map

| Phase | Objective | State | Exit dependency |
|---|---|---|---|
| 0 | Research refresh, architecture review, and executable planning | completed | Accepted source baseline and primary-source evidence |
| 1 | Reusable domain seams and typed read contracts | completed | Phase 0 accepted |
| 2 | Local stdio read-only resource/server implementation and conformance | completed | Phase 1 accepted |
| 3 | Workflow-aware safe mutation adapter | blocked | `workflow-foundations-next` through `WF-22`, then Phase 2 accepted |

## Universal delegation rules

- Execute every ticket in a fresh named terminal session.
- Use an isolated worktree unless the ticket is explicitly read-only.
- Read required references and current source before editing.
- Follow writable-path restrictions.
- Do not add tests without naming the contract or failure they protect.
- Stop when source contradicts the ticket in a way that could overwrite newer architecture.
- Produce a ticket completion report and preserve all command output.
- Use configured agent classes; implementation work is interactive unless policy says otherwise.
- Use `agent-workflow launch`, never raw tmux or direct executor spawning.
- MCP remains a client adapter. Workflow scheduling, child launch, routing policy,
  approvals, messages, and receipts remain authoritative in shared services.
- Do not expose HTTP, force kill, arbitrary paths, raw terminal capture, shell
  strings, environment dumps, direct state-file writes, or MCP Tasks as the
  workflow authority.
- Runtime code may depend on `mcp==1.28.1`; do not import private APIs or copy
  the SDK into runtime application code.

## How to execute remaining work

Do not execute Phase 3 until `WF-22` is marked done in `BACKLOG.md`. Then start
with `phase-3/tickets/P3-00-workflow-baseline.md`, which must prove every MCP
operation maps to a stable shared service. Validate with
`agent-workflow pack validate` and run focused MCP/workflow tests before any
mutation implementation.
