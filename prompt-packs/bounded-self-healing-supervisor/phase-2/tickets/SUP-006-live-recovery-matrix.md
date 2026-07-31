# SUP-006 — installed live compatibility and recovery matrix

## Objective

Prove the accepted supervisor on supported hosts, tmux versions, packaging paths, and every executor capability the project claims.

## Dependencies and lane

- Depends on `SUP-GATE-1`, accepted `REL-003`, and supported compatibility policy.

## Required behavior

- Exercise interactive permission waits, no-progress stalls, terminal loss, process death, missed wakeups, corrupt cursors/projections, transient provider failures, output exhaustion, and restart.
- Verify exact evidence and remediation behavior after supervisor and orchestrator restart.
- Publish machine-readable compatibility evidence with versions and unavailable reasons.

## Acceptance criteria

The installed-product matrix passes on every claimed combination; unsupported combinations fail closed and are not marketed as supported.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, skills, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant and installed-product journeys for every required behavior, including failure, replay/restart, and tamper paths. Run prompt-pack validation and the release-asset audit. Record exact commands, exit codes, durable evidence paths, and receipt references.

## Stop conditions

Stop and report rather than widening authority, weakening redaction or retention, making tmux/process state authoritative, adding unbounded evidence or retries, bypassing canonical services, inventing unsupported compatibility claims, or changing acceptance criteria to make the ticket pass.
