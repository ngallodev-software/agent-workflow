# DEC-007 — Rebuildable SQLite evidence projection

- **Status:** decided
- **Date:** 2026-07-30
- **Scope:** single-host operational search, supervision, and analysis
- **Supersedes:** the defer-until-slow posture previously recorded as `ARC-002`

## Decision

`agent-workflow` will use a hybrid evidence architecture:

1. Per-run JSON, append-only JSONL journals, immutable snapshots, and sealed receipts remain authoritative.
2. One host-local SQLite database provides a reconstructable, searchable projection across active and archived runs.
3. The projection may be deleted and rebuilt without losing execution, permission, review, workflow, or acceptance authority.
4. One indexer writer owns schema migration and reconciliation. Concurrent readers use SQLite WAL mode.
5. Every projected file and event retains source-run, relative-path, sequence, schema, and SHA-256 provenance.
6. Raw terminal captures, prompts, logs, message bodies, credentials, and unrestricted provider payloads are not copied into SQLite.
7. Multi-host shared authority is not introduced by this decision. PostgreSQL or a broker remains gated by `DEC-003`.

## Context

The evidence plane now includes launch contracts, lifecycle events, workflow journals, terminal observations, health samples, permission findings, incidents, remediation outcomes, process results, evaluation metrics, and hierarchy designs. File-local authority is ideal for sealing, portability, replay, and failure isolation, but repeated cross-run analysis through recursive filesystem scans is increasingly costly and difficult to secure consistently.

Typical operational questions are relational:

- Which executor/model combinations stall most often?
- Which permission operations remain pending?
- Which remediation rules recover runs?
- Which workflow nodes form the critical path?
- Which runs are missing or have corrupt evidence?
- Has elapsed time, first-output latency, token use, or cost regressed?

These questions should not require changing the authority model.

## Authority boundary

SQLite is a **materialized projection**, never a source of execution truth.

| Concern | Authoritative source | SQLite role |
|---|---|---|
| Launch identity and policy | `launch-contract.json`, provenance, source baseline | Searchable columns and digests |
| Lifecycle and workflow transitions | Append-only JSONL journals and immutable snapshots | Indexed event/node/edge views |
| Permission and remediation history | Per-run journals | Cross-run filtering and summaries |
| Completion and acceptance | Sealed completion, final receipt, lifecycle receipts | Verified digest and disposition columns |
| Terminal/output content | Per-run bounded files | Metadata/digest only; no raw content |
| Mutable status | Reconstructable `status.json` | Current projection for discovery only |

A query result cannot authorize a permission, acceptance, merge, restart, or policy expansion. Any authority-changing action must reopen and verify the original evidence.

## Selected technology

SQLite is selected for the single-host product because it provides transactions, migrations, foreign keys, indexes, views, concurrent readers, a small operational footprint, and excellent Python standard-library support.

The database is stored at:

```text
$XDG_STATE_HOME/agent-workflow/index/agent-workflow.sqlite3
```

Normal configuration uses:

- WAL journal mode;
- `synchronous=FULL`;
- foreign-key enforcement;
- a bounded busy timeout;
- application identity and schema version pragmas;
- one exclusive indexer lock;
- owner-only directory and file permissions.

## Reconciliation model

The first implementation performs safe per-run incremental reconciliation:

1. Discover active and, by default, archived run directories.
2. Compute a deterministic fingerprint from structured artifact paths, sizes, modification/change times, file identity, and mode metadata.
3. Skip unchanged current projections.
4. For a changed run, read structured artifacts through no-follow descriptors; hold shared locks while reading append-only JSONL journals.
5. Validate known `agent-workflow/*` schemas.
6. Replace that run’s projection in one transaction.
7. Quarantine corrupt runs as `index_state=error` without losing healthy projections.
8. Prune rows whose source run no longer exists in the selected discovery scope.

`agent-workflow index verify --full` rehashes every indexed structured source artifact. A later measured-scale task may add byte-offset journal checkpoints, but offset state must remain reconstructable and may never become event authority.

## Privacy and retention

Only normalized analytical fields, an allowlisted bounded incident summary, source metadata, and digests enter SQLite. Free-form remediation reasons are represented by digest only. In particular:

- terminal `content` is excluded;
- prompt and completion prose is excluded;
- output and stderr logs are excluded;
- message bodies are excluded;
- arbitrary provider payloads are excluded;
- permission targets are limited to the already-redacted source contract;
- summaries are bounded.

`HARD-006` and `SUP-003` still own final field-level retention, export, and deletion policy. SQLite must never become a way to bypass those gates.

## Failure and recovery

The database is disposable:

```bash
rm ~/.local/state/agent-workflow/index/agent-workflow.sqlite3*
agent-workflow index rebuild
agent-workflow index verify --full
```

A corrupt source run is represented as an index error and is not silently repaired. The authoritative run remains available for explicit evidence repair or investigation. SQLite migration errors affect only the projection and must never rewrite historical source artifacts.

## Alternatives considered

### Continue filesystem scans only

Rejected as the sole query mechanism. It preserves simplicity but scales poorly for cross-run supervision, trend analysis, workflow joins, and dashboards.

### DuckDB as the operational store

Deferred. DuckDB is attractive for Parquet and large analytical cohorts, but SQLite is better suited to host-local operational state, incremental updates, and many short CLI queries. DuckDB may later consume exported analytical snapshots.

### PostgreSQL

Deferred until multi-host operation is approved and demonstrated. It would add service deployment, authentication, backup, and availability requirements without improving the current local-first product enough to justify the burden.

### Replace JSONL with SQLite

Rejected. It would make database corruption, migration, or accidental mutation capable of changing the historical execution record and would reduce run portability and independent verification.

## Consequences

### Positive

- Fast cross-run operational and analytical queries.
- Searchable active and archived history.
- Better fleet views for the supervisor and future hierarchy.
- Deterministic recovery from the authoritative evidence plane.
- No new runtime dependency or database service.
- Clear migration path to Parquet/DuckDB or a future multi-host control plane.

### Costs and risks

- Duplicate derived data consumes disk space.
- Schema migrations and query compatibility require maintenance.
- Projection freshness must be visible to users.
- Privacy policy must cover normalized fields and summaries.
- Indexing active journals requires careful locking and corruption handling.

## Required verification

Closeout requires:

- rebuild equivalence after database deletion;
- safe incremental update and stale-row pruning;
- archive discovery;
- schema migration and downgrade refusal;
- SQLite integrity and foreign-key checks;
- full source-digest verification;
- corrupt-run quarantine without damaging healthy projections;
- proof that raw terminal and message content is absent;
- installed-wheel CLI and supervisor synchronization journeys;
- scale evidence before claiming a specific run/event capacity.
