# BKL-001 — durable per-consumer cursors and handling dispositions

**Backlog:** [`BKL-001`](../../../../BACKLOG.md)  
**Priority:** P0 / High  
**Design:** [Durable two-way messaging](../../../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#add-one-shared-orchestrator-inbox)

## Goal

Add a reusable deterministic cursor/disposition substrate for consumers of append-only message journals. A consumer must resume after restart, process each source record idempotently, and advance its cursor only after the associated durable side effect has committed.

## External prerequisites

- `DEC-001` is resolved with explicit ordering, producer, idempotency, and no-wakeup-latency policy.
- `HARD-002` artifact/path integrity is accepted.
- `HARD-004` immutable launch and receipt authority is accepted.

Do not infer or silently choose unresolved service-level semantics inside this ticket.

## Required implementation

- Define a versioned cursor record keyed by consumer identity and source journal identity. Include last committed source sequence, source message ID/digest, disposition, update timestamp, and schema version.
- Define stable handling dispositions such as `applied`, `rejected`, `ignored`, `deferred`, and `security_error`. Do not use free-form prose as the machine state.
- Provide lock-scoped read, compare, and atomic update operations. Cursor advancement occurs only after the consumer’s durable target append or external-effect receipt is committed.
- Treat cursor files as performance projections. Missing, stale, truncated, or corrupt cursors trigger bounded replay/reconstruction rather than source message loss.
- Make duplicate source IDs idempotent only when canonical bytes/digest match. Conflicting reuse of an ID is a hard integrity failure.
- Support independent cursors for multiple consumers of the same journal without one consumer acknowledging work for another.
- Bind consumer identity to trusted configuration or immutable launch evidence; do not accept arbitrary path fragments or actor labels as storage keys.
- Preserve the existing append-only source journal as authority. Do not rewrite, compact, or annotate source records in place.

## Writable paths

- `src/agent_workflow/messages.py` and a narrowly named cursor/disposition module.
- Versioned JSON Schemas for cursor and disposition evidence.
- Public CLI/service code only if needed to inspect or repair a consumer cursor.
- One installed-product acceptance journey and one compact replay/integrity matrix.
- Architecture, operations, command/help/man documentation only where public behavior changes.

Run in parallel with `MSG-001` in a separate worktree. Avoid editing the orchestrator inbox implementation owned by `MSG-001` except through an agreed interface.

## Acceptance-first evidence

- An installed process consumes records, commits a durable target effect, advances its cursor, restarts, and does not repeat the semantic effect.
- A crash injected before the target commit leaves the cursor unchanged and the record is retried.
- A crash injected after target commit but before cursor update produces one idempotent target record and then advances safely.
- Deleting or corrupting the cursor reconstructs state from source and target evidence without losing messages.
- Two independent consumers advance independently.
- Reusing a source ID with different bytes fails closed and produces a stable diagnostic.

A compact parameterized matrix may cover malformed cursor versions, nonmonotonic sequences, duplicate IDs, and disposition transitions. Do not add private-parser, mock-call, or exact-dictionary tests.

## Security acceptance

- Cursor paths are beneath the configured state root, no-follow, regular-file only, and atomically replaced with directory fsync.
- Cursor identity cannot be used for path traversal or collision.
- A child cannot advance an orchestrator cursor.
- Error output does not disclose message content beyond the configured redaction policy.

## Non-targets

- Aggregate orchestrator inbox (`MSG-001`).
- Supervisor/wakeup loop (`MSG-002`).
- Late executor steering (`BKL-002`).
- Database migration, remote transport, or journal compaction.

## Stop conditions

Stop when `DEC-001` remains unresolved, the cursor would become authoritative over the source journal, a target effect lacks an idempotency contract, or implementation requires weakening path/identity controls.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include interface contracts consumed by `MSG-001` and `MSG-002`, injected-crash evidence, changed paths, acceptance commands, unresolved risks, and drift-audit results.
