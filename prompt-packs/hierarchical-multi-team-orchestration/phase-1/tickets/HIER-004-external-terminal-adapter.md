# HIER-004 — optional external terminal adapter

## Objective

Add a narrow configured argv-only adapter that can open a new terminal attached
to an exact managed tmux team window.

## Dependencies and lane

- Depends on `HIER-003`.
- Optional side branch; does not block `HIER-005` or later core hierarchy work.
- Requires independent acceptance through `HIER-GATE-1A` if implemented.

## Required behavior

- `current` mode always works without spawning another terminal.
- Implement one host-tested adapter selected through trusted configuration.
- Never accept prompt-derived shell text or silently fall back to shell mode.
- External terminal failure leaves the durable team/window intact and returns an
  exact attach command/diagnostic.
- Record executable identity, argv, exit, and bounded output through process.py.

## Writable scope

Limit changes to the modules, schemas, focused tests, command/docs/man/skill surfaces directly required by this ticket. Preserve current direct-orchestrator compatibility and do not update `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant tests and an installed-product acceptance journey for the required behavior. Run package validation and relevant release audits. Record exact commands, exit codes, durable artifact paths, and receipt references.

## Acceptance criteria

All required behavior is proven from immutable contracts, append-only journals, verified receipts, and canonical service paths. Existing supported direct orchestration journeys remain green.

## Stop conditions

Stop and report rather than weakening durable authority, bypassing canonical launch/workflow services, inferring completion from tmux/process state, adding arbitrary recursion or multi-host infrastructure, widening permissions, or introducing shell-derived terminal commands.
