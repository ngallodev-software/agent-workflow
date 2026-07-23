# P1-00 — Durable local messages and bounded steering

## Objective

Implement only the Phase-1 local substrate. Add a validated append-only message
log, child `progress`, parent `steer`, and `watch --after SEQUENCE` that blocks
until a durable record or timeout. Disk is authoritative; a tmux wakeup may
reduce latency but waiters always replay.

## Required behavior

- Versioned records have UUID idempotency IDs, session binding, contiguous
  sequence, flock/fsync, bounded fields, and malformed-tail rejection.
- `progress` is child-to-parent. `steer` is parent-to-child and remains pending
  until an explicit child `ack`; no terminal teardown is permitted.
- Reject terminal runs, traversal/symlink paths, arbitrary terminal targets,
  invalid directions/kinds, and oversized content.
- Preserve lifecycle `events.jsonl` semantics. Do not add a broker, daemon,
  database, remote transport, or generic plugin API.

## Writable paths

`src/agent_workflow/messages.py`, `sessions.py`, `cli.py`, `tmux.py`, narrowly
required schemas/receipts, matching tests, and command documentation only.

## Acceptance criteria

Parent `watch` returns a durable child update without a status-poll loop; a
steer has a UUID and remains pending until its correlated ack; restart/replay
does not lose or duplicate records.

## Tests and stop

Test append/replay, concurrent sequence, corrupt log, restart/replay, timeout,
pending/acknowledged steer, terminal rejection, and legacy launch/status. If a
selected executor closes stdin or has no verified control adapter, leave a steer
durable-and-pending; never fake delivery through shell keystrokes.
