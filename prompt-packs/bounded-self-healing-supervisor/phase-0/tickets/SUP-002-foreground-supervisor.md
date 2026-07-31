# SUP-002 — foreground supervisor and bounded remediation

## Objective

Complete and verify the foregroundable deterministic supervisor, including replay, projection repair, incident deduplication, status probes, and explicitly opted-in interrupt/restart rules.

## Dependencies and lane

- Depends on `SUP-001`.
- Critical path; Phase 0 foundation.

## Required behavior

- Rebuild only reconstructable mutable projections from immutable authority.
- Persist remediation intent/outcome with stable rule IDs and idempotency keys.
- Enforce per-rule attempt ceilings and circuit-break after failure.
- Keep probe enabled by safe default; keep interrupt/restart disabled unless operator policy opts in.
- Verify every action from authoritative post-action evidence.

## Non-targets

No daemon, arbitrary model-written policy, authority widening, acceptance, merge, cleanup, or credential exposure.

## Required tests and evidence

Installed CLI once/run journeys, corrupt projection repair, missed wake replay, one-probe ceiling, opt-in interrupt/restart, crash/restart, and tamper tests.

## Acceptance criteria

Repeated supervisor cycles are idempotent, safe by default, and durably explain every proposed and performed action.

## Stop conditions

Stop on duplicate semantic actions, mutable-only authorization, unbounded retry, or any automated authority change.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, skills, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.
