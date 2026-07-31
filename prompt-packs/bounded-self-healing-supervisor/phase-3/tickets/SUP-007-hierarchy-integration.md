# SUP-007 — root and team-lead supervision integration

## Objective

Integrate the accepted supervisor into the root-orchestrator → team-lead → worker hierarchy without creating an alternate authority or scheduler.

## Dependencies and lane

- Depends on `SUP-GATE-2`, `HIER-005`, and `HIER-006`.

## Required behavior

- Team leads supervise only delegated workers and local budgets.
- The root supervises team leads, cross-team dependencies, and global capacity.
- Escalations preserve authenticated principal, incident, remediation, and retry lineage.
- Lost windows/panes are reconstructed as presentation; verified processes and durable records remain authority.

## Acceptance criteria

A sealed two-team journey proves local repair, root escalation, restart recovery, and no cross-team capability leakage.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, skills, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant and installed-product journeys for every required behavior, including failure, replay/restart, and tamper paths. Run prompt-pack validation and the release-asset audit. Record exact commands, exit codes, durable evidence paths, and receipt references.

## Stop conditions

Stop and report rather than widening authority, weakening redaction or retention, making tmux/process state authoritative, adding unbounded evidence or retries, bypassing canonical services, inventing unsupported compatibility claims, or changing acceptance criteria to make the ticket pass.
