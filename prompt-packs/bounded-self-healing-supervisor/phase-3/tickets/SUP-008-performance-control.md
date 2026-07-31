# SUP-008 — evidence-derived performance control

## Objective

Use accepted comparable benchmark cohorts and supervisor evidence to detect regressions and deterministically narrow launch concurrency or select preapproved fallback policy.

## Dependencies and lane

- Depends on `SUP-007`, `SUP-006`, accepted `BKL-004`, and `HIER-007`.

## Required behavior

- Compare queue, active, blocked, idle, critical-path, token, cost, CPU, memory, IO, and retry evidence only across compatible cohorts.
- Apply static configured thresholds and hysteresis; no online learning or model-authored policy.
- Reduce concurrency or pause new launches under regression/pressure; never increase authority or cost ceilings automatically.
- Record every recommendation and action with provenance and verification.

## Acceptance criteria

Deterministic replay produces the same decision, false-positive safeguards are proven, and operator override is explicit and audited.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, skills, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant and installed-product journeys for every required behavior, including failure, replay/restart, and tamper paths. Run prompt-pack validation and the release-asset audit. Record exact commands, exit codes, durable evidence paths, and receipt references.

## Stop conditions

Stop and report rather than widening authority, weakening redaction or retention, making tmux/process state authoritative, adding unbounded evidence or retries, bypassing canonical services, inventing unsupported compatibility claims, or changing acceptance criteria to make the ticket pass.
