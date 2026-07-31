# IDX-004 — public CLI, help, man, and documentation surfaces

## Objective

Deliver status/sync/rebuild/verify/query commands, fixed parameterized filters, parser-derived catalog/completion support, man pages, README, architecture, operations, security, testing, and evidence documentation.

## Dependencies and lane

- Internal dependency: `IDX-GATE-0`.
- Follow the external policy gates recorded for `IDX-004` in `docs/BACKLOG.md`.
- Use an isolated worktree; do not edit the canonical backlog from the child session.

## Required behavior

- Reuse canonical configuration, path, schema, receipt, workflow, and supervisor services.
- Preserve a complete rebuild path from authoritative artifacts.
- Record source provenance and bounded errors; fail closed on authority ambiguity.
- Add installed-product or invariant evidence at the public boundary appropriate to this ticket.

## Acceptance criteria

Installed-wheel commands are discoverable, machine-readable, bounded, truthful about freshness, and recover cleanly after database deletion.

## Non-targets

No arbitrary SQL console and no hidden background daemon.

## Stop conditions

Stop on source mutation, raw sensitive-body duplication, arbitrary SQL exposure, hidden authority in the projection, unverifiable migration, or an unbounded scan/query surface.

## Completion evidence

Record changed paths, commands, exit codes, migration/schema versions, representative query output, source digests, test evidence, unresolved gates, and a structured completion handoff.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.
