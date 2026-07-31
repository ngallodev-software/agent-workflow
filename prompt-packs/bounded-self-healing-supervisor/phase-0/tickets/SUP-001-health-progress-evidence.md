# SUP-001 — health, progress, terminal, and incident evidence

## Objective

Complete and verify the implemented bounded health evidence model. Preserve the
separation between supervisor heartbeat, executor liveness, semantic progress,
and known blocked states for interactive and non-interactive runs.

## Dependencies and lane

- Governed by decided `DEC-006`.
- Critical path; Phase 0 foundation.

## Required behavior

- Validate schemas and caps for health, terminal, permission, incident, process-result, and remediation artifacts.
- Prove interactive capture is change-driven, ANSI-cleaned, secret-redacted, and never execution authority.
- Prove heartbeat freshness cannot mask stale semantic progress.
- Preserve nulls for unsupported host metrics and record collector capability.
- Seal all terminal evidence through the canonical receipt path.

## Non-targets

No resource-limit enforcement, permission expansion, authenticated principal system, hierarchy, or online learning.

## Required tests and evidence

Focused invariant tests, installed tmux journey, truncation/tamper tests, source archive and checkout paths, pack validation, and release audit.

## Acceptance criteria

A reviewer can distinguish alive, progressing, blocked, stalled, orphaned, and terminal runs solely from bounded durable evidence.

## Stop conditions

Stop on unbounded transcript retention, secret leakage, heartbeat-as-progress, tmux-as-authority, or silent evidence loss.

## Writable scope

Limit changes to the modules, schemas, focused tests, documentation, man pages, skills, and fixtures directly required by this ticket. Preserve canonical launch, workflow, message, receipt, and policy services. Do not edit `docs/BACKLOG.md` from the child session.
