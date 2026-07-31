# IDX-005 — supervisor synchronization and index health

## Objective

Integrate incremental indexing after each foreground supervisor cycle by default, report index errors without suppressing health supervision, expose freshness/error state, and keep one-writer semantics.

## Dependencies and lane

- Internal dependency: `IDX-GATE-0`.
- Follow the external policy gates recorded for `IDX-005` in `docs/BACKLOG.md`.
- Use an isolated worktree; do not edit the canonical backlog from the child session.

## Required behavior

- Reuse canonical configuration, path, schema, receipt, workflow, and supervisor services.
- Preserve a complete rebuild path from authoritative artifacts.
- Record source provenance and bounded errors; fail closed on authority ambiguity.
- Add installed-product or invariant evidence at the public boundary appropriate to this ticket.

## Acceptance criteria

A supervisor cycle updates changed evidence, remains useful when indexing fails, and never derives an authority-changing action solely from SQLite.

## Non-targets

No mandatory long-lived database service or automatic source repair.

## Stop conditions

Stop on source mutation, raw sensitive-body duplication, arbitrary SQL exposure, hidden authority in the projection, unverifiable migration, or an unbounded scan/query surface.

## Completion evidence

Record changed paths, commands, exit codes, migration/schema versions, representative query output, source digests, test evidence, unresolved gates, and a structured completion handoff.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.
