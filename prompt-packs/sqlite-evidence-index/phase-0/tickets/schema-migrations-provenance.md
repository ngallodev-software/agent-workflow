# IDX-001 — versioned SQLite schema and provenance contract

## Objective

Define and verify the owner-only host-local database, schema/application versioning, forward-only projection migrations, foreign keys, WAL/synchronous policy, one-writer lock, and source-file/record provenance.

## Dependencies and lane

- Internal dependency: `DEC-007`.
- Follow the external policy gates recorded for `IDX-001` in `docs/BACKLOG.md`.
- Use an isolated worktree; do not edit the canonical backlog from the child session.

## Required behavior

- Reuse canonical configuration, path, schema, receipt, workflow, and supervisor services.
- Preserve a complete rebuild path from authoritative artifacts.
- Record source provenance and bounded errors; fail closed on authority ambiguity.
- Add installed-product or invariant evidence at the public boundary appropriate to this ticket.

## Acceptance criteria

Schema creation is deterministic; unsupported/newer versions fail closed; deleting the database loses no authority; every projected row traces to source evidence.

## Non-targets

No shared/multi-host database, arbitrary SQL, raw body ingestion, or source-artifact mutation.

## Stop conditions

Stop on source mutation, raw sensitive-body duplication, arbitrary SQL exposure, hidden authority in the projection, unverifiable migration, or an unbounded scan/query surface.

## Completion evidence

Record changed paths, commands, exit codes, migration/schema versions, representative query output, source digests, test evidence, unresolved gates, and a structured completion handoff.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.
