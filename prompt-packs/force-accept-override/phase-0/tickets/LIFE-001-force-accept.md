# LIFE-001 — audited manual force acceptance

## Objective

Add a simple user-invocable force-accept CLI command for a completed run whose
normal acceptance gate cannot be satisfied. The command is an explicit local
operator override, not an authenticated-human security boundary: HARD-007
remains blocked and must be named in documentation and output.

## Required preflight

Read `docs/references/WORKTREE_PREFLIGHT.md` and perform the exact-worktree
preflight before structural discovery. Read the current parser, lifecycle,
approval, receipt, and relevant acceptance tests before editing.

## Writable scope

`src/agent_workflow/cli.py`, lifecycle/approval/receipt modules strictly
needed by the command, schemas for an additive override receipt, focused
acceptance/invariant tests, `docs/COMMAND_REFERENCE.md`, `docs/OPERATIONS.md`,
and this ticket handoff. Do not change ordinary `accept` semantics, MCP tools,
or backlog state.

## Required behavior

- Expose a dedicated `agent-workflow force-accept` command; do not add a
  bypass flag to ordinary `accept`.
- Require an explicit force acknowledgement and a non-empty reason; require a
  local interactive terminal or another narrowly documented manual operator
  confirmation mechanism.
- The command must record an immutable, receipt-linked override disposition
  including session, actor, timestamp, reason, normal-gate failures, and the
  invoking command identity. It must never alter or fabricate normal review,
  completion, evaluation, or final-receipt artifacts.
- It may override only a terminal run. Refuse running/launched sessions and
  invalid/missing lifecycle evidence. Preserve append-only lifecycle order.
- The default list/status/ledger outputs must distinguish normal acceptance
  from forced acceptance.
- Document that this is operator-controlled, not authenticated human-only
  authorization; HARD-007 remains the required future security boundary.

## Evidence

Add an installed-product journey that first proves ordinary acceptance still
rejects the incomplete fixture, then demonstrates that explicit manual
force-accept creates the override receipt and visible disposition. Add a
compact invariant matrix for missing acknowledgement, empty reason,
non-terminal state, repeated force requests, and tamper/missing evidence.
Run focused tests, `python3 scripts/audit-release-assets.py`, pack validation,
and the relevant full suite; record all exit codes.

## Stop conditions

Stop if a solution requires pretending to authenticate a human, rewrites or
deletes normal evidence, permits a running run, exposes the override through
MCP, or weakens the ordinary `accept` validation path.

## Handoff

Use `templates/TICKET_COMPLETION.md`; include the exact override authority
model, receipt schema/paths, ordinary-path regression evidence, known HARD-007
limitation, and sealed completion evidence.
