# SUP-004 — resource enforcement and backpressure

## Objective

Apply accepted `HARD-003` resource policy to launch and supervision, then use observed pressure only to narrow concurrency or stop new work.

## Dependencies and lane

- Depends on `SUP-GATE-0` and accepted `HARD-003`.
- May run in parallel with `SUP-003` and `SUP-005`.

## Required behavior

- Enforce configured CPU, memory, process, file-descriptor, wall-time, output, disk, and network boundaries where supported.
- Record effective controls and unsupported fields explicitly.
- Pause new launches and reduce approved concurrency under host pressure.
- Never raise resource ceilings automatically.
- Prove OOM/disk/output exhaustion classification and bounded recovery.

## Acceptance criteria

Installed journeys demonstrate effective limits, fail-closed unsupported policy, pressure backoff, and no authority widening.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, skills, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.

## Required tests and evidence

Add focused invariant and installed-product journeys for every required behavior, including failure, replay/restart, and tamper paths. Run prompt-pack validation and the release-asset audit. Record exact commands, exit codes, durable evidence paths, and receipt references.

## Stop conditions

Stop and report rather than widening authority, weakening redaction or retention, making tmux/process state authoritative, adding unbounded evidence or retries, bypassing canonical services, inventing unsupported compatibility claims, or changing acceptance criteria to make the ticket pass.
