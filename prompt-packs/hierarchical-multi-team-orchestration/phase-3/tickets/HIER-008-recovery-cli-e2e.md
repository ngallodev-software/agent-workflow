# HIER-008 — recovery, CLI tree UX, and end-to-end proof

## Objective

Deliver orchestration/team CLI commands, tree status/attach UX, deterministic
root/team recovery, and a sealed installed-product multi-team journey.

## Dependencies and lane

- Depends on `HIER-007`.
- Final critical-path implementation ticket before `HIER-GATE-3`.

## Required behavior

- Reconstruct state after root restart, team-lead loss, tmux server loss, window
  close, pane movement, and external terminal close without duplicate launches.
- Distinguish lost/intervention-required from failed/completed.
- Tree output shows root, teams, workers, dependencies, unread questions,
  capacities, receipts, and approval state from durable evidence.
- Prove two team leads with multiple workers, local and escalated questions,
  cross-team result binding, steering, tamper rejection, team/root sealing, and
  explicit final acceptance.
- Update architecture, operations, command reference, skills, man pages, tests,
  release assets, and changelog without stale parallel task lists.

## Writable scope

Limit changes to the modules, schemas, focused tests, command/docs/man/skill surfaces directly required by this ticket. Preserve current direct-orchestrator compatibility and do not update `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant tests and an installed-product acceptance journey for the required behavior. Run package validation and relevant release audits. Record exact commands, exit codes, durable artifact paths, and receipt references.

## Acceptance criteria

All required behavior is proven from immutable contracts, append-only journals, verified receipts, and canonical service paths. Existing supported direct orchestration journeys remain green.

## Stop conditions

Stop and report rather than weakening durable authority, bypassing canonical launch/workflow services, inferring completion from tmux/process state, adding arbitrary recursion or multi-host infrastructure, widening permissions, or introducing shell-derived terminal commands.

## Feature-boundary steering

Implement hierarchy-specific contracts, services, state, and policy in the dedicated built-in hierarchy feature package. Core authority services may be consumed through narrow public interfaces; do not embed hierarchy-only branches throughout generic session, scheduler, CLI, workflow, or tmux modules. Preserve direct orchestration as the default path and require explicit hierarchy enablement.
