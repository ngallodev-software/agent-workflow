# agent-workflow backlog

This is the only task register for unfinished work. Design documents explain architecture and constraints; they do not maintain parallel checklists. Completed implementation detail belongs in Git history and [CHANGELOG.md](CHANGELOG.md).

## Rules

- Every active item has a stable ID, priority, state, and observable exit evidence.
- `done` means the behavior and evidence exist; completed items move to the history summary.
- `blocked` names the missing external prerequisite.
- `decision` requires explicit maintainer authorization before implementation.
- New features require an installed-product acceptance journey or an approved strict future specification.

## Now

| ID | Priority | State | Work and exit evidence | Reference |
|---|---|---|---|---|
| BKL-001 | P0 | ready | Add durable per-consumer message cursors and idempotent handling dispositions. Prove restart recovery, duplicate safety, and cursor advancement only after successful handling. | [Operations](docs/OPERATIONS.md#durable-messages) |
| BKL-002 | P0 | ready | Add executor-specific post-launch steering for detached runs. A running executor must consume a steer without restart and emit correlated delivered/applied/rejected evidence; terminal text or process liveness is not proof. | Strict future journey in `tests/future/test_late_steering_journey.py` |
| REL-001 | P0 | needs-decision | Select and add the project license, matching package metadata, and distribution policy. | [Public release readiness](docs/PUBLIC_RELEASE_READINESS.md#blocking-decisions) |
| REL-002 | P0 | blocked | Establish a real monitored vulnerability-reporting channel and update `SECURITY.md`. | [Public release readiness](docs/PUBLIC_RELEASE_READINESS.md#blocking-decisions) |
| REL-003 | P0 | ready | Define the supported Linux/Python/tmux/executor matrix and run live compatibility journeys on representative clean hosts. | [Testing](docs/TESTING.md#live-compatibility) |
| BKL-004 | P1 | ready | Run a controlled real-executor baseline/candidate cohort with pinned model, executor, environment, tools, cache policy, repetitions, exclusions, and sealed evidence. | [Evidence and evaluation](docs/EVIDENCE_AND_EVALUATION.md#cohort-comparison) |
| BKL-007 | P1 | ready | Add opt-in installer-owned host routing enforcement only for narrowly defined direct delegation commands, with preserved hooks and an audited break-glass path. | [Operations](docs/OPERATIONS.md#host-routing) |
| MCP-003 | P1 | ready | Add idempotent pack validation, worktree creation, bounded launch, workflow validate/start/status/resume, progress, ack, and steer tools through existing services. | [MCP server](docs/MCP_SERVER.md#planned-mutation-phase) and [`prompt-packs/mcp-server-next/`](prompt-packs/mcp-server-next/) |

## Blocked prerequisites

| ID | Priority | State | Missing input and exit evidence | Reference |
|---|---|---|---|---|
| BKL-010 | P1 | blocked | Supply a pinned browser-image digest, font manifest, and verified pre-seal browser/Inspect evidence bridge before implementing the visual priority-picker fixture. | [Evidence and evaluation](docs/EVIDENCE_AND_EVALUATION.md) |

## Decisions

| ID | Priority | State | Decision |
|---|---|---|---|
| DEC-001 | P0 | needs-decision | Set the durable-control service objective: storage/failure model, ordering scope, producer model, external-effect idempotency, and maximum no-wakeup latency. |
| DEC-002 | P1 | needs-decision | Set benchmark policy: first executors, billing meaning, cache role, replicate count/effect threshold, and treatment of interrupted or human-assisted trials. |
| DEC-003 | P2 | deferred | Authorize multi-host orchestration only after a measured single-host failure. Preserve replayable durable records as authority; prefer JetStream unless an existing Redis dependency is mandated. |
| DEC-MCP-HTTP | P2 | deferred | Authorize any non-stdio MCP transport only through a separate security ADR after local adoption evidence. |

## Deferred architecture

| ID | Priority | Trigger |
|---|---|---|
| ARC-001 | P2 | Add a transport-neutral notifier only after measured wakeup latency or operability requires it; replay remains mandatory. |
| ARC-002 | P3 | Add a reconstructable SQLite index only after JSONL replay/scan cost is measured as a problem. |
| ARC-003 | P3 | Add a multi-host broker, shared-artifact references, and cross-trust signing only after `DEC-003`. |
| MCP-004 | P2 | Add policy-gated review/disposition and interrupt/terminate tools after `MCP-003`; force kill remains excluded. |
| WF-006 | P2 | Consider evidence-derived routing recommendations only after comparable real-executor cohorts exist; no online learning or vector-memory dependency. |

## Completed history

| Release | Summary |
|---|---|
| 0.1.x | Worktrees, tmux lifecycle, durable state, prompt packs, evaluation, provider adapters, skills, and packaging foundations. |
| 0.2.0 | Workflow DAGs, approvals, result binding, aggregate receipts, templates, routing advice, and provider/trial evidence. |
| 0.2.1 | Authority, replay, locking, symlink, scorer-receipt, provider-accounting, and immutable-input hardening. |
| 0.2.2 | Acceptance-first installed-product tests, compact invariant matrices, strict future TDD journeys, CI, and public-documentation consolidation. |
