# MSG-GATE-01 — independent two-way messaging review

**Task type:** independent gate; no backlog ownership  
**Design:** [Durable two-way messaging](../../../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md)

## Goal

Independently review the complete integrated two-way messaging implementation. This gate may correct a narrowly reproduced defect but may not add planned feature scope.

## Prerequisites

- `BKL-001`, `BKL-002`, and `MSG-001` through `MSG-007` are integrated with completion evidence.
- Every external `HARD-*` prerequisite named by the tickets is accepted.
- `DEC-001` is resolved and its SLO is represented in tests/configuration.

## Required review

- Apply `phase-gate-review` and `release-drift-auditor`.
- Inspect integrated code and durable artifacts, not only ticket reports.
- Run the complete installed-product acceptance suite and all available live tmux/executor journeys.
- Prove that per-session journals and sealed lifecycle evidence remain authoritative; the inbox is delivery authority only; wake signals are hints only.
- Suppress and duplicate wake signals, kill the supervisor at every durable boundary, delete/corrupt cursors, and attempt a second supervisor.
- Inject prompt-injection text, ANSI controls, shell metacharacters, oversized content, duplicate IDs, symlinks, traversal, and principal substitution.
- Verify fixed notification text contains no child-controlled content and no adapter treats pane/process liveness as application evidence.
- Verify delivery, acknowledgement, and action are distinct and restart-safe.
- Verify this pack owns only its declared backlog items and does not collide with hardening or MCP packs.
- Reconcile README, backlog, architecture, operations, command/help/man pages, diagrams, testing, security, skills, schemas, and release metadata.

## Writable paths

- Narrow fixes for defects reproduced during this review.
- Gate report, manifests, and directly affected documentation.

No unrelated cleanup or new features.

## Acceptance evidence

- Explicit accept or reject decision.
- Exact revisions and commands.
- Default and live test results with skips explained.
- Attack/restart matrix.
- No-wakeup latency evidence against `DEC-001`.
- Resource-bound measurements.
- Collision/drift audit results.
- Remaining risks classified as release blocker, follow-up, or accepted limitation.

## Stop conditions

Reject when correctness depends on wake delivery, a cursor advances before its durable effect, child text reaches orchestrator injection, principal identity is caller-selected, restart duplicates semantic actions, a second scheduler/state machine exists, or active pack ownership collides.
