# HIER-007 — root team scheduler and cross-team fan-in

## Objective

Schedule multiple teams from a root dependency graph, lease global capacity,
bind verified team results into dependent teams, and reconcile team receipts.

## Dependencies and lane

- Depends on accepted `HIER-GATE-2`.
- Critical path.

## Required behavior

- Enforce maximum teams, workers, interactive panes, and active leases globally.
- Deterministic team IDs and launch footprints prevent duplicate team leads.
- Cross-team inputs come only from verified team receipts/results and are copied
  into read-only bounded binding artifacts before dependent launch.
- Dependency failure/retry semantics mirror existing workflow safety.
- Global completion remains separate from explicit acceptance.

## Writable scope

Limit changes to the modules, schemas, focused tests, command/docs/man/skill surfaces directly required by this ticket. Preserve current direct-orchestrator compatibility and do not update `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant tests and an installed-product acceptance journey for the required behavior. Run package validation and relevant release audits. Record exact commands, exit codes, durable artifact paths, and receipt references.

## Acceptance criteria

All required behavior is proven from immutable contracts, append-only journals, verified receipts, and canonical service paths. Existing supported direct orchestration journeys remain green.

## Stop conditions

Stop and report rather than weakening durable authority, bypassing canonical launch/workflow services, inferring completion from tmux/process state, adding arbitrary recursion or multi-host infrastructure, widening permissions, or introducing shell-derived terminal commands.
