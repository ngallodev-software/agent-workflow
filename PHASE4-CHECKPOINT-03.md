# Phase 4/5 Checkpoint 03 — External delivery adapter boundary

This cumulative changes-only overlay is based on the authoritative verified
Phase 3 source and includes Checkpoints 01–02 plus this slice.

## Added in this slice

- Treats `worker_mode=external` steering as `external-host-v1` rather than
  immediately closing persisted steer requests as unsupported.
- Adds a generation-guarded public pending-delivery view over existing durable
  Agent Run messages and steering-delivery evidence.
- Adds generation-guarded delivery reporting using the existing append-only
  steering-delivery journal; no parallel message or delivery authority is
  introduced.
- Requires caller-supplied positive delivery attempt numbers so retries of the
  same report remain idempotent at the journal boundary.
- Preserves delivery versus acknowledgement: successful host transport records
  `delivered` only; application/rejection remains the existing correlated
  acknowledgement path.
- Rejects delivery operations from stale or unbound external Worker
  generations.
- Documents the public schemas and CLI operations and advances the Phase 5
  planning state.

## Verification

Per Phase 4 policy, the test suite was not run. Only non-executing Python AST
parsing and archive/diff inspection were used before packaging.
