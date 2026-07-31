# MSG-002 — foregroundable supervisor and shared wakeup channel

**Backlog:** [`MSG-002`](../../../../docs/BACKLOG.md)  
**Priority:** P0 / Critical  
**Design:** [Use one shared wake channel](../../../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#use-one-shared-wake-channel)

## Goal

Implement a deterministic, foregroundable supervisor that waits on one best-effort orchestrator wake channel, periodically replays all registered child journals, normalizes new events into the aggregate inbox, and remains correct when signals are lost or duplicated.

## Dependencies and prerequisites

- Pack dependencies: `BKL-001`, `MSG-001`.
- External prerequisites: `HARD-001` and `HARD-008` accepted.

## Required implementation

- Add a public command such as `agent-workflow orchestrator watch ORCHESTRATOR_ID` only after command naming is reconciled with the existing CLI hierarchy and docs.
- Run in the foreground by default. It may be launched inside tmux or by an external user service, but this ticket must not install an implicit system daemon.
- Derive one non-sensitive shared tmux wait-for channel from the trusted orchestrator identity.
- After every timeout or signal, enumerate the verified registry and replay each child after its durable cursor. Never treat the signal itself as evidence.
- Commit normalized inbox events before advancing child-source cursors.
- Enforce bounded batches, round-robin/fair replay, configurable polling fallback, exponential backoff on repeated adapter/storage failure, and clean shutdown.
- Acquire a single-supervisor lock/lease. A second active supervisor exits with a stable diagnostic or enters an explicitly read-only observer mode.
- Record supervisor startup, shutdown, wake reason, replay counts, cursor outcomes, and errors without logging sensitive message bodies.
- Keep status/projection files non-authoritative. Reconstruct pending work from registry, source journals, inbox, acknowledgements, and cursors.

## Writable paths

- New supervisor service and CLI dispatch.
- `tmux.py` only for the shared-channel helper and bounded wait/signal adapter.
- Configuration schema/defaults for bounded intervals and batch limits.
- Installed-product supervisor journeys and compact lock/fairness matrices.
- Help, man, architecture, operations, and diagrams where public behavior changes.

Run in parallel with `BKL-002`. Do not edit executor-specific late-steering adapters owned by that ticket.

## Acceptance-first evidence

Tests must exercise the installed public command/service path first; retain only a compact low-level matrix where exhaustive replay or security cases cannot be expressed economically end to end.

- A child completion wakes the supervisor, produces one inbox event, and advances the source cursor only after the inbox append.
- Suppressing the wake signal still delivers the event within the configured maximum no-wakeup latency.
- Sending the wake signal repeatedly does not duplicate the event.
- Two children completing concurrently are both delivered without starvation.
- A second supervisor cannot become an active writer.
- SIGTERM or Ctrl-C exits cleanly without advancing an uncommitted cursor.
- Restarting the supervisor resumes from durable evidence.
- Installed-product evidence covers lost and duplicate wake hints; focused
  deterministic invariants cover bounded round-robin replay,
  single-supervisor exclusion, and SIGTERM/SIGINT cursor resume without
  treating the hint or terminal output as authority.

## Security acceptance

- Channel names reveal no local path, prompt, user, or secret.
- All subprocess behavior uses the bounded process substrate; no `shell=True` or shell interpolation.
- Registry, cursor, and inbox paths are validated through the hardened no-follow path layer.
- Supervisor logs and diagnostics are metadata-minimal and redacted.

## Non-targets

- Injecting anything into the orchestrator pane (`MSG-003`).
- Implementing a new scheduler, message broker, database, socket authority, or system daemon.
- Treating process/pane liveness as completion or readiness evidence.

## Stop conditions

Stop if the design requires one watcher process per child, relies on wake delivery for correctness, advances a cursor before the inbox commit, or cannot establish single-writer ownership.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include timing/failure evidence, supervisor state contract, CLI/help changes, bounded resource measurements, and integration notes for `MSG-003` and `MSG-005`.
