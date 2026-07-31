# IDX-006 — privacy-governed analytical exports

## Objective

After HARD-006/SUP-003 and comparable evidence gates, define approved fields and produce immutable Parquet or equivalent analytical snapshots with provenance, retention, deletion, and cohort semantics.

## Dependencies and lane

- Internal dependency: `IDX-GATE-1`.
- Follow the external policy gates recorded for `IDX-006` in `docs/BACKLOG.md`.
- Use an isolated worktree; do not edit the canonical backlog from the child session.

## Required behavior

- Reuse canonical configuration, path, schema, receipt, workflow, and supervisor services.
- Preserve a complete rebuild path from authoritative artifacts.
- Record source provenance and bounded errors; fail closed on authority ambiguity.
- Add installed-product or invariant evidence at the public boundary appropriate to this ticket.

## Acceptance criteria

Exports are reproducible, privacy-classified, digest-bound, free of prohibited bodies, and consumable by offline analytical tools without changing run authority.

## Non-targets

No remote multi-user query service, no implicit currency combination, and no export before privacy approval.

## Stop conditions

Stop on source mutation, raw sensitive-body duplication, arbitrary SQL exposure, hidden authority in the projection, unverifiable migration, or an unbounded scan/query surface.

## Completion evidence

Record changed paths, commands, exit codes, migration/schema versions, representative query output, source digests, test evidence, unresolved gates, and a structured completion handoff.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.
