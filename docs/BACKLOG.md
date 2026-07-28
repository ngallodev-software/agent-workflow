# agent-workflow backlog

This is the only task register for unfinished work. Design documents explain architecture and constraints; they do not maintain parallel status checklists. Completed implementation detail belongs in Git history and [CHANGELOG.md](CHANGELOG.md).

The determinism and security work below is derived from the [feature determinism and security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md) and sequenced in the [hardening plan](DETERMINISM_SECURITY_HARDENING_PLAN.md).

## Rules

- Every active item has a stable ID, priority, state, observable exit evidence, and one canonical owner.
- `done` means behavior and evidence exist; completed items move to the history summary.
- `in-review` means the implementation is integrated but shared acceptance and phase-gate evidence remain open.
- `blocked` names the missing prerequisite.
- `needs-decision` requires explicit maintainer authorization before implementation.
- New features require an installed-product acceptance journey or an approved strict future specification.
- Repository-owned prompt-pack tasks declare `backlog_id`. Exactly one active prompt pack may own a backlog item.
- Review-only tasks use `task_type: gate`, do not claim a backlog item, and may not implement new scope.
- Parallel agents use separate worktrees. Missing dependency edges permit concurrency; prose may not bypass manifest dependencies.
- Run the `release-drift-auditor` skill and `scripts/audit-release-assets.py` before every phase gate and archive.

## Active prompt-pack ownership

| Prompt pack | Canonical backlog ownership | Execution status |
| --- | --- | --- |
| [`deterministic-enforcement-foundations`](../prompt-packs/deterministic-enforcement-foundations/) | HARD-001, HARD-002, HARD-004, HARD-005 | Implementations integrated for HARD-001, HARD-002, HARD-004, and HARD-005; FOUND-GATE-01 remains rejected pending shared acceptance. |
| [`execution-isolation-and-secrets`](../prompt-packs/execution-isolation-and-secrets/) | HARD-008, HARD-003, HARD-006 | Blocked until the foundations gate is accepted. |
| [`public-beta-trust-and-release`](../prompt-packs/public-beta-trust-and-release/) | HARD-007, HARD-009, HARD-010, REL-003, REL-004 | Blocked until the first two packs are accepted. |
| [`mcp-server-next`](../prompt-packs/mcp-server-next/) | MCP-003 | Blocked on HARD-004, HARD-005, and HARD-007; future mutations must preserve the current parser-derived capability/catalog resources and launch-contract v2 command-context parity. |
| [`orchestrator-two-way-messaging`](../prompt-packs/orchestrator-two-way-messaging/) | BKL-001, BKL-002, MSG-001 through MSG-007 | BKL-001 accepted with sealed evidence; remaining phase 0 work is blocked on accepted HARD-002 and HARD-004 authority work. |
| [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/) | PROC-001 through PROC-005 | Planning complete; phase 0 tasks are ready for isolated implementation. |
| [`chatgpt-sealed-run-assessment`](../prompt-packs/chatgpt-sealed-run-assessment/) | CHATGPT-EVAL-001, CHATGPT-TDD-001 | Assessment and future-TDD artifacts completed; future journeys remain strict expected failures and do not unblock planned runtime work. |

## Ready now

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| BKL-002 | P0 | High | ready | Add executor-specific post-launch steering for detached runs. A running executor must consume a steer without restart and emit correlated delivered/applied/rejected evidence; terminal text or process liveness is not proof. | Strict future journey in `tests/future/test_late_steering_journey.py` |
| PROC-001 | P0 | High | ready | Resolve launch prerequisites from live lifecycle receipts and immutable evidence, not stale status projections; failed preflight must not create a misleading running session. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-001-authoritative-preflight.md) |
| PROC-002 | P0 | Critical | ready | Add a durable progress/ack control-plane handshake with correlated delivery, application, rejection, and unavailable outcomes; read-only parent projections must not be communication targets. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-002-control-handshake.md) |
| PROC-003 | P1 | High | ready | Detect silent panes independently from heartbeat, log, and executor-event growth; preserve evidence through safe terminate/retry lineage. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-003-run-observability.md) |
| PROC-004 | P0 | Critical | ready | Reject placeholder-only completion handoffs and require substantive identity, scope, commands, exit codes, acceptance, and unresolved-evidence fields. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-004-completion-validation.md) |
| PROC-005 | P1 | High | ready | Align steering, templates, hooks/reminders, and recovery references with the enforced launch, communication, observation, completion, and closeout pattern. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-1/tickets/PROC-005-operator-enforcement.md) |
| REL-001 | P0 | Critical | needs-decision | Select and add the project license, matching package metadata, and distribution policy. | [Public release readiness](PUBLIC_RELEASE_READINESS.md#governance-and-compatibility-blockers) |
| REL-002 | P0 | Critical | blocked | Establish a real monitored vulnerability-reporting channel and update `SECURITY.md`. | [Public release readiness](PUBLIC_RELEASE_READINESS.md#governance-and-compatibility-blockers) |

## Additional release follow-up

These items remain tracked separately from the hardening ownership above; they are release-evidence and local-CI follow-up, not alternate owners for HARD or MCP work.

| ID | Priority | State | Work and exit evidence | Reference |
|---|---|---|---|---|
| REL-005 | P1 | completed | Added schema-validated release policy and direct dependency lock, JUnit evidence, CycloneDX SBOM, source/build provenance, artifact digests, and an enforceable blocker summary. | [Release evidence](RELEASE_EVIDENCE.md) |
| REL-006 | P1 | ready | Configure the local Jenkins job to trigger from commits to the local repository and verify that the trigger builds the matching master revision; the pipeline itself is already green. | [Release check audit](RELEASE_CHECK_AUDIT.md#jenkins-verification) |
| REL-007 | P1 | ready | Run and record clean-machine install/uninstall evidence and a controlled real workflow/provider cohort before describing the project as publicly supported. | [Public release readiness](PUBLIC_RELEASE_READINESS.md#governance-and-compatibility-blockers) |
| CHATGPT-EVAL-001 | P1 | High | completed | Added evidence-first exported-run assessment, truthful ledger evaluation state, and focused invariant coverage. | [Sealed foundation evidence](EVIDENCE_SEALED_FOUNDATION_RUNS_20260726.md) |

## Integrated pending phase gate

| ID | Priority | Risk | State | Integrated implementation and remaining exit evidence | Reference |
|---|---|---:|---|---|---|
| BKL-001 | P0 | High | completed | Integrated in `63e953b`; sealed verification run `bkl-001-completion-verification-20260728-r7` passed focused tests, evidence fidelity, writable scope, report/collection/ledger checks, and lifecycle acceptance. | [Evidence recovery and final acceptance](BKL-001_EVIDENCE_RECOVERY_20260728.md) |
| HARD-001 | P0 | Critical | completed | Integrated in `91f5ff3`; sealed implementation run passed its focused process/acceptance criteria and was independently accepted in lifecycle receipt `deterministic-foundations-hard-001-rerun-20260726`. The aggregate foundation gate remains separate and rejected. | [Sealed evidence](EVIDENCE_SEALED_FOUNDATION_RUNS_20260726.md) |
| HARD-002 | P0 | Critical | completed | Integrated in `5d689b6`; sealed path/schema criteria passed, with filesystem-socket coverage unavailable on this host, and was independently accepted in lifecycle receipt `deterministic-foundations-hard-002-rerun-20260726`. The aggregate foundation gate remains separate and rejected. | [Sealed evidence](EVIDENCE_SEALED_FOUNDATION_RUNS_20260726.md) |
| HARD-004 | P0 | Critical | in-review | Integrated in the current authority implementation, but the exported run lacks complete portable lifecycle/evaluation evidence and an independent accepted disposition. The shared foundation gate remains open; MSG-001 must not start. | [2026-07-28 blocker-clearance review](TWO_WAY_MESSAGING_BLOCKER_CLEARANCE_20260728.md#hard-004) |
| HARD-005 | P0 | Critical | in-review | Integrated in `8fde4c3`; metadata/no-follow criteria passed, but installed-wheel stdio MCP coverage and an independent accepted disposition remain unverified. Re-run in a dependency-enabled environment, then rerun the shared gate. | [2026-07-28 blocker-clearance review](TWO_WAY_MESSAGING_BLOCKER_CLEARANCE_20260728.md#hard-005) |

## Planned TDD follow-up

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| CHATGPT-TDD-001 | P1 | High | completed | Added strict future journeys for HARD-004, MSG-005, BKL-004, and MCP-003/HARD-007; all remain honest expected failures pending implementation and accepted gates. | [Future tests](../tests/future/) |

## Blocked prerequisites

| ID | Priority | Risk | State | Missing prerequisite and exit evidence | Reference |
|---|---|---:|---|---|---|
| MSG-001 | P0 | Critical | blocked | After DEC-001, HARD-002, and HARD-004, add an immutable orchestrator registry and append-only aggregate inbox that normalizes verified child events without replacing per-session lifecycle authority. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#add-one-shared-orchestrator-inbox) |
| MSG-002 | P0 | Critical | blocked | After BKL-001, MSG-001, HARD-001, and HARD-008, add a foregroundable single-writer supervisor, shared hashed tmux wake channel, periodic replay fallback, bounded fairness, and cursor-after-commit fan-in. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#use-one-shared-wake-channel) |
| MSG-003 | P0 | Critical | blocked | After MSG-002, HARD-004, HARD-006, HARD-007, and HARD-008, add fixed-format orchestrator wake/resume adapters that receive opaque event IDs only and cannot inject child-controlled content. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#the-supervisor-must-wake-the-orchestrator-safely) |
| MSG-004 | P1 | High | blocked | After MSG-002, MSG-003, MSG-005, and HARD-007, distinguish durable event delivery, orchestrator application acknowledgement, and linked scheduling/lifecycle action evidence through shared services. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#acknowledgement-model) |
| MSG-005 | P1 | Critical | blocked | After BKL-001, MSG-001, and MSG-002, reconstruct delivery after supervisor/orchestrator restart, missed or duplicate signals, corrupt cursors, and every cursor/inbox crash window without duplicate semantic effects. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#failure-and-restart-behavior) |
| MSG-006 | P1 | Critical | blocked | After the integrated messaging implementation and HARD-001/HARD-002/HARD-004/HARD-006/HARD-007/HARD-008, harden identity, bounds, redaction, no-follow storage, duplicate IDs, prompt injection, notification templates, resource use, and supervisor ownership adversarially. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#security-requirements) |
| MSG-007 | P1 | High | blocked | After MSG-001 through MSG-005 and BKL-002, add installed-wheel completion/wakeup/restart/action journeys plus opt-in real tmux and supported executor compatibility tests; keep low-level tests limited to compact security/replay matrices. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#acceptance-strategy) |
| HARD-008 | P1 | High | blocked | After HARD-001, validate config ownership/mode, reject unknown policy keys, record executable version/path/digest, sanitize Git/executor environments, and separate compatibility data from hard-coded defaults. | [Assessment F03-F06, F15, F20](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#41-entry-points-configuration-host-integration-and-release-tooling) |
| HARD-003 | P0 | Critical | blocked | After HARD-001, HARD-002, and HARD-008, enforce allowed writes, home/credential isolation, network default-deny, and CPU/memory/time/output limits for native jobs and evaluation/acceptance commands. Post-run scope comparison remains evidence, not the barrier. | [Assessment F39-F42, F69-F73](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#5-guidance-that-should-become-deterministic-enforcement) |
| HARD-006 | P1 | High | blocked | After HARD-001 and HARD-005, add content classification, redaction, explicit sensitive-content opt-in, and retention/deletion policy for prompts, argv, logs, messages, provider events, telemetry, and exported reports. | [Assessment F44-F47, F64, F81-F85](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#7-security-posture-by-trust-boundary) |
| HARD-007 | P1 | Critical | blocked | After HARD-004, replace caller-selected actor labels with authenticated principals for review, acceptance, steering, and future MCP mutation. Enforce independent-review policy from immutable identity evidence. | [Assessment F48-F52, F89](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#5-guidance-that-should-become-deterministic-enforcement) |
| HARD-009 | P1 | High | blocked | After HARD-003 through HARD-008, generate command/man/schema/service inventories from code, enforce backlog-to-pack ownership, detect stale docs/skills/diagrams/future tests, and make drift audit a release gate. | [Assessment F01-F02, F09-F10, F90-F96](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#8-public-release-direction) |
| HARD-010 | P1 | High | blocked | After FOUND-GATE-01 and ISO-GATE-01, add locked dependencies, SBOM generation, wheel/source provenance, independent reproducibility checks, and authenticated release signing/attestation against the integrated hardened tree. | [Assessment F13-F14](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#4-feature-and-component-inventory) |
| REL-003 | P0 | High | blocked | After HARD-008, define the supported Linux/Python/tmux/executor matrix and run opt-in live compatibility journeys on representative clean hosts. | [Testing](TESTING.md#live-compatibility) |
| BKL-004 | P1 | High | blocked | After HARD-003, HARD-006, and REL-003, run a controlled real-executor baseline/candidate cohort with pinned model, executor, environment, tools, cache policy, repetitions, exclusions, and sealed evidence. | [Evidence and evaluation](EVIDENCE_AND_EVALUATION.md#cohort-comparison) |
| BKL-007 | P1 | High | blocked | After HARD-001 and HARD-008, add opt-in installer-owned host routing enforcement only for narrowly defined direct delegation commands, with preserved hooks and an audited break-glass path. | [Operations](OPERATIONS.md#host-routing) |
| MCP-003 | P1 | Critical | blocked | After HARD-004, HARD-005, and HARD-007, add idempotent pack validation, worktree creation, bounded launch, workflow validate/start/status/resume, progress, ack, and steer tools through existing services. Preserve the current read-only capability/catalog resources; MCP launch must reuse the CLI launch service and retain launch-contract v2 command artifacts/digests rather than creating MCP-local command or launch authority. | [MCP server](MCP_SERVER.md#planned-mutation-phase) and [`mcp-server-next`](../prompt-packs/mcp-server-next/) |
| REL-004 | P1 | Critical | blocked | After all P0 HARD items, HARD-010, REL-001, REL-002, and REL-003, execute the public-preview gate: clean-source build/install/uninstall, signed artifacts, drift audit, live compatibility, threat-model review, and explicit go/no-go record. | [Public release readiness](PUBLIC_RELEASE_READINESS.md#release-gate) |
| BKL-010 | P1 | Medium | blocked | Supply a pinned browser-image digest, font manifest, and verified pre-seal browser/Inspect evidence bridge before implementing the visual priority-picker fixture. | [Evidence and evaluation](EVIDENCE_AND_EVALUATION.md) |

## Decisions

| ID | Priority | State | Decision |
|---|---|---|---|
| DEC-001 | P0 | decided | Local JSONL authority, per-consumer FIFO, at-least-once append, digest-bound idempotency, rebuildable cursors, and a 2-second normal replay objective. | [Decision](DECISIONS/DEC-001-DURABLE-CONTROL.md) |
| DEC-002 | P1 | needs-decision | Set benchmark policy: first executors, billing meaning, cache role, replicate count/effect threshold, and treatment of interrupted or human-assisted trials. |
| DEC-003 | P2 | deferred | Authorize multi-host orchestration only after a measured single-host failure. Preserve replayable durable records as authority; prefer JetStream unless an existing Redis dependency is mandated. |
| DEC-MCP-HTTP | P2 | deferred | Authorize any non-stdio MCP transport only through a separate security ADR after local adoption evidence. |
| DEC-004 | P1 | decided | Retain `agent-workflow` as the execution host, add a versioned trusted plugin API, and build `agent-workflow-spec` as the first sibling plugin before extracting other subsystems. |

## Proposed specification and plugin program

These tasks are designed under decided `DEC-004` but remain planning-only until their individual implementation gates are authorized. No prompt pack owns them yet. The sibling repository remains independent; core must not import it.

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| PLUG-001 | P1 | High | needs-decision | Add a minimal trusted first-party plugin host using package entry points, explicit enablement, API/version checks, atomic conflict-free registration, command-catalog provenance, schema/assets registration, recovery mode, and one installed-product fixture-plugin journey. | [Plugin mechanism](SPEC_AUTHORING_PLUGIN_ARCHITECTURE.md#plugin-mechanism) |
| SPEC-001 | P1 | High | blocked | After `PLUG-001`, bootstrap the sibling `agent-workflow-spec` repository with canonical implementation-spec, event, approval, and compiler-receipt contracts plus standalone init/validate/render/approve commands. | [Sibling repository design](SPEC_AUTHORING_PLUGIN_ARCHITECTURE.md#sibling-repository-design-agent-workflow-spec) |
| SPEC-002 | P1 | High | blocked | After `SPEC-001`, deterministically compile approved specs into the existing prompt-pack format, machine task contracts, result schemas, traceability, output manifests, and compiler receipts. | [Deterministic compiler](SPEC_AUTHORING_PLUGIN_ARCHITECTURE.md#deterministic-compiler) |
| SPEC-003 | P1 | High | blocked | After `SPEC-002`, generate declarative installed-product acceptance/evaluation artifacts and assess sealed evidence at requirement granularity without generating a bespoke test file for every requirement. | [Acceptance and evaluation](SPEC_AUTHORING_PLUGIN_ARCHITECTURE.md#acceptance-and-evaluation-generation) |
| SPEC-004 | P2 | Medium | blocked | After `SPEC-001`, add collaborative intent, research, questions, structured revisions, coverage review, and human approval pauses through a framework-neutral native authoring engine. | [Collaborative authoring](SPEC_AUTHORING_PLUGIN_ARCHITECTURE.md#collaborative-authoring-model) |
| SPEC-005 | P2 | Medium | blocked | After `SPEC-004`, add an optional LangGraph adapter implementing the same authoring-engine interface while canonical events, approved JSON, and compiler receipts remain authoritative. | [LangGraph placement](SPEC_AUTHORING_PLUGIN_ARCHITECTURE.md#langgraph-placement) |
| ARC-004 | P2 | High | blocked | After stable real-world evidence from `PLUG-001` and the spec plugin, evaluate extracting exactly one existing optional subsystem; do not perform a broad simultaneous repository split. | [Core decomposition roadmap](SPEC_AUTHORING_PLUGIN_ARCHITECTURE.md#core-decomposition-roadmap) |

## Deferred architecture

These existing items already own the assessment's P2 recommendations. The hardening packs must not create competing tickets for them.

| ID | Priority | Trigger |
|---|---|---|
| ARC-001 | P2 | Add a transport-neutral notifier only after measured wakeup latency or operability requires it; replay remains mandatory. |
| ARC-002 | P3 | Add a reconstructable SQLite index only after JSONL replay/scan cost is measured as a problem. |
| ARC-003 | P3 | Add a multi-host broker, shared-artifact references, and cross-trust signing only after `DEC-003`. |
| MCP-004 | P2 | Add policy-gated review/disposition and interrupt/terminate tools after `MCP-003`; preserve the capability/command-context resources and never infer authorization from catalog membership; force kill remains excluded. |
| WF-006 | P2 | Consider evidence-derived routing recommendations only after comparable real-executor cohorts exist; no online learning or vector-memory dependency. |

## Completed history

| Release | Summary |
|---|---|
| 0.1.x | Worktrees, tmux lifecycle, durable state, prompt packs, evaluation, provider adapters, skills, and packaging foundations. |
| 0.2.0 | Workflow DAGs, approvals, result binding, aggregate receipts, templates, routing advice, and provider/trial evidence. |
| 0.2.1 | Authority, replay, locking, symlink, scorer-receipt, provider-accounting, and immutable-input hardening. |
| 0.2.2 | Acceptance-first installed-product tests, compact invariant matrices, strict future TDD journeys, CI, and public-documentation consolidation. |
| 0.2.2 maintenance | Jenkins local pipeline now provisions an isolated Python environment, installs build/test dependencies, avoids stale workspace virtualenvs, builds and locally installs the wheel, and passed build #16 with `35 passed, 2 skipped, 1 xfailed`. |
| 0.2.4 maintenance | Completed evaluation/benchmark templating and REL-005 release evidence: policy/lock validation, structured tests, CycloneDX SBOM, provenance, and blocker enforcement without closing REL-001/002/003 or HARD-010. |
| 0.2.5 spec/plugin design | Added the trusted plugin boundary and sibling `agent-workflow-spec` architecture; DEC-004 is decided while implementation tasks remain separately gated and non-executable. |
| 0.2.5 maintenance | Accepted BKL-001 durable consumer cursors and idempotent handling dispositions with restart, reconstruction, crash-window, isolation, redaction, scope, and sealed-evaluation evidence; see [final acceptance evidence](BKL-001_EVIDENCE_RECOVERY_20260728.md). |
| 0.2.5 command catalog | Added the parser-derived command catalog, role-scoped launch cards, sealed launch-contract v2 bindings, and child environment exports that reduce routine `--help` probing; validated by installed-product acceptance and invariant tests. |
| 0.2.5 MCP command context | Added bounded read-only MCP capability/catalog resources and verified per-run command context/card resources with schema validation, redacted CLI identity, no dynamic tools, and fail-closed digest checks. |
| 0.2.5 Jenkins deployment | Jenkins build #23 on `master` at `5de662c` passed the installed-product/release suite, built the wheel, and installed `agent-workflow 0.2.5` plus `mcp==1.28.1` globally through the host deployment path. |
