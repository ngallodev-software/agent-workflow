# SUP-005 — authenticated permission and remediation principals

## Objective

Apply accepted `HARD-007` principal identity and authorization to steering, permission decisions, remediation, review, and escalation.

## Dependencies and lane

- Depends on `SUP-GATE-0` and accepted `HARD-007`.
- May run in parallel with `SUP-003` and `SUP-004`.

## Required behavior

- Bind every action to an authenticated principal and immutable delegation policy.
- Distinguish operator, root orchestrator, team lead, worker, and system supervisor authority.
- Reject replay, substitution, and privilege-escalation attempts.
- Require human approval for any permission, credential, acceptance, merge, or policy expansion.

## Acceptance criteria

Tamper and impersonation tests prove that automatic remediation can only narrow or exercise preauthorized capabilities.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, skills, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant and installed-product journeys for every required behavior, including failure, replay/restart, and tamper paths. Run prompt-pack validation and the release-asset audit. Record exact commands, exit codes, durable evidence paths, and receipt references.

## Stop conditions

Stop and report rather than widening authority, weakening redaction or retention, making tmux/process state authoritative, adding unbounded evidence or retries, bypassing canonical services, inventing unsupported compatibility claims, or changing acceptance criteria to make the ticket pass.
