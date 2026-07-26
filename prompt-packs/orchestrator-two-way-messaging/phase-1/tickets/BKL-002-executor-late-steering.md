# BKL-002 — executor-specific post-launch steering

**Backlog:** [`BKL-002`](../../../../docs/BACKLOG.md)  
**Priority:** P0 / High  
**Design:** [Acknowledgement model](../../../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#acknowledgement-model)

## Goal

Make post-launch parent-to-child steering real for detached or long-running executor sessions. A running executor must consume a durable steer without restart and emit a correlated `delivered`, `applied`, `rejected`, `unsupported`, or `expired` outcome.

## Dependencies and prerequisites

- Pack dependency: `BKL-001`.
- External prerequisites: `HARD-001`, `HARD-004`, `HARD-007`, and `HARD-008` accepted.

## Required implementation

- Define one typed adapter contract for delivering a bounded steer to a verified live executor session.
- Implement adapters only for executor modes whose real delivery mechanism is understood and can produce evidence. Unsupported modes return a durable `unsupported` result; they do not pretend terminal text proves application.
- Correlate every adapter attempt and child acknowledgement to the original immutable message ID.
- Distinguish `queued`, `delivered`, `applied`, `rejected`, `unsupported`, `expired`, and `failed`. Do not collapse these into one boolean.
- Bind the recipient to immutable session/executor identity and authenticated principal authorization.
- Preserve replay idempotency: retrying an already applied steer cannot apply it twice.
- Set bounded delivery deadlines and attempt counts. Expiration is durable evidence.
- Record adapter executable/version/identity and sanitized outcome through shared provenance controls.
- Preserve existing interactive-agent reuse semantics and integrate rather than adding a second assignment channel.

## Writable paths

- Executor adapter boundary and existing session/message services.
- Executor-specific protocol fixtures and opt-in live adapter tests.
- Public CLI output only where stronger status is available.
- Operations/help/man documentation for actual supported modes.

Run in parallel with `MSG-002`; avoid the aggregate inbox/supervisor implementation.

## Acceptance-first evidence

- A deterministic external fixture receives a steer after launch and emits a correlated applied acknowledgement.
- Retrying the same message ID does not apply the instruction twice.
- A fixture explicitly rejects a steer and the parent sees `rejected`, not `applied` or generic failure.
- An unsupported detached mode returns durable `unsupported` evidence.
- Expired steering is not delivered later after restart.
- Interactive-agent reuse continues to require correlated child acknowledgement before returning to `busy`.
- Opt-in live compatibility covers each executor adapter claimed as supported.

## Security acceptance

- Steer content follows size, classification, redaction, and retention policy.
- Adapter invocation is argv-only through the bounded process substrate.
- A caller cannot steer a session it does not own or target a different executor process by mutable PID/path data.
- Child acknowledgements are accepted only from the verified recipient identity.

## Non-targets

- Aggregate orchestrator inbox and child-completion fan-in.
- Arbitrary terminal key injection as a generic steering implementation.
- Claiming support for executors without live evidence.

## Stop conditions

Stop when an executor offers no evidence-capable delivery mechanism, when principal identity is unavailable, or when implementation would equate terminal output/process liveness with applied steering.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the adapter support matrix, real versus fixture evidence, unsupported modes, correlation/replay proof, and documentation updates.
