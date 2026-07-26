# MSG-005 — restart reconstruction and missed-wakeup recovery

**Backlog:** [`MSG-005`](../../../../docs/BACKLOG.md)  
**Priority:** P1 / Critical  
**Design:** [Failure and restart behavior](../../../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#failure-and-restart-behavior)

## Goal

Prove that supervisor, orchestrator, and host-process restarts cannot lose durable child events, duplicate semantic delivery, or strand agents because a wake signal was missed.

## Dependencies

- `BKL-001`, `MSG-001`, and `MSG-002`.

## Required implementation

- Reconstruct active child registrations, source cursors, inbox events, pending acknowledgements, and pending actions from durable records at supervisor startup.
- Treat cursor and supervisor status files as projections; rebuild them from source and target evidence when absent or inconsistent.
- Define deterministic stale-lock recovery for a crashed supervisor. Use process identity/start evidence and bounded operator override; do not delete a lock merely because elapsed time passed.
- Reconcile crash windows explicitly: before source read, after source read, before inbox append, after inbox append, before cursor update, after notification attempt, after application acknowledgement, and before action append.
- Ensure duplicate inbox import and duplicate wake/resume attempts are idempotent by stable keys and digests.
- Add bounded periodic replay so a missed/coalesced wake signal meets the `DEC-001` maximum no-wakeup latency.
- Preserve fairness and bounded work when many sessions accumulate events during downtime.
- Expose a diagnostic/rebuild command only if it uses the same deterministic reconstruction service and cannot mutate source authority.

## Writable paths

- Supervisor recovery/reconciliation services and projections.
- Acceptance fixtures for injected crash points and process restart.
- Compact recovery matrix.
- Operations/troubleshooting documentation.

Run in parallel with `MSG-003`. Avoid wake/resume adapter implementation except through its declared interface.

## Acceptance-first evidence

Tests must exercise the installed public command/service path first; retain only a compact low-level matrix where exhaustive replay or security cases cannot be expressed economically end to end.

- Kill the supervisor at every durable boundary and restart it; each source event produces exactly one semantic inbox event.
- Omit all tmux signals; periodic replay delivers within the configured SLO.
- Delete the cursor projection; reconstruction does not lose or duplicate an event.
- Corrupt a cursor; the supervisor quarantines/diagnoses it and rebuilds safely.
- Start two supervisors after a crash; one obtains ownership and the other does not write.
- Accumulate events from many children while the supervisor is down; restart drains them fairly within bounds.
- An acknowledged but unactioned event remains visible after restart.

## Security acceptance

- Recovery never trusts mutable PID alone for stale-lock decisions.
- Quarantined projection content is bounded and redacted.
- Reconstruction validates source IDs/digests and fails closed on conflicting duplicates.
- Operator repair cannot rewrite source journals or sealed lifecycle evidence.

## Non-targets

- Multi-host consensus, leader election, distributed locks, or remote broker replay.
- Journal compaction or destructive cleanup.

## Stop conditions

Stop if correctness depends on a wake signal, if recovery requires editing source records, or if lock ownership cannot be established safely.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the crash-window matrix, timing evidence against `DEC-001`, lock-recovery design, and exact reconstruction sources.
