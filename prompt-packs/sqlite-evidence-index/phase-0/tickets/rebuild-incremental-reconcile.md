# IDX-002 — deterministic rebuild and incremental reconciliation

## Objective

Implement full rebuild, changed-run reconciliation, active/archive discovery, stable no-follow reads, shared journal locks, atomic per-run replacement, stale-row pruning, corruption quarantine, and full source-digest verification.

## Dependencies and lane

- Internal dependency: `IDX-001`.
- Follow the external policy gates recorded for `IDX-002` in `docs/BACKLOG.md`.
- Use an isolated worktree; do not edit the canonical backlog from the child session.

## Required behavior

- Reuse canonical configuration, path, schema, receipt, workflow, and supervisor services.
- Preserve a complete rebuild path from authoritative artifacts.
- Record source provenance and bounded errors; fail closed on authority ambiguity.
- Add installed-product or invariant evidence at the public boundary appropriate to this ticket.

## Acceptance criteria

Deletion/rebuild equivalence, unchanged-run skip, source tamper detection, corrupt-run isolation, interrupt-safe retries, and archive indexing are proven through public behavior.

## Non-targets

No repair of corrupt authoritative evidence and no offset checkpoint authority.

## Stop conditions

Stop on source mutation, raw sensitive-body duplication, arbitrary SQL exposure, hidden authority in the projection, unverifiable migration, or an unbounded scan/query surface.

## Completion evidence

Record changed paths, commands, exit codes, migration/schema versions, representative query output, source digests, test evidence, unresolved gates, and a structured completion handoff.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.
