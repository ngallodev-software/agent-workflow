# IDX-003 — typed operational projections

## Objective

Materialize normalized run, source, event, health, permission, incident, remediation, process, performance, workflow-node, and workflow-edge data with bounded summaries and curated views.

## Dependencies and lane

- Internal dependency: `IDX-001`.
- Follow the external policy gates recorded for `IDX-003` in `docs/BACKLOG.md`.
- Use an isolated worktree; do not edit the canonical backlog from the child session.

## Required behavior

- Reuse canonical configuration, path, schema, receipt, workflow, and supervisor services.
- Preserve a complete rebuild path from authoritative artifacts.
- Record source provenance and bounded errors; fail closed on authority ambiguity.
- Add installed-product or invariant evidence at the public boundary appropriate to this ticket.

## Acceptance criteria

Cross-run operational questions are answerable with indexed normalized fields while prompts, terminal/message bodies, output logs, credentials, and unrestricted provider payloads are absent.

## Non-targets

No dashboards, remote API, analytical export, or policy decisions from query rows.

## Stop conditions

Stop on source mutation, raw sensitive-body duplication, arbitrary SQL exposure, hidden authority in the projection, unverifiable migration, or an unbounded scan/query surface.

## Completion evidence

Record changed paths, commands, exit codes, migration/schema versions, representative query output, source digests, test evidence, unresolved gates, and a structured completion handoff.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.
