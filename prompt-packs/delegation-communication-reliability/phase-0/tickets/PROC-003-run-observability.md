# PROC-003 — silent-run observability and recovery

**Backlog:** [`PROC-003`](../../../../docs/BACKLOG.md)

## Goal

Detect a run whose pane is alive but whose heartbeat, log, and executor event
stream are silent, classify it as a communication fault, and provide a safe
retry/close path without deleting evidence.

## Writable paths

- `src/agent_workflow/agent_context.py`, `src/agent_workflow/state.py`, and
  the public status/observation CLI path.
- Focused status/watchdog journey and a compact stale-state matrix.

## Acceptance

- Status reports heartbeat age, log/event growth, tmux liveness, and pane death
  independently; it does not call a silent live pane healthy.
- Observation distinguishes legitimate long work from missing communication
  using configured thresholds and preserves the advisory nature of
  `possibly_stalled`.
- Interrupt/terminate/retry preserves the original run evidence and creates a
  new lineage-visible session when retried.
- The public status/watch journey proves detection and safe closeout.
- Add or update a focused installed-product test and report its exit code.

## Non-targets and stop conditions

Do not auto-kill solely because a timer elapsed, alter tmux ownership, or add a
new scheduler. Stop if the state cannot be reconstructed without rewriting
authority. Use `templates/TICKET_COMPLETION.md`.
