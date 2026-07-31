# IDX-GATE-0 — independent phase review

## Review scope

Independently verify every implementation dependency in this phase against `DEC-007`, the SQLite architecture, the canonical backlog, public CLI behavior, source provenance, security/privacy exclusions, rebuildability, and release drift.

## Mandatory checks

- Rebuild from a deleted database and compare indexed results.
- Verify SQLite integrity, foreign keys, schema/application versions, and full source digests.
- Confirm corrupt projections are disposable and corrupt source evidence fails closed.
- Inspect the database for prohibited raw terminal, prompt, message, log, or credential content.
- Run focused tests, installed-wheel journeys where dependencies permit, pack validation, and release-asset audit.
- Reject any claim not supported on the tested host/executor matrix.

## Authority

This is review-only. Do not implement missing behavior. Reject or block with exact evidence and follow-up ownership.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.

## Acceptance criteria

Accept only when every dependency has complete source-provenance, rebuild, security-exclusion, installed-product, and release-drift evidence with no authority ambiguity.

## Stop conditions

Reject on source mutation, hidden projection authority, prohibited raw content, unverifiable migration, stale documentation, or unsupported performance/compatibility claims.
