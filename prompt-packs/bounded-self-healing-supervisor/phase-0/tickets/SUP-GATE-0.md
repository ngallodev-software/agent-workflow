# SUP-GATE-0 — phase 0 independent review

Review only. Verify the phase against `DEC-006`, the architecture, security
boundaries, durable evidence, attempt ceilings, replay/idempotency, installed
journeys, documentation, and release drift. Do not implement new scope.

## Dependencies and lane

- Depends on SUP-002.
- Acceptance is required before the next phase.

## Required tests and evidence

Run the focused acceptance/invariant matrix, prompt-pack validation, release
asset audit, documentation/skill drift checks, and applicable live host tests.
Record exact commands and exit codes.

## Acceptance criteria

Issue an evidence-backed accept or reject decision for every ticket and design
invariant. Unverified pane text, mutable status, or process liveness is not
acceptance evidence.

## Stop conditions

Reject on authority widening, secret leakage, unbounded evidence or retries,
missing authenticated action, duplicate semantic effects, stale documentation,
or unsupported compatibility claims.

## Writable scope

Review reports and evidence artifacts only. Do not implement new behavior or edit the canonical backlog from the gate session.
