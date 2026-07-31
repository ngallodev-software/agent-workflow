# SQLite evidence index prompt pack

This pack completes and independently reviews the rebuildable SQLite projection governed by `DEC-007`. JSON/JSONL artifacts, immutable workflow snapshots, and sealed receipts remain authoritative. The database is a disposable host-local query projection.

## Phases

| Phase | Scope | Gate |
|---|---|---|
| 0 | Schema, provenance, deterministic reconciliation, and typed projections | `IDX-GATE-0` |
| 1 | Public CLI/man/help surfaces and supervisor integration | `IDX-GATE-1` |
| 2 | Privacy-governed analytical export and comparable cohort integration | `IDX-GATE-2` |
| 3 | Measured scale, incremental journal checkpoints, and migration proof | `IDX-GATE-3` |

Phases 0 and 1 are implemented in the current candidate and require independent acceptance. Phase 2 remains blocked on `HARD-006`, `SUP-003`, and comparable real-executor evidence. Phase 3 must be driven by measured scale evidence rather than assumption.

## Non-negotiable boundaries

- No lifecycle or permission decision exists only in SQLite.
- No arbitrary SQL or raw free-form content is exposed through the CLI.
- Rebuild must remain supported after every migration.
- Corrupt source evidence fails closed and is never rewritten by the indexer.
- A query result must disclose freshness and source provenance.
