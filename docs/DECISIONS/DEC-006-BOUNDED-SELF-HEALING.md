# DEC-006 — Bounded deterministic self-healing

- **Status:** decided
- **Date:** 2026-07-30
- **Scope:** local single-host run supervision, diagnosis, and remediation

## Decision

`agent-workflow` will implement self-correction as a deterministic, evidence-driven control loop around coding agents. Automatic behavior is selected from versioned rules in application code; the language model does not invent recovery policy or expand its own authority.

The loop is:

```text
observe → diagnose → authorize → act → verify → record
```

All observations, incidents, and remediation attempts are durable run evidence. Automatic actions must be bounded, idempotent, attributable, and independently verifiable.

## Authority rule

Automatic remediation may:

- reconstruct mutable projections from immutable authority;
- replay journals and rebuild cursors;
- capture bounded health and terminal evidence;
- send a bounded progress/status probe;
- retry a known transient action within an immutable budget;
- interrupt or restart only when an operator has explicitly enabled that rule.

Automatic remediation may not:

- grant filesystem, network, credential, model, or tool authority;
- answer a permission prompt;
- change acceptance criteria or budgets;
- accept, reject, merge, or delete work;
- hide, overwrite, or discard failed attempts;
- retry indefinitely or reuse the same run identity for a new attempt.

## Rationale

A fresh process heartbeat proves only that the runner is alive. It does not prove that the executor is making progress. Interactive terminal output, process/resource state, permission prompts, durable messages, and completion evidence must be observed separately so unattended runs can distinguish healthy work from a live-but-stalled process.

Deterministic control code is preferable to model-written recovery because it is testable, reviewable, replayable, and capable of failing closed.

## Consequences

### Positive

- Failures visible to a human watching tmux become durable and diagnosable.
- Recovery attempts preserve lineage and can be audited.
- The future root/team-lead hierarchy can reuse one supervision contract at each tier.
- Safety boundaries are explicit: self-healing never means self-authorizing.

### Costs

- Additional bounded journals consume local storage and require retention policy.
- Interactive terminal capture can contain sensitive content and therefore depends on HARD-006 for governed release.
- Portable resource telemetry is partial; unsupported fields remain `null`.
- Opt-in interruption and restart require careful live-host compatibility evidence.

## Implementation status

The current tree implements:

- process/resource health samples;
- separate liveness and semantic-progress signals;
- change-driven interactive terminal snapshots;
- permission, incident, remediation, and process-result evidence;
- a foreground supervisor;
- automatic status-projection repair;
- one bounded progress probe per configured allowance;
- opt-in interruption and lineage-preserving restart.

Governed sandbox enforcement, authenticated principals, retention/redaction policy, adaptive scheduling, hierarchical integration, and live compatibility remain sequenced in [`docs/BACKLOG.md`](../BACKLOG.md).
