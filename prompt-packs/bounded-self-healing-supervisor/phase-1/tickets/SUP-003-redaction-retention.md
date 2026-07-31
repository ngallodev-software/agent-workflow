# SUP-003 — evidence redaction, retention, and export policy

## Objective

Apply accepted `HARD-006` policy to terminal, permission, health, incident, and remediation evidence without destroying diagnostic usefulness.

## Dependencies and lane

- Depends on `SUP-GATE-0` and accepted `HARD-006`.
- May run in parallel with `SUP-004` and `SUP-005`.

## Required behavior

- Define field-level sensitivity, redaction, retention class, export, and deletion rules.
- Prevent credentials, uncontrolled absolute paths, prompts, and terminal history from leaking into receipts or reports.
- Preserve digests, categories, relative targets, and bounded excerpts sufficient for diagnosis.
- Add retention/cleanup evidence without deleting sealed release/legal-hold artifacts.

## Acceptance criteria

Adversarial fixtures prove useful incident diagnosis with no prohibited data in journals, archives, reports, or console output.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, skills, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant and installed-product journeys for every required behavior, including failure, replay/restart, and tamper paths. Run prompt-pack validation and the release-asset audit. Record exact commands, exit codes, durable evidence paths, and receipt references.

## Stop conditions

Stop and report rather than widening authority, weakening redaction or retention, making tmux/process state authoritative, adding unbounded evidence or retries, bypassing canonical services, inventing unsupported compatibility claims, or changing acceptance criteria to make the ticket pass.
