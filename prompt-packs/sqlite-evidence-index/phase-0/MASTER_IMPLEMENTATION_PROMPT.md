# Phase 0 master implementation prompt

Implement and independently verify the authority boundary, versioned schema, deterministic rebuild/incremental reconciliation, provenance, and typed projections.

Execute the phase manifest exactly. Preserve JSON/JSONL and sealed receipts as authority, use only fixed read-only query surfaces, record exact commands and evidence, run the release-drift audit, and stop on any design that makes SQLite non-reconstructable or capable of widening authority. Complete implementation tickets before the independent gate.
