# Execution protocol

Use `docs/references/EXECUTION_PROTOCOL.md`. Immutable contracts, append-only
health/incident/remediation journals, and sealed receipts are authoritative.
Process state, tmux panes, terminal capture, and mutable status are observations.
Automatic actions must be deterministic, idempotent, attempt-bounded, verified,
and incapable of widening authority.
