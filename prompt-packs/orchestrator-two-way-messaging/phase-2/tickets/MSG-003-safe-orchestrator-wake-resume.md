# MSG-003 — safe orchestrator wake and resume adapters

**Backlog:** [`MSG-003`](../../../../BACKLOG.md)  
**Priority:** P0 / Critical  
**Design:** [Wake the orchestrator safely](../../../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#the-supervisor-must-wake-the-orchestrator-safely)

## Goal

Add a bounded adapter layer that surfaces pending durable events to an orchestrator turn without injecting child-controlled content and without assuming that tmux pane liveness means a model process is ready.

## Dependencies and prerequisites

- Pack dependency: `MSG-002`.
- External prerequisites: `HARD-004`, `HARD-006`, `HARD-007`, and `HARD-008` accepted.

## Required implementation

- Define typed outcomes for `notified_existing_turn`, `resumed_turn`, `started_turn`, `already_pending`, `unsupported`, `expired`, and `failed`.
- The adapter receives only trusted orchestrator identity and opaque event ID/cursor. It must fetch no child-controlled text for pane injection.
- For tmux notification, inject one fixed application-owned token or command. Use literal key operations/argv and avoid shell interpretation.
- Verify pane/session identity from immutable launch/session evidence before injection.
- Detect whether an orchestrator process is available to receive input. Pane existence alone is insufficient.
- Where supported, add executor-native resume/start adapters with bounded process execution and idempotency keys.
- Record every attempt and outcome durably before retrying. Prevent repeated wake signals from starting duplicate turns for the same pending event set.
- Apply bounded retry/backoff and preserve pending events when all adapters fail.
- Do not mark an event delivered merely because `send-keys` returned zero; delivery evidence requires the adapter-specific contract.

## Writable paths

- New orchestrator notification/resume adapter module.
- Existing executor/tmux integration only through narrow interfaces.
- Configuration for adapter selection and bounded retries.
- Acceptance fixtures, help/man/operations documentation for implemented commands.

Run in parallel with `MSG-005` in a separate worktree.

## Acceptance-first evidence

Tests must exercise the installed public command/service path first; retain only a compact low-level matrix where exhaustive replay or security cases cannot be expressed economically end to end.

- A verified waiting orchestrator pane receives only the fixed event token and then reads the event through the public CLI.
- A child summary containing quotes, shell syntax, terminal control sequences, and prompt-injection prose does not appear in pane input, argv, logs, or notification evidence.
- When the prior orchestrator process exited, a supported adapter starts/resumes one new turn and records `started_turn` or `resumed_turn`.
- Duplicate notifications for the same pending set do not start duplicate turns.
- Unsupported adapters leave the event pending with explicit evidence.
- Adapter failure and retry do not lose or action the event.

## Security acceptance

- Fixed notification templates are application-owned constants, not configuration strings writable by children.
- Principal authorization prevents a child from waking an unrelated orchestrator.
- Terminal control characters and oversized IDs are rejected before any adapter call.
- All commands use the bounded process substrate and sanitized environment.

## Non-targets

- Reading/actioning events (`MSG-004`).
- Generic arbitrary terminal automation.
- Remote orchestrator transport or HTTP.

## Stop conditions

Stop if the adapter must inject event content, cannot verify the destination identity, or cannot distinguish pane existence from a receptive orchestrator process.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include adapter outcome contracts, injection-safety evidence, idempotency proof, supported/unsupported matrix, and drift-audit results.
