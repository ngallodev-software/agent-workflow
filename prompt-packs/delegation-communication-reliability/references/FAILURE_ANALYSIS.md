# Communication failure analysis

The prior HARD-004 attempt exposed four independent failure modes:

1. It used a stale baseline and stopped on `status.json`/backlog projections
   even though current lifecycle receipts later showed HARD-001 and HARD-002
   accepted.
2. A child `progress` call attempted to mutate a read-only parent state and
   failed without a launch-time handshake or clear correlated fallback.
3. A pane could remain reported as running while its log and executor-event
   stream were empty.
4. A default completion template could exist without a substantive handoff.

Current source anchors include `sessions.progress` and
`sessions._append_control_message`, `metrics.write_control_events`,
`state.repair_status`, `runner._read_handoff_completion`, and the
`control-event`/`completion` schemas. Implementers must verify these anchors
against current source; this note is context, not authority.
