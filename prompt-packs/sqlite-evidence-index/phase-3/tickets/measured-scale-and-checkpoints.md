# IDX-007 — measured scale and reconstructable journal checkpoints

## Objective

Collect representative scale evidence and, only when justified, add byte-offset/sequence checkpoints, migration compatibility, bounded rebuild performance, and declared capacity envelopes.

## Dependencies and lane

- Internal dependency: `IDX-GATE-2`.
- Follow the external policy gates recorded for `IDX-007` in `docs/BACKLOG.md`.
- Use an isolated worktree; do not edit the canonical backlog from the child session.

## Required behavior

- Reuse canonical configuration, path, schema, receipt, workflow, and supervisor services.
- Preserve a complete rebuild path from authoritative artifacts.
- Record source provenance and bounded errors; fail closed on authority ambiguity.
- Add installed-product or invariant evidence at the public boundary appropriate to this ticket.

## Acceptance criteria

Published evidence covers run/event counts, database size, sync/rebuild/query latency, interruption recovery, truncation/rotation handling, and rebuild equivalence. Checkpoints can be discarded and reconstructed.

## Non-targets

No speculative distributed database, no claim unsupported by measured fixtures, and no checkpoint as event authority.

## Stop conditions

Stop on source mutation, raw sensitive-body duplication, arbitrary SQL exposure, hidden authority in the projection, unverifiable migration, or an unbounded scan/query surface.

## Completion evidence

Record changed paths, commands, exit codes, migration/schema versions, representative query output, source digests, test evidence, unresolved gates, and a structured completion handoff.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.
