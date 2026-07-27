# DEC-001 — Durable-control service objective

**Status:** decided
**Date:** 2026-07-26
**Scope:** single-host `agent-workflow` runs and local tmux orchestration

## Decision

Use the existing local filesystem and append-only JSONL journals as the
durable-control authority. Cursors, projections, wake signals, terminal text,
and agent claims are secondary evidence or performance aids; they never replace
the source journal or sealed lifecycle/receipt evidence.

| Objective | Decision |
|---|---|
| Storage and failure model | Machine-local state below the configured XDG state root. Source records and aggregate inbox appends are locked, bounded, fsynced, and append-only. A crash may leave work to replay; it must not erase a committed source record. Remote replication is out of scope. |
| Ordering scope | FIFO by source journal sequence for each consumer, and monotonic sequence for each aggregate inbox. There is no global order across child journals. |
| Producer model | At-least-once durable append. `tmux wait-for` is a best-effort wake hint only; periodic replay is mandatory and correctness cannot depend on signal delivery. |
| External-effect idempotency | A source message ID is idempotent only when its canonical bytes/digest match. Target effects use a stable source identity and digest; retrying after any crash window must produce one semantic effect or a durable rejected/security disposition. |
| Cursor semantics | A cursor is a rebuildable projection keyed by trusted consumer and source identity. Advance it only after the target append/effect receipt is committed. Missing, corrupt, or stale cursors replay from the authoritative journal. |
| No-wakeup objective | The supervisor replays all registered sources at least every 2 seconds under normal local load. This is an operational objective, not a correctness guarantee; missed wakeups are recovered by the next bounded replay. |
| Security boundary | Paths are beneath the configured state root and opened with no-follow regular-file checks. Actor labels, mutable status, terminal output, and child-controlled content cannot authorize lifecycle or delivery state. |

## Consequences

- `BKL-001` and `MSG-001` may implement local cursor and inbox contracts
  against this decision.
- `MSG-002` must use one shared wake channel plus a 2-second bounded replay
  fallback and a single-supervisor lock.
- `BKL-002` and later adapters must report `queued`, `delivered`, `applied`,
  `rejected`, `unsupported`, `expired`, or `failed`; they may not infer
  application from a live pane or terminal text.
- A future distributed or remote-control design requires a new decision; it
  must not silently change these local guarantees.

## Rejected alternatives

Redis, NATS, SQLite WAL, a per-child daemon, and terminal scraping are not
introduced for this phase. They may be reconsidered only after measured local
scale or recovery evidence demonstrates that JSONL cannot meet the objective.

## Evidence required for implementation acceptance

The messaging phase must prove crash-window replay, duplicate-ID conflict
rejection, independent consumer progress, corrupt-cursor reconstruction,
single-supervisor ownership, missed-wakeup recovery within the objective, and
correlated executor delivery/application outcomes.
