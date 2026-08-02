# HIER-002 — hierarchy journals, replay, and receipts

## Objective

Add append-only fsynced hierarchy lifecycle/action/ack journals, deterministic
replay, team receipt, and root orchestration receipt construction/verification.

## Dependencies and lane

- Depends on `HIER-001`.
- Critical path; must be accepted by `HIER-GATE-0` before tmux topology work.

## Required behavior

- Local journal sequences are contiguous; cross-journal ordering uses causation
  and correlation, not a false global sequence.
- Imports are idempotent by source journal identity and message ID.
- Rebuild projections from immutable contract plus journals.
- Team receipt seals exact worker final/lifecycle/result evidence.
- Root receipt seals exact team contracts/receipts and global approval evidence.
- Tamper, truncation, duplicate, mixed-identity, and symlink tests fail closed.

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
