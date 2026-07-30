# HIER-005 — bounded team-lead runtime

## Objective

Launch a team lead through canonical session services with principal identity and
an immutable delegation contract, then let it launch canonical worker workflows
within that contract.

## Dependencies and lane

- Depends on accepted `HIER-GATE-1`.
- External gates: `MSG-001`, `PROC-001`, and `PROC-002` must be accepted.
- Critical path.

## Required behavior

- No alternate executor/scheduler path.
- Team readiness requires durable registry/inbox/workflow footprint.
- Worker contracts are strict subsets of team authority.
- Enforce source/worktree isolation, executor/model/command/retry/time budgets,
  allowed tasks, and capacity leases.
- Team lead cannot create team leads or alter root journals/projections.
- Completion requires a verified team receipt, not team-lead prose or pane exit.

## Writable scope

Limit changes to the modules, schemas, focused tests, command/docs/man/skill surfaces directly required by this ticket. Preserve current direct-orchestrator compatibility and do not update `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant tests and an installed-product acceptance journey for the required behavior. Run package validation and relevant release audits. Record exact commands, exit codes, durable artifact paths, and receipt references.

## Acceptance criteria

All required behavior is proven from immutable contracts, append-only journals, verified receipts, and canonical service paths. Existing supported direct orchestration journeys remain green.

## Stop conditions

Stop and report rather than weakening durable authority, bypassing canonical launch/workflow services, inferring completion from tmux/process state, adding arbitrary recursion or multi-host infrastructure, widening permissions, or introducing shell-derived terminal commands.
