# Orchestrator Messaging and Regression Evals

## Outcome

Make local tmux-backed delegations observable and steerable without a daemon or
network message bus, then establish two small receipt-backed regression evals:

1. a deterministic JSON-normalization task; and
2. a pinned-browser priority-picker task that proves explicit parent/child
   communication as well as visual and accessibility behavior.

## Decision

The run directory remains the authority. Add append-only, fsync'd control
records and use `tmux wait-for` only as a best-effort wakeup. A waiter always
replays durable records after waking. This avoids lost updates if tmux, a
watcher, or an orchestrator restarts.

Do not add Redis, NATS, Temporal, a daemon, a database, or a generic plugin
system for this single-host CLI. Those become candidates only when runs need
cross-host consumers, independently durable subscriptions, or multi-user ACLs.

`tmux wait-for` is documented in the [tmux manual](https://github.com/tmux/tmux/blob/master/tmux.1); filesystem wakeup behavior and loss/coalescing limits are documented by [inotify](https://man7.org/linux/man-pages/man7/inotify.7.html). Redis Streams and Temporal signals are research comparators, not dependencies: [Redis Streams](https://redis.io/docs/latest/develop/data-types/streams/) and [Temporal message passing](https://docs.temporal.io/develop/python/message-passing).

## Contracts

### Control record

`messages.jsonl` is append-only while a run is active. Every record has a
versioned schema, contiguous `sequence`, UUID `message_id`, session ID, UTC
timestamp, `parent_to_child` or `child_to_parent` direction, `steer`,
`progress`, `ack`, or `error` kind, bounded actor/content, and an optional
correlation ID.

Writers lock, append one complete line, flush, and fsync. Records are capped,
validated, and replayed in contiguous sequence order. A command is at-least
once; consumers deduplicate by `message_id` and append an `ack` only after
applying its effect.

### Delivery boundary

The CLI supports child progress and parent steering records plus a blocking
`watch` view. It cannot promise that an arbitrary one-shot executor consumes a
prompt after its initial stdin closes. Executor-specific live injection is a
later adapter with an acknowledgement contract; terminal keystrokes are not
semantic delivery evidence.

### Sealed evaluation evidence

Before sealing, write `execution-metrics.json` and `control-events.jsonl`.
Metrics include nullable input/cached-input/output/provider-total/cost/currency,
monotonic stage duration, first-output latency, retries, steering outcomes, and
normalized errors. Absence is `null`, never zero. Raw executor streams remain
the primary provider evidence.

## Phases

| Phase | Scope | Exit gate |
|---|---|---|
| 0 | Research and design decision | Source-backed contract matrix; no runtime edits. |
| 1 | Durable local messaging | Validated log, progress, steer, replay-based wait, unit tests. |
| 2 | Deterministic eval and metrics | Sealed metrics/control artifacts; normalization fixture and stable report. |
| 3 | Visual orchestration eval | Pinned browser fixture, explicit child telemetry, receipt bridge. |

## Current implementation status

Phase 1 is implemented and hardened: `messages.jsonl` uses a versioned,
validated, locked and fsync'd record format. It rejects unsafe targets, mixed
session records, duplicate IDs, invalid direction/kind pairs, and duplicate or
out-of-order acknowledgements. The CLI exposes `steer`, `progress`, `ack`, and
blocking `watch`; a request is durable and observable but is not represented as
delivered until a correlated acknowledgement exists.

Phase 2 is implemented for native runs: `control-events.jsonl` and
`execution-metrics.json` are atomically written, schema-validated, sealed,
made read-only, and included in reports. Metrics expose nullable normalized
provider usage, orchestration/child/verification/total stages, steer state,
and errors. The deterministic normalization fixture has hidden-contract,
mutation, oracle-canary, and repeatability coverage.

The generic executor adapter remains intentionally absent: current runners
write an initial prompt to one-shot stdin and close it, so they cannot prove
late semantic delivery. Phase 3 is correctly blocked: no pinned browser image
digest/font manifest or verified pre-seal browser/Inspect evidence bridge is
available. See `docs/PHASE_3_BLOCKED_GATE_REPORT.md`.

## Evaluation fixtures

### Deterministic JSON normalization

Fixture layout:

```text
tests/fixtures/regression-evals/deterministic-json/
  app/normalize.py
  tests/test_normalize.py
  tests/fixtures/input.json
  tests/fixtures/expected.json
  prompt.md
  evaluation.json
```

The task is `normalize_records(records)`: canonical ordering, duplicate merge,
UTC timestamp normalization, invalid-row rejection, and stable JSON output.
Known plus evaluator-only hidden cases and deliberate mutations independently
cover ordering, duplicate merge, timezone, invalid input, and formatting.
Functional verdicts are exact exit/test/output facts, never an LLM judgment.

### Visual priority picker

Fixture layout:

```text
tests/fixtures/regression-evals/ui-child-handoff/
  app/index.html
  app/app.js
  app/style.css
  tests/ui.spec.ts
  Dockerfile
  prompt.md
  evaluation.json
```

The UI opens a compact priority palette; choosing `Urgent` changes the badge
and accessible label; Escape closes the palette without changing selection.
Pin a 1280x720 viewport, device scale, browser, fonts, and animation timing.
Use Playwright click/keyboard/ARIA assertions and an evaluator-held screenshot
baseline. Explicit telemetry must include `child_started`, request/result
digests, `child_finished`, stage, child ID, monotonic time, and errors.

## Acceptance criteria

- A parent blocks on a session update instead of polling; restart/replay does
  not lose a message.
- A child emits progress; a parent persists a steer request and observes its
  acknowledgement or non-delivery state without killing the session.
- Every eval run retains stage and total usage/cost/time, retry/error, and
  steering summaries, plus raw sealed evidence.
- The deterministic fixture has known and evaluator-only hidden cases and a
  repeatable exact verdict.
- The UI fixture pins browser/font/viewport/animation behavior and checks DOM,
  keyboard, accessibility, and screenshot evidence. It fails if required child
  telemetry is absent, out of order, or unacknowledged.

## Non-goals and stop conditions

- Do not infer progress or delegation from model prose.
- Do not auto-accept a ticket from terminal exit, a message, or an eval pass.
- Do not persist secrets/raw prompts in control records.
- Stop a phase if an executor adapter, pinned browser image, or source contract
  is unavailable; record the blocker rather than inventing a transport.
