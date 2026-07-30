# HIER-003 — managed tmux session/window topology

## Objective

Create one root-managed tmux session with a root window and stable team windows;
create worker panes only inside the owning team window.

## Dependencies and lane

- Depends on accepted `HIER-GATE-0`.
- External gate: `PROC-006` pane-identity work must be accepted.
- Critical path; `HIER-004` may branch in parallel after this ticket.

## Required behavior

- Use stable tmux IDs and metadata; names/indexes are display-only.
- Bind root/team/session/assignment identities at session, window, and pane levels.
- Reconcile missing, moved, reindexed, dead, and conflicting topology without
  duplicate launches.
- Preserve current direct pane launch compatibility.
- Enforce global and per-team interactive-pane budgets before mutation.
- Installed-product tests must cover two team windows, pane movement/reindexing,
  terminal loss, attach, and restart reconciliation.

## Writable scope

Limit changes to the modules, schemas, focused tests, command/docs/man/skill surfaces directly required by this ticket. Preserve current direct-orchestrator compatibility and do not update `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant tests and an installed-product acceptance journey for the required behavior. Run package validation and relevant release audits. Record exact commands, exit codes, durable artifact paths, and receipt references.

## Acceptance criteria

All required behavior is proven from immutable contracts, append-only journals, verified receipts, and canonical service paths. Existing supported direct orchestration journeys remain green.

## Stop conditions

Stop and report rather than weakening durable authority, bypassing canonical launch/workflow services, inferring completion from tmux/process state, adding arbitrary recursion or multi-host infrastructure, widening permissions, or introducing shell-derived terminal commands.
