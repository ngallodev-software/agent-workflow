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
| [`deterministic-enforcement-foundations`](../prompt-packs/deterministic-enforcement-foundations/) | HARD-001, HARD-002, HARD-004, HARD-005 | HARD-001, HARD-002, HARD-004, HARD-005, and FOUND-GATE-01 accepted for the current integrated tree. |
| [`execution-isolation-and-secrets`](../prompt-packs/execution-isolation-and-secrets/) | HARD-008, HARD-003, HARD-006 | HARD-008 accepted; HARD-003 and HARD-006 remain blocked on their declared prerequisites. |
| [`public-beta-trust-and-release`](../prompt-packs/public-beta-trust-and-release/) | HARD-007, HARD-009, HARD-010, REL-003, REL-004 | Blocked until the first two packs are accepted. |
| [`mcp-server-next`](../prompt-packs/mcp-server-next/) | MCP-003 | Blocked on HARD-004, HARD-005, and HARD-007; future mutations must preserve the current parser-derived capability/catalog resources and launch-contract v2 command-context parity. |
| [`orchestrator-two-way-messaging`](../prompt-packs/orchestrator-two-way-messaging/) | BKL-001, BKL-002, MSG-001 through MSG-007 | BKL-002 now has an opt-in cooperative file adapter, durable delivery outcomes, and installed fixture evidence; it remains in review pending HARD-007, claimed live-executor adapters, and the owning phase gate. MSG-001 remains in review. |
| [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/) | PROC-001 through PROC-005 | PROC-001 and PROC-002 remain in review. PROC-003 and PROC-004 are implemented with focused invariant/installed evidence and are in review pending the pack gate and remaining recovery matrix. |
| [`tmux-pane-identity-reliability`](../prompt-packs/tmux-pane-identity-reliability/) | PROC-006 | Integrated pane-identity work is in review pending repaired closeout, live-host, and sealed acceptance evidence. |
| [`source-preflight-snapshot-reliability`](../prompt-packs/source-preflight-snapshot-reliability/) | PROC-007 | Implemented and in review: exact-root status now preserves operator Git excludes while recording bounded command provenance; focused installed clean/dirty evidence passes. |
| [`chatgpt-sealed-run-assessment`](../prompt-packs/chatgpt-sealed-run-assessment/) | CHATGPT-EVAL-001, CHATGPT-TDD-001 | Assessment and future-TDD artifacts completed; future journeys remain strict expected failures and do not unblock planned runtime work. |
| [`force-accept-override`](../prompt-packs/force-accept-override/) | LIFE-001 | Ready for isolated implementation; add an explicit, audited manual force-accept path without weakening normal acceptance. |
| [`codex-luna-effort-policy`](../prompt-packs/codex-luna-effort-policy/) | POL-001 | Integrated and in review; automatic Codex selection is Luna-only with low/medium/high effort and immutable launch evidence. |
| [`hierarchical-multi-team-orchestration`](../prompt-packs/hierarchical-multi-team-orchestration/) | HIER-001 through HIER-008 | Proposed design package; blocked on maintainer approval of DEC-005 and the ticket-specific accepted messaging, delegation, steering, and pane-identity prerequisites listed below. |
| [`bounded-self-healing-supervisor`](../prompt-packs/bounded-self-healing-supervisor/) | SUP-001 through SUP-008 | SUP-001 and SUP-002 are implemented and in review. Security enforcement, authenticated authority, live compatibility, hierarchy integration, and performance control remain sequenced behind their declared gates. |
| [`sqlite-evidence-index`](../prompt-packs/sqlite-evidence-index/) | IDX-001 through IDX-007 | IDX-001 through IDX-005 are implemented and in review. Privacy-governed analytical export and measured-scale checkpoint work remain explicitly gated. |

## Bounded self-healing supervision

`DEC-006` establishes a deterministic `observe → diagnose → act → verify → record` loop. Automatic actions may repair reconstructable projections, replay durable records, send bounded probes, or exercise explicitly preauthorized interrupt/restart policy. They may never grant permissions, expose credentials, alter acceptance criteria, choose an unauthorized model/tool, merge work, delete evidence, or widen any delegation or resource budget.

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| SUP-001 | P0 | Critical | in-review | Bounded health, process-result, terminal, permission, incident, and remediation evidence now separates supervisor liveness, executor liveness, semantic progress, and blocked state. Interactive terminal capture is change-driven, ANSI-cleaned, redacted, and advisory. Closeout requires the Phase 0 gate and installed live-tmux evidence. | [Architecture](SELF_HEALING_SUPERVISOR_ARCHITECTURE.md#evidence-model) |
| SUP-002 | P0 | Critical | in-review | A foregroundable supervisor now repairs reconstructable status projections, samples health, classifies incidents, deduplicates evidence, and applies attempt-bounded safe probes. Interrupt and orphan restart remain disabled by default and require explicit operator policy. Closeout requires replay/restart/tamper and installed-product gate evidence. | [Supervisor loop](SELF_HEALING_SUPERVISOR_ARCHITECTURE.md#supervisor-lifecycle) |
| SUP-003 | P0 | Critical | blocked | Apply field-level redaction, retention, export, and deletion policy to terminal, permission, health, incident, and remediation evidence while preserving useful digests/categories. Blocked on accepted HARD-006 and SUP-GATE-0. | [Privacy and retention](SELF_HEALING_SUPERVISOR_ARCHITECTURE.md#security-and-privacy) |
| SUP-004 | P0 | Critical | blocked | Enforce CPU, memory, process, descriptor, wall-time, output, disk, and network policy where supported; record effective controls; pause launches and narrow concurrency under pressure without raising ceilings. Blocked on accepted HARD-003 and SUP-GATE-0. | [Resource control](SELF_HEALING_SUPERVISOR_ARCHITECTURE.md#performance-and-capacity) |
| SUP-005 | P0 | Critical | blocked | Bind permission decisions, steering, remediation, review, and escalation to authenticated principals and immutable delegation policy. Blocked on accepted HARD-007 and SUP-GATE-0. | [Authority boundary](DECISIONS/DEC-006-BOUNDED-SELF-HEALING.md) |
| SUP-006 | P0 | Critical | blocked | Prove installed recovery across supported hosts, tmux versions, source archives/checkouts, and every claimed executor: permission wait, no-progress stall, process/pane loss, missed wake, projection/cursor corruption, resource exhaustion, and restart. Blocked on SUP-GATE-1 and REL-003. | [Compatibility matrix](../prompt-packs/bounded-self-healing-supervisor/phase-2/) |
| SUP-007 | P0 | Critical | blocked | Integrate the accepted supervisor at root and team-lead scope, preserving team isolation, escalation lineage, global/local budgets, and presentation-only tmux recovery. Blocked on SUP-GATE-2, HIER-005, and HIER-006. | [Hierarchy integration](SELF_HEALING_SUPERVISOR_ARCHITECTURE.md#hierarchical-integration) |
| SUP-008 | P1 | High | blocked | Detect comparable process/performance regressions and deterministically pause launches, narrow concurrency, or select only configured preapproved fallback policy using static thresholds and hysteresis. Blocked on SUP-006, SUP-007, BKL-004, and HIER-007. | [Performance control](SELF_HEALING_SUPERVISOR_ARCHITECTURE.md#performance-and-capacity) |

### Self-healing dependency order

The current Phase 0 implementation may be reviewed immediately. Security-governed work deliberately fans out only after the Phase 0 gate; all three Phase 1 lanes must be accepted before compatibility claims or automatic recovery are widened.

| Lane | Required order | Execution rule |
|---|---|---|
| Observable foundation | `SUP-001 → SUP-002 → SUP-GATE-0` | Implemented and ready for independent installed/live review. |
| Privacy and retention | accepted `HARD-006` + `SUP-GATE-0 → SUP-003` | May run in parallel with SUP-004 and SUP-005. |
| Resource enforcement | accepted `HARD-003` + `SUP-GATE-0 → SUP-004` | May narrow launch capacity; may never raise limits automatically. |
| Authenticated authority | accepted `HARD-007` + `SUP-GATE-0 → SUP-005` | Human authority remains mandatory for permissions and acceptance. |
| Governed gate | `SUP-003 + SUP-004 + SUP-005 → SUP-GATE-1` | No broad recovery compatibility claim before this gate. |
| Installed recovery matrix | accepted `REL-003` + `SUP-GATE-1 → SUP-006 → SUP-GATE-2` | Must prove every claimed host/executor combination and fail closed elsewhere. |
| Hierarchical supervision | `SUP-GATE-2 + HIER-005 + HIER-006 → SUP-007` | Team leads supervise only their delegated workers; root owns cross-team policy. |
| Performance control | `SUP-007 + SUP-006 + BKL-004 + HIER-007 → SUP-008 → SUP-GATE-3` | Static configured thresholds only; no online/model-authored policy. |

```text
SUP-001 → SUP-002 → SUP-GATE-0
                      ├─ [HARD-006] → SUP-003 ─┐
                      ├─ [HARD-003] → SUP-004 ─┼→ SUP-GATE-1
                      └─ [HARD-007] → SUP-005 ─┘
                                                ↓
                               [REL-003] → SUP-006 → SUP-GATE-2
                                                ↓
                     [HIER-005 + HIER-006] → SUP-007
                                                ↓
                     [BKL-004 + HIER-007] → SUP-008 → SUP-GATE-3
```

## Searchable evidence projection

`DEC-007` replaces the former defer-until-slow `ARC-002` posture. JSON/JSONL artifacts, immutable snapshots, and sealed receipts remain authoritative; SQLite is a host-local, fully rebuildable operational projection. Prompt-pack gate IDs (`IDX-GATE-*`) are independent review tasks, not backlog items.

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| IDX-001 | P0 | Critical | in-review | Versioned SQLite schema, application identity, WAL/foreign-key/full-sync configuration, owner-only storage, exclusive writer locking, and source-file/record SHA-256 provenance are implemented. Closeout requires migration and installed-product review at `IDX-GATE-0`. | [Decision](DECISIONS/DEC-007-REBUILDABLE-SQLITE-PROJECTION.md) |
| IDX-002 | P0 | Critical | in-review | Full rebuild, active/archive discovery, changed-run incremental reconciliation, stable no-follow/shared-lock reads, atomic per-run replacement, stale-row pruning, source-digest verification, and corrupt-run quarantine are implemented. Closeout requires interruption, archive, and rebuild-equivalence evidence. | [Reconciliation](SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md#rebuild-and-incremental-synchronization) |
| IDX-003 | P0 | High | in-review | Normalized run, source, event, health, permission, incident, remediation, process, performance, workflow-node, and workflow-edge projections plus curated views are implemented. Raw prompts, terminal/message bodies, credentials, and large logs are excluded. | [Schema and ERD](SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md#data-model) |
| IDX-004 | P1 | High | in-review | `index status|sync|rebuild|verify|query`, freshness-bearing query envelopes, fixed parameterized filters, help/catalog/completion integration, man pages, README, and operator/security/testing documentation are implemented. The isolated wheel-installed delete/rebuild journey and release drift audit pass; closeout awaits independent `IDX-GATE-1` review. | [Command reference](COMMAND_REFERENCE.md#searchable-evidence-index) |
| IDX-005 | P1 | High | in-review | Foreground supervisor cycles incrementally synchronize the projection by default and report indexing failures without stopping health supervision. Closeout requires concurrency, failure-injection, and representative active/archive evidence. | [Supervisor integration](SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md#supervisor-integration) |
| IDX-006 | P1 | High | blocked | After accepted HARD-006, SUP-003, IDX-GATE-1, and comparable BKL-004 evidence, define privacy-governed immutable analytical exports, retention/deletion rules, provenance, and cohort semantics for offline Parquet/DuckDB analysis. | [Analytical path](SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md#security-and-privacy) |
| IDX-007 | P2 | Medium | blocked | After IDX-GATE-2 and measured scale evidence, add reconstructable byte-offset/sequence checkpoints, migration compatibility, bounded capacity claims, and truncation/rotation recovery without making checkpoints authoritative. | [Scale evolution](SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md#performance-strategy) |

### SQLite projection dependency order

The first two phases are implemented and may be independently reviewed. Privacy and scale work remain off the critical path until their external evidence exists.

| Lane | Required order | Execution rule |
|---|---|---|
| Authority and schema | `DEC-007 → IDX-001` | No query feature may precede the authority/provenance boundary. |
| Reconciliation and projections | `IDX-001 → {IDX-002 ∥ IDX-003} → IDX-GATE-0` | Rebuild/reconciliation and typed schema lanes may run in parallel after the base migration contract. |
| Public product surface | `IDX-GATE-0 → {IDX-004 ∥ IDX-005} → IDX-GATE-1` | CLI/docs and supervisor integration are independent lanes sharing one accepted projection service. |
| Governed analytics | accepted `HARD-006` + `SUP-003` + `BKL-004` + `IDX-GATE-1 → IDX-006 → IDX-GATE-2` | No analytical export before field classification, retention, and comparable evidence are accepted. |
| Measured optimization | measured scale evidence + `IDX-GATE-2 → IDX-007 → IDX-GATE-3` | Add checkpoints only after measured need; complete rebuild remains mandatory. |

```text
DEC-007 → IDX-001 → ┬→ IDX-002 ─┐
                     └→ IDX-003 ─┴→ IDX-GATE-0
                                      ├→ IDX-004 ─┐
                                      └→ IDX-005 ─┴→ IDX-GATE-1
                                                       ↓
                     [HARD-006 + SUP-003 + BKL-004] → IDX-006 → IDX-GATE-2
                                                                            ↓
                                                        [measured scale] → IDX-007 → IDX-GATE-3
```

## Proposed hierarchical orchestration

These items implement the bounded root orchestrator → team lead → worker design. `DEC-005` authorizes the hierarchy. Existing messaging, delegation, steering, and pane-identity work remains independently gated at the first ticket that consumes each foundation; those prerequisites may proceed in parallel with the decision and Phase 0 contract work.

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| HIER-001 | P0 | Critical | needs-decision | After `DEC-005` is approved, define immutable hierarchy and team-delegation contracts with fixed depth, principal identity, scope, budgets, allowed command/model policy, and capability narrowing. | [Hierarchical design](HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md#contracts) |
| HIER-002 | P0 | Critical | blocked | Add append-only hierarchy/action/ack journals, deterministic replay, team receipts, and root orchestration receipts with tamper/truncation tests. Blocked on HIER-001. | [Prompt pack phase 0](../prompt-packs/hierarchical-multi-team-orchestration/phase-0/) |
| HIER-003 | P0 | Critical | blocked | Add a managed tmux session with stable root/team window IDs and worker panes scoped to the owning team; reconcile movement, reindexing, loss, and restart without duplicate launch. Blocked on HIER-002 and accepted PROC-006. | [Managed tmux topology](HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md#tmux-and-terminal-design) |
| HIER-004 | P1 | High | blocked | Add an optional configured argv-only external terminal adapter that attaches to an exact team window and fails without destroying durable team state. Blocked on HIER-003. | [Forking a new terminal](HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md#forking-a-new-terminal) |
| HIER-005 | P0 | Critical | blocked | Launch a team lead as a canonical session with bounded delegation authority and allow only contract-scoped canonical worker workflows. Blocked on HIER-002, HIER-003, MSG-001, PROC-001, and PROC-002 acceptance. | [Team-lead lifecycle](HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md#team-lead-lifecycle) |
| HIER-006 | P0 | Critical | blocked | Implement root ↔ team-lead and team-lead ↔ worker replayable messaging, acknowledgements, local decisions, escalation, late steering, cancel, and unavailable evidence. Blocked on HIER-005 and BKL-002. | [Message model](HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md#message-model) |
| HIER-007 | P0 | Critical | blocked | Add root-level team dependency scheduling, global capacity leases, verified cross-team result bindings, retries, and fan-in. Blocked on HIER-005 and HIER-006. | [Scheduling and budgets](HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md#scheduling-and-budgets) |
| HIER-008 | P0 | Critical | blocked | Deliver tree/status/attach CLI, deterministic root/team recovery, docs/skills/man pages, and a sealed two-team installed-product journey with explicit final approval. Blocked on HIER-007. | [Acceptance journeys](HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md#acceptance-journeys) |

### Hierarchical orchestration dependency order

The hierarchy work has one critical path and one optional terminal-integration branch. Prompt-pack gate IDs (`HIER-GATE-*`) are review tasks, not backlog items. A later phase must not start merely because implementation code exists; the preceding critical-path gate must accept its evidence.

| Lane | Required order | Execution rule |
|---|---|---|
| Decision and durable authority | `DEC-005` → `HIER-001` → `HIER-002` → `HIER-GATE-0` | This lane may start while the existing messaging and pane work is being completed. |
| Managed tmux critical path | accepted `PROC-006` + `HIER-GATE-0` → `HIER-003` → `HIER-GATE-1` | Stable pane identity must be accepted before managed team windows become executable authority projections. |
| Team-lead runtime | accepted `MSG-001`, `PROC-001`, and `PROC-002` + `HIER-GATE-1` → `HIER-005` | The team lead reuses accepted registry/inbox, preflight, and control-handshake foundations. |
| Hierarchical messaging | accepted `BKL-002` + `HIER-005` → `HIER-006` → `HIER-GATE-2` | Late steering must be proven before the second messaging boundary is accepted. |
| Root scheduling and product proof | `HIER-GATE-2` → `HIER-007` → `HIER-008` → `HIER-GATE-3` | This is the final fan-out/fan-in, recovery, CLI, and sealed acceptance path. |
| Optional external terminal branch | `HIER-003` → `HIER-004` → `HIER-GATE-1A` | This branch may run in parallel after `HIER-003`. It does not block `HIER-005`, `HIER-006`, or the core product path. If implemented, it requires its own gate evidence. |

Critical path:

```text
DEC-005
  → HIER-001 → HIER-002 → HIER-GATE-0
  → [accepted PROC-006] → HIER-003 → HIER-GATE-1
  → [accepted MSG-001 + PROC-001 + PROC-002] → HIER-005
  → [accepted BKL-002] → HIER-006 → HIER-GATE-2
  → HIER-007 → HIER-008 → HIER-GATE-3

Optional parallel branch after HIER-003:
  HIER-004 → HIER-GATE-1A
```

## Ready now

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| BKL-002 | P0 | High | in-review | Added a typed opt-in `control-file-v1` adapter, immutable request inbox, durable `queued`/`delivered`/`applied`/`rejected`/`unsupported`/`expired`/`failed` journal, correlated child bridge acknowledgement, replay/race safeguards, and an installed-wheel acceptance journey. Default and unverified executors remain `unsupported`. Acceptance still requires HARD-007, any claimed live Codex/Claude adapter evidence, and the owning phase gate. | Installed journey in `tests/acceptance/test_late_steering_journey.py` |
| MSG-001 | P0 | Critical | in-review | Integrated at `50ea762`; repair the installed-product fixture and obtain sealed acceptance evidence for the immutable registry and append-only aggregate inbox before completion. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#add-one-shared-orchestrator-inbox) |
| PROC-001 | P0 | High | in-review | Reimplemented and integrated at `7136f86`; receipt-bound preflight rejects missing, stale, and rejected lifecycle evidence before tmux creation. Obtain final phase-review/acceptance evidence without treating the invalid child completion projection as success. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-001-authoritative-preflight.md) |
| PROC-002 | P0 | Critical | in-review | Control bridge is integrated at `1368769`; close installed matrix and sealed-evidence gaps for correlated progress/ack delivery, application, rejection, and unavailable outcomes. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-002-control-handshake.md) |
| PROC-003 | P1 | High | in-review | Observation now separates runner heartbeat, executor/process liveness, semantic progress, terminal activity, permission state, pane death, and output-capture exhaustion. A fresh heartbeat no longer masks a no-progress stall. The new supervisor journals bounded health/incident evidence; installed terminate/retry/live-host closeout and the owning pack gate remain open. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-003-run-observability.md) |
| PROC-004 | P0 | Critical | in-review | Completion collection now rejects placeholder-only completed reports, identity mismatch, absent revisions, acceptance evidence, or command receipts; failed/partial/blocked reports retain real failed commands and require unresolved evidence. Invalid collection makes the terminal run fail. Focused installed and invariant evidence passes; the owning phase gate remains open. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-004-completion-validation.md) |
| PROC-005 | P1 | High | ready | Align steering, templates, hooks/reminders, and recovery references with the enforced launch, communication, observation, completion, and closeout pattern. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-1/tickets/PROC-005-operator-enforcement.md) |
| PROC-006 | P0 | Critical | in-review | Pane identity is integrated at `55f4ed5`; current corrective commits `5785998` and `72451cc` await integration. Complete live-host and sealed acceptance evidence: layout changes must retain the bound pane, while termination or genuine loss must report it unavailable without rebinding. | [`tmux-pane-identity-reliability`](../prompt-packs/tmux-pane-identity-reliability/phase-0/tickets/PROC-006-pane-identity.md) |
| PROC-007 | P0 | High | in-review | Exact-root cleanliness now executes a fresh `git -C <root> status --porcelain`, preserves the operator's system/global exclude view without enabling prompts or helpers, records bounded executable/argv/exit/output-digest provenance, accepts globally ignored state, and still rejects real untracked changes. Focused installed and invariant evidence passes; pack review and broader host compatibility remain open. | [`source-preflight-snapshot-reliability`](../prompt-packs/source-preflight-snapshot-reliability/phase-0/tickets/PROC-007-source-snapshot.md) |
| LIFE-001 | P0 | Critical | ready | Add a locally interactive, explicit `force-accept` command that records an immutable override receipt with actor, reason, and failed-normal-gate evidence. It must preserve ordinary `accept` validation and truthfully document that authenticated human-only authorization remains blocked on HARD-007. | [`force-accept-override`](../prompt-packs/force-accept-override/phase-0/tickets/LIFE-001-force-accept.md) |
| POL-001 | P0 | High | in-review | Automatic Codex selection is Luna-only with bounded low/medium/high effort, deterministic `-c model_reasoning_effort=...` argv, immutable launch effort evidence, and pre-launch bypass rejection. Focused installed/invariant evidence passes; final phase evidence remains open. | [`codex-luna-effort-policy`](../prompt-packs/codex-luna-effort-policy/phase-0/tickets/POL-001-luna-effort-policy.md) |
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
| HARD-004 | P0 | Critical | completed | Accepted at `ef6393e`; coordinator review verified the immutable launch contract, restart authority, projection repair, exact receipt digest, installed status-tamper journey, focused slice (`26 passed`), full suite (`103 passed, 2 skipped, 5 xfailed`), release assets, and pack validation. The shared foundation gate remains open; MSG-001 must not start. | [HARD-004 review and closure](HARD-004-REVIEW-20260728.md) |
| HARD-005 | P0 | Critical | completed | Accepted against the current tree after the installed stdio journey (`7 passed`), security slices (`18 passed`), full suite (`103 passed, 2 skipped, 5 xfailed`), release audit, and pack validation. | [HARD-005 review and closure](HARD-005-REVIEW-20260728.md) |
| HARD-008 | P1 | High | completed | Integrated in `622b0df`; current trust/config acceptance slices pass (`14 passed`), with full-suite, release-audit, and pack validation evidence retained. | [Foundation gate review](FOUNDATION-GATE-REVIEW-20260728.md) |

## Planned TDD follow-up

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| CHATGPT-TDD-001 | P1 | High | completed | Added strict future journeys for HARD-004, MSG-005, BKL-004, and MCP-003/HARD-007; all remain honest expected failures pending implementation and accepted gates. | [Future tests](../tests/future/) |

## Blocked prerequisites

| ID | Priority | Risk | State | Missing prerequisite and exit evidence | Reference |
|---|---|---:|---|---|---|
| MSG-002 | P0 | Critical | blocked | Reuse the implemented foreground supervisor foundation, then after BKL-001, MSG-001, HARD-001, and HARD-008 add aggregate single-writer inbox ownership, shared hashed tmux wake channels, periodic replay fallback, bounded fairness, and cursor-after-commit fan-in. The health supervisor does not yet satisfy aggregate messaging ownership. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#use-one-shared-wake-channel) |
| MSG-003 | P0 | Critical | blocked | After MSG-002, HARD-004, HARD-006, HARD-007, and HARD-008, add fixed-format orchestrator wake/resume adapters that receive opaque event IDs only and cannot inject child-controlled content. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#the-supervisor-must-wake-the-orchestrator-safely) |
| MSG-004 | P1 | High | blocked | After MSG-002, MSG-003, MSG-005, and HARD-007, distinguish durable event delivery, orchestrator application acknowledgement, and linked scheduling/lifecycle action evidence through shared services. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#acknowledgement-model) |
| MSG-005 | P1 | Critical | blocked | After BKL-001, MSG-001, and MSG-002, reconstruct delivery after supervisor/orchestrator restart, missed or duplicate signals, corrupt cursors, and every cursor/inbox crash window without duplicate semantic effects. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#failure-and-restart-behavior) |
| MSG-006 | P1 | Critical | blocked | After the integrated messaging implementation and HARD-001/HARD-002/HARD-004/HARD-006/HARD-007/HARD-008, harden identity, bounds, redaction, no-follow storage, duplicate IDs, prompt injection, notification templates, resource use, and supervisor ownership adversarially. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#security-requirements) |
| MSG-007 | P1 | High | blocked | After MSG-001 through MSG-005 and BKL-002, add installed-wheel completion/wakeup/restart/action journeys plus opt-in real tmux and supported executor compatibility tests; keep low-level tests limited to compact security/replay matrices. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#acceptance-strategy) |
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

| ID | Priority | State | Decision | Reference |
|---|---|---|---|---|
| DEC-001 | P0 | decided | Local JSONL authority, per-consumer FIFO, at-least-once append, digest-bound idempotency, rebuildable cursors, and a 2-second normal replay objective. | [Decision](DECISIONS/DEC-001-DURABLE-CONTROL.md) |
| DEC-002 | P1 | needs-decision | Set benchmark policy: first executors, billing meaning, cache role, replicate count/effect threshold, and treatment of interrupted or human-assisted trials. | — |
| DEC-003 | P2 | deferred | Authorize multi-host orchestration only after a measured single-host failure. Preserve replayable durable records as authority; prefer JetStream unless an existing Redis dependency is mandated. | — |
| DEC-MCP-HTTP | P2 | deferred | Authorize any non-stdio MCP transport only through a separate security ADR after local adoption evidence. | — |
| DEC-004 | P1 | decided | Retain `agent-workflow` as the execution host, add a versioned trusted plugin API, and build `agent-workflow-spec` as the first sibling plugin before extracting other subsystems. | — |
| DEC-005 | P0 | needs-decision | Adopt a bounded root orchestrator → team lead → worker hierarchy with durable authority and one managed tmux window per team. | [Decision](DECISIONS/DEC-005-HIERARCHICAL-ORCHESTRATION.md) |
| DEC-006 | P0 | decided | Use bounded deterministic self-healing: durable evidence is authoritative; automatic action must be preauthorized, idempotent, attempt-bounded, verified, and incapable of widening authority. | [Decision](DECISIONS/DEC-006-BOUNDED-SELF-HEALING.md) |
| DEC-007 | P0 | decided | Keep JSON/JSONL, immutable snapshots, and sealed receipts authoritative while adding a host-local, single-writer, fully rebuildable SQLite projection for cross-run search and analysis. | [Decision](DECISIONS/DEC-007-REBUILDABLE-SQLITE-PROJECTION.md) |

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
| ARC-003 | P3 | Add a multi-host broker, shared-artifact references, and cross-trust signing only after `DEC-003`. |
| MCP-004 | P2 | Add policy-gated review/disposition and interrupt/terminate tools after `MCP-003`; preserve the capability/command-context resources and never infer authorization from catalog membership; force kill remains excluded. |
| WF-006 | P2 | Consider evidence-derived routing recommendations only after comparable real-executor cohorts exist; no online learning or vector-memory dependency. |

## Completed history

| Release | Summary |
|---|---|
| 0.5.1 | Completion handoffs validate before reuse, invalid child bridge intents are rejected, and pending reuse cannot seal as successful. |
| 0.5.0 | Bounded self-healing supervision added with Luna-only automatic Codex policy preserved. |
| 0.3.0 | Sandbox-safe child control bridge, launcher-executable binding, source-snapshot repair, clean wheel builds, and enforceable semantic-version bump checks. PROC-001, PROC-002, PROC-006, and MSG-001 remain separately tracked as in-review until their acceptance evidence is complete. |
| 0.3.0 SQLite projection design | `ARC-002` superseded by decided `DEC-007`; implementation is tracked under `IDX-001` through `IDX-007`. |
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
