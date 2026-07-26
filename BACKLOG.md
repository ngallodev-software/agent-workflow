# agent-workflow backlog

This is the only task register for unfinished work. Design documents explain architecture and constraints; they do not maintain parallel status checklists. Completed implementation detail belongs in Git history and [CHANGELOG.md](CHANGELOG.md).

The determinism and security work below is derived from the [feature determinism and security assessment](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md) and sequenced in the [hardening plan](docs/DETERMINISM_SECURITY_HARDENING_PLAN.md).

## Rules

- Every active item has a stable ID, priority, state, observable exit evidence, and one canonical owner.
- `done` means behavior and evidence exist; completed items move to the history summary.
- `blocked` names the missing prerequisite.
- `needs-decision` requires explicit maintainer authorization before implementation.
- New features require an installed-product acceptance journey or an approved strict future specification.
- Repository-owned prompt-pack tasks declare `backlog_id`. Exactly one active prompt pack may own a backlog item.
- Review-only tasks use `task_type: gate`, do not claim a backlog item, and may not implement new scope.
- Parallel agents use separate worktrees. Missing dependency edges permit concurrency; prose may not bypass manifest dependencies.
- Run the `release-drift-auditor` skill and `scripts/audit-release-assets.py` before every phase gate and archive.

## Active prompt-pack ownership

| Prompt pack | Canonical backlog ownership | Execution status |
|---|---|---|
| [`deterministic-enforcement-foundations`](prompt-packs/deterministic-enforcement-foundations/) | HARD-001, HARD-002, HARD-004, HARD-005 | Start now; phase-0 tickets run in parallel. |
| [`execution-isolation-and-secrets`](prompt-packs/execution-isolation-and-secrets/) | HARD-008, HARD-003, HARD-006 | Blocked until the foundations gate is accepted. |
| [`public-beta-trust-and-release`](prompt-packs/public-beta-trust-and-release/) | HARD-007, HARD-009, HARD-010, REL-003, REL-004 | Blocked until the first two packs are accepted. |
| [`mcp-server-next`](prompt-packs/mcp-server-next/) | MCP-003 | Blocked on HARD-004, HARD-005, and HARD-007. |
| [`orchestrator-two-way-messaging`](prompt-packs/orchestrator-two-way-messaging/) | BKL-001, BKL-002, MSG-001 through MSG-007 | Planning complete; phase 0 is blocked on DEC-001, HARD-002, and HARD-004. |

## Ready now

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| BKL-001 | P0 | High | ready | Add durable per-consumer message cursors and idempotent handling dispositions. Prove restart recovery, duplicate safety, and cursor advancement only after successful handling. | [Operations](docs/OPERATIONS.md#durable-messages) |
| BKL-002 | P0 | High | ready | Add executor-specific post-launch steering for detached runs. A running executor must consume a steer without restart and emit correlated delivered/applied/rejected evidence; terminal text or process liveness is not proof. | Strict future journey in `tests/future/test_late_steering_journey.py` |
| HARD-001 | P0 | Critical | ready | Replace ad hoc subprocess calls with one bounded process substrate: timeout, process groups, cancellation, capped/spooled output, sanitized environment, executable identity, and argv redaction. Migrate doctor, Git, runner, archive, probe, and evaluation call sites. | [Assessment F04-F06, F18-F20, F71](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#4-feature-and-component-inventory) |
| HARD-002 | P0 | Critical | ready | Make prompt packs, schemas, native jobs, and bounded paths content-complete and no-follow: reject symlinks/special files, manifest every accepted entry, fail on duplicate schema IDs, and remove resolve-before-validation gaps. | [Assessment F11, F34-F38, F87](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#10-source-observations-supporting-the-highest-priority-findings) |
| REL-001 | P0 | Critical | needs-decision | Select and add the project license, matching package metadata, and distribution policy. | [Public release readiness](docs/PUBLIC_RELEASE_READINESS.md#governance-and-compatibility-blockers) |
| REL-002 | P0 | Critical | blocked | Establish a real monitored vulnerability-reporting channel and update `SECURITY.md`. | [Public release readiness](docs/PUBLIC_RELEASE_READINESS.md#governance-and-compatibility-blockers) |

## Additional release follow-up

These items remain tracked separately from the hardening ownership above; they are release-evidence and local-CI follow-up, not alternate owners for HARD or MCP work.

| ID | Priority | State | Work and exit evidence | Reference |
|---|---|---|---|---|
| REL-005 | P1 | ready | Add automated release-blocker checks and durable release evidence: license/security-channel metadata, declared compatibility matrix, structured test results, SBOM, dependency lock, and build provenance. | [Release check audit](docs/RELEASE_CHECK_AUDIT.md#gap-analysis) |
| REL-006 | P1 | ready | Configure the local Jenkins job to trigger from commits to the local repository and verify that the trigger builds the matching master revision; the pipeline itself is already green. | [Release check audit](docs/RELEASE_CHECK_AUDIT.md#jenkins-verification) |
| REL-007 | P1 | ready | Run and record clean-machine install/uninstall evidence and a controlled real workflow/provider cohort before describing the project as publicly supported. | [Public release readiness](docs/PUBLIC_RELEASE_READINESS.md#governance-and-compatibility-blockers) |

## Blocked prerequisites

| ID | Priority | Risk | State | Missing prerequisite and exit evidence | Reference |
|---|---|---:|---|---|---|
| MSG-001 | P0 | Critical | blocked | After DEC-001, HARD-002, and HARD-004, add an immutable orchestrator registry and append-only aggregate inbox that normalizes verified child events without replacing per-session lifecycle authority. | [Messaging design](docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#add-one-shared-orchestrator-inbox) |
| MSG-002 | P0 | Critical | blocked | After BKL-001, MSG-001, HARD-001, and HARD-008, add a foregroundable single-writer supervisor, shared hashed tmux wake channel, periodic replay fallback, bounded fairness, and cursor-after-commit fan-in. | [Messaging design](docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#use-one-shared-wake-channel) |
| MSG-003 | P0 | Critical | blocked | After MSG-002, HARD-004, HARD-006, HARD-007, and HARD-008, add fixed-format orchestrator wake/resume adapters that receive opaque event IDs only and cannot inject child-controlled content. | [Messaging design](docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#the-supervisor-must-wake-the-orchestrator-safely) |
| MSG-004 | P1 | High | blocked | After MSG-002, MSG-003, MSG-005, and HARD-007, distinguish durable event delivery, orchestrator application acknowledgement, and linked scheduling/lifecycle action evidence through shared services. | [Messaging design](docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#acknowledgement-model) |
| MSG-005 | P1 | Critical | blocked | After BKL-001, MSG-001, and MSG-002, reconstruct delivery after supervisor/orchestrator restart, missed or duplicate signals, corrupt cursors, and every cursor/inbox crash window without duplicate semantic effects. | [Messaging design](docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#failure-and-restart-behavior) |
| MSG-006 | P1 | Critical | blocked | After the integrated messaging implementation and HARD-001/HARD-002/HARD-004/HARD-006/HARD-007/HARD-008, harden identity, bounds, redaction, no-follow storage, duplicate IDs, prompt injection, notification templates, resource use, and supervisor ownership adversarially. | [Messaging design](docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#security-requirements) |
| MSG-007 | P1 | High | blocked | After MSG-001 through MSG-005 and BKL-002, add installed-wheel completion/wakeup/restart/action journeys plus opt-in real tmux and supported executor compatibility tests; keep low-level tests limited to compact security/replay matrices. | [Messaging design](docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#acceptance-strategy) |
| HARD-004 | P0 | Critical | blocked | After HARD-001 and HARD-002, add one immutable launch contract consumed by runners and collectors; remove remaining `status.json` authority, and return the digest of the exact receipt verified. | [Assessment F17, F24, F68](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#5-guidance-that-should-become-deterministic-enforcement) |
| HARD-005 | P0 | Critical | blocked | After HARD-002, make MCP reads metadata-minimal, no-follow, bounded, descriptor-stable, and error-normalized. Full message bodies require a separately authorized/redacted capability. | [Assessment F83-F88](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#46-mcp-adapter) |
| HARD-008 | P1 | High | blocked | After HARD-001, validate config ownership/mode, reject unknown policy keys, record executable version/path/digest, sanitize Git/executor environments, and separate compatibility data from hard-coded defaults. | [Assessment F03-F06, F15, F20](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#41-entry-points-configuration-host-integration-and-release-tooling) |
| HARD-003 | P0 | Critical | blocked | After HARD-001, HARD-002, and HARD-008, enforce allowed writes, home/credential isolation, network default-deny, and CPU/memory/time/output limits for native jobs and evaluation/acceptance commands. Post-run scope comparison remains evidence, not the barrier. | [Assessment F39-F42, F69-F73](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#5-guidance-that-should-become-deterministic-enforcement) |
| HARD-006 | P1 | High | blocked | After HARD-001 and HARD-005, add content classification, redaction, explicit sensitive-content opt-in, and retention/deletion policy for prompts, argv, logs, messages, provider events, telemetry, and exported reports. | [Assessment F44-F47, F64, F81-F85](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#7-security-posture-by-trust-boundary) |
| HARD-007 | P1 | Critical | blocked | After HARD-004, replace caller-selected actor labels with authenticated principals for review, acceptance, steering, and future MCP mutation. Enforce independent-review policy from immutable identity evidence. | [Assessment F48-F52, F89](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#5-guidance-that-should-become-deterministic-enforcement) |
| HARD-009 | P1 | High | blocked | After HARD-003 through HARD-008, generate command/man/schema/service inventories from code, enforce backlog-to-pack ownership, detect stale docs/skills/diagrams/future tests, and make drift audit a release gate. | [Assessment F01-F02, F09-F10, F90-F96](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#8-public-release-direction) |
| HARD-010 | P1 | High | blocked | After FOUND-GATE-01 and ISO-GATE-01, add locked dependencies, SBOM generation, wheel/source provenance, independent reproducibility checks, and authenticated release signing/attestation against the integrated hardened tree. | [Assessment F13-F14](docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#4-feature-and-component-inventory) |
| REL-003 | P0 | High | blocked | After HARD-008, define the supported Linux/Python/tmux/executor matrix and run opt-in live compatibility journeys on representative clean hosts. | [Testing](docs/TESTING.md#live-compatibility) |
| BKL-004 | P1 | High | blocked | After HARD-003, HARD-006, and REL-003, run a controlled real-executor baseline/candidate cohort with pinned model, executor, environment, tools, cache policy, repetitions, exclusions, and sealed evidence. | [Evidence and evaluation](docs/EVIDENCE_AND_EVALUATION.md#cohort-comparison) |
| BKL-007 | P1 | High | blocked | After HARD-001 and HARD-008, add opt-in installer-owned host routing enforcement only for narrowly defined direct delegation commands, with preserved hooks and an audited break-glass path. | [Operations](docs/OPERATIONS.md#host-routing) |
| MCP-003 | P1 | Critical | blocked | After HARD-004, HARD-005, and HARD-007, add idempotent pack validation, worktree creation, bounded launch, workflow validate/start/status/resume, progress, ack, and steer tools through existing services. | [MCP server](docs/MCP_SERVER.md#planned-mutation-phase) and [`mcp-server-next`](prompt-packs/mcp-server-next/) |
| REL-004 | P1 | Critical | blocked | After all P0 HARD items, HARD-010, REL-001, REL-002, and REL-003, execute the public-preview gate: clean-source build/install/uninstall, signed artifacts, drift audit, live compatibility, threat-model review, and explicit go/no-go record. | [Public release readiness](docs/PUBLIC_RELEASE_READINESS.md#release-gate) |
| BKL-010 | P1 | Medium | blocked | Supply a pinned browser-image digest, font manifest, and verified pre-seal browser/Inspect evidence bridge before implementing the visual priority-picker fixture. | [Evidence and evaluation](docs/EVIDENCE_AND_EVALUATION.md) |

## Decisions

| ID | Priority | State | Decision |
|---|---|---|---|
| DEC-001 | P0 | needs-decision | Set the durable-control service objective: storage/failure model, ordering scope, producer model, external-effect idempotency, and maximum no-wakeup latency. |
| DEC-002 | P1 | needs-decision | Set benchmark policy: first executors, billing meaning, cache role, replicate count/effect threshold, and treatment of interrupted or human-assisted trials. |
| DEC-003 | P2 | deferred | Authorize multi-host orchestration only after a measured single-host failure. Preserve replayable durable records as authority; prefer JetStream unless an existing Redis dependency is mandated. |
| DEC-MCP-HTTP | P2 | deferred | Authorize any non-stdio MCP transport only through a separate security ADR after local adoption evidence. |

## Deferred architecture

These existing items already own the assessment's P2 recommendations. The hardening packs must not create competing tickets for them.

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
| 0.2.2 maintenance | Jenkins local pipeline now provisions an isolated Python environment, installs build/test dependencies, avoids stale workspace virtualenvs, builds and locally installs the wheel, and passed build #16 with `35 passed, 2 skipped, 1 xfailed`. |
