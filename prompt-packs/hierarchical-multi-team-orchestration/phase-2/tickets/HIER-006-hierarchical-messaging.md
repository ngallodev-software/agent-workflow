# HIER-006 — root/team/worker messaging and escalation

## Objective

Extend durable messaging to root ↔ team lead and team lead ↔ worker with replay,
cursors, correlation, acknowledgement, bounded references, and wake hints.

## Dependencies and lane

- Depends on `HIER-005`.
- External gate: `BKL-002` late steering must be accepted.
- Critical path; acceptance is recorded by `HIER-GATE-2`.

## Required behavior

- Root normally addresses team leads, not workers.
- Team lead resolves questions locally only within delegated authority.
- Escalation preserves causation from worker question through root decision to
  worker steer and applied/rejected acknowledgement.
- `received` is distinct from `applied`; terminal/process evidence is insufficient.
- Missed/coalesced tmux wakeups cannot lose messages.
- Prove duplicate imports, restart replay, late steer, cancel, unavailable, and
  conflicting identity behavior.

## Writable scope

Limit changes to the modules, schemas, focused tests, command/docs/man/skill surfaces directly required by this ticket. Preserve current direct-orchestrator compatibility and do not update `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant tests and an installed-product acceptance journey for the required behavior. Run package validation and relevant release audits. Record exact commands, exit codes, durable artifact paths, and receipt references.

## Acceptance criteria

All required behavior is proven from immutable contracts, append-only journals, verified receipts, and canonical service paths. Existing supported direct orchestration journeys remain green.

## Stop conditions

Stop and report rather than weakening durable authority, bypassing canonical launch/workflow services, inferring completion from tmux/process state, adding arbitrary recursion or multi-host infrastructure, widening permissions, or introducing shell-derived terminal commands.
