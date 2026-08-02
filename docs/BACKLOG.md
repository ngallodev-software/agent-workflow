# agent-workflow backlog

This is the only task register for unfinished work. Design documents explain architecture and constraints; they do not maintain parallel status checklists. Completed implementation detail belongs in Git history and [CHANGELOG.md](CHANGELOG.md).

The determinism and security work below is derived from the [feature determinism and security assessment](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md) and sequenced in the [hardening plan](DETERMINISM_SECURITY_HARDENING_PLAN.md).

## Rules

- Every active item has a stable ID, priority, state, observable exit evidence, and one canonical owner.
- `completed` means behavior and accepted evidence exist; completed items move to the history summary.
- `ready` means every declared implementation prerequisite is satisfied, although acceptance evidence may still be required.
- `in-review` means the implementation is integrated but shared acceptance and phase-gate evidence remain open.
- `blocked` names the missing prerequisite.
- `needs-decision` requires explicit maintainer authorization before implementation.
- New features require an installed-product acceptance journey or an approved strict future specification.
- Repository-owned prompt-pack tasks declare `backlog_id`. Exactly one active prompt pack may own a backlog item.
- Review-only tasks use `task_type: gate`, do not claim a backlog item, and may not implement new scope.
- Parallel agents use separate worktrees. Missing dependency edges permit concurrency; prose may not bypass manifest dependencies.
- Run the `release-drift-auditor` skill and `scripts/audit-release-assets.py` before every phase gate and archive.

## Prompt-pack ownership and gate state

| Prompt pack | Canonical backlog ownership | Execution status |
| --- | --- | --- |
| [`deterministic-enforcement-foundations`](../prompt-packs/deterministic-enforcement-foundations/) | HARD-001, HARD-002, HARD-004, HARD-005 | Completed and accepted for the current integrated tree, including FOUND-GATE-01. |
| [`execution-isolation-and-secrets`](../prompt-packs/execution-isolation-and-secrets/) | HARD-008, HARD-003, HARD-006 | HARD-008 is completed; HARD-003 and HARD-006 are now unblocked and ready. |
| [`public-beta-trust-and-release`](../prompt-packs/public-beta-trust-and-release/) | HARD-007, HARD-009, HARD-010, REL-003, REL-004 | HARD-007 and REL-003 are ready; HARD-009, HARD-010, and REL-004 remain dependency-gated. |
| [`mcp-server-next`](../prompt-packs/mcp-server-next/) | MCP-003 | HARD-004 and HARD-005 are accepted; blocked on HARD-007; future mutations must preserve the current parser-derived capability/catalog resources and launch-contract v2 command-context parity. |
| [`orchestrator-two-way-messaging`](../prompt-packs/orchestrator-two-way-messaging/) | BKL-001, BKL-002, MSG-003 through MSG-007 | MSG-002 was independently accepted with a valid sealed, critical-tier review at `570a787`; BKL-002 remains in review pending HARD-007, claimed live-executor adapters, and the owning phase gate. MSG-001 was force-accepted with a sealed, explicit operator override after independent focused verification. |
| [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/) | PROC-001 through PROC-005, MAINT-003 through MAINT-006 | PROC-001 and PROC-002 remain in review. PROC-003 and PROC-004 are implemented with focused invariant/installed evidence and are in review pending the pack gate and remaining recovery matrix. MAINT-003 repairs terminal-completion inbox expectations; MAINT-004 repairs review ticket identity; MAINT-005 closes remaining review-launch and completion-template enforcement gaps; MAINT-006 repairs historical host-index verification so valid review gates are not blocked by obsolete evidence. |
| [`tmux-pane-identity-reliability`](../prompt-packs/tmux-pane-identity-reliability/) | PROC-006 | Integrated pane-identity work is in review pending repaired closeout, live-host, and sealed acceptance evidence. |
| [`tmux-operator-experience`](../prompt-packs/tmux-operator-experience/) | TMUXUI-001 through TMUXUI-009 | Planned from the tmux prior-art assessment. Core work is dependency-gated on accepted PROC-006 pane identity; the traffic-light material is an additive presentation contract, and the embedded sidebar remains separately `needs-decision`. |
| [`source-preflight-snapshot-reliability`](../prompt-packs/source-preflight-snapshot-reliability/) | PROC-007 | Implemented and in review: exact-root status now preserves operator Git excludes while recording bounded command provenance; focused installed clean/dirty evidence passes. |
| [`chatgpt-sealed-run-assessment`](../prompt-packs/chatgpt-sealed-run-assessment/) | CHATGPT-EVAL-001, CHATGPT-TDD-001 | Completed. HARD-004 graduated from future TDD to installed acceptance; remaining future journeys stay strict expected failures. |
| [`force-accept-override`](../prompt-packs/force-accept-override/) | LIFE-001 | Integrated in 0.7.0 and in review: explicit local force acceptance writes a separate immutable receipt and preserves the normal acceptance gate. |
| [`codex-luna-effort-policy`](../prompt-packs/codex-luna-effort-policy/) | POL-001 | Integrated and in review; automatic Codex selection is Luna-only with low/medium/high effort and immutable launch evidence. |
| [`hierarchical-multi-team-orchestration`](../prompt-packs/hierarchical-multi-team-orchestration/) | HIER-001 through HIER-008 | DEC-005 is decided; HIER-001 and HIER-002 authority are implemented and in review, including immutable contracts, append-only journals, deterministic replay, and digest-sealed team/root receipts with installed-product evidence. HIER-GATE-0 is the next review-only step. Later tickets remain gated by accepted phase reviews and their messaging, delegation, steering, and pane-identity prerequisites; hierarchy stays an explicitly enabled built-in feature under DEC-009. |
| [`bounded-self-healing-supervisor`](../prompt-packs/bounded-self-healing-supervisor/) | SUP-001 through SUP-008 | SUP-001 and SUP-002 are implemented and in review. Security enforcement, authenticated authority, live compatibility, hierarchy integration, and performance control remain sequenced behind their declared gates. |
| [`sqlite-evidence-index`](../prompt-packs/sqlite-evidence-index/) | IDX-001 through IDX-007 | IDX-001 through IDX-005 are implemented and in review. Privacy-governed analytical export and measured-scale checkpoint work remain explicitly gated. |
| [`release-installers`](../prompt-packs/release-installers/) | REL-008 | Implemented and in review: bootstrap, deterministic bundles, checksums, tag-only publication workflow, and installer tests exist; clean tagged-release evidence remains open. Jenkins CI/job files are repository-only and must never enter installed wheels or runtime bundles. |
| [`feature-modularization`](../prompt-packs/feature-modularization/) | MAINT-001, PLUG-001, ARC-004 | MAINT-001 is in progress after completing process, CLI, SQLite schema/source/query, and session artifact/control splits behind stable facades. PLUG-001 is in review with explicit enablement, atomic registration, recovery, catalog provenance, digest-bound installed package resources, and an installed fixture-wheel journey. MOD-GATE-1 remains its only closure step; ARC-004 remains evidence-gated until the boundary survives real first-party use. |
| [`comparative-benchmark-scoring-corrections`](../prompt-packs/comparative-benchmark-scoring-corrections/) | BENCH-CORR-001 through BENCH-CORR-010 | Rebased to 0.7.8. Phase 0 contract and efficiency-policy decisions are ready; implementation remains dependency-gated. The benchmark stays a built-in feature under DEC-009, and this pack does not add plugin hooks or perform ARC-004 extraction. |

## Bounded self-healing supervision

`DEC-006` establishes a deterministic `observe → diagnose → act → verify → record` loop. Automatic actions may repair reconstructable projections, replay durable records, send bounded probes, or exercise explicitly preauthorized interrupt/restart policy. They may never grant permissions, expose credentials, alter acceptance criteria, choose an unauthorized model/tool, merge work, delete evidence, or widen any delegation or resource budget.

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| SUP-001 | P0 | Critical | in-review | SUP-GATE-0 completed with a partial/reject recommendation: focused checks passed, but required real live-tmux/executor evidence and expected implementation-status evidence were unavailable. Retain the evidence boundary and rerun the gate after those journeys exist. | [Architecture](SELF_HEALING_SUPERVISOR_ARCHITECTURE.md#evidence-model) |
| SUP-002 | P0 | Critical | in-review | Integrated repair `70d27b0` makes every `SAFE-PROBE-STALL-v1` outcome consume its bounded attempt and records authoritative post-action observation for successful probes. Focused invariant and installed supervisor evidence passed; repeat SUP-GATE-0 after the review-completion collection defect is repaired. | [Supervisor loop](SELF_HEALING_SUPERVISOR_ARCHITECTURE.md#supervisor-lifecycle) |
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
| IDX-001 | P0 | Critical | in-review | IDX-GATE-0 completed: focused/schema/installed evidence passed. It remains open because IDX-002 failed the shared gate. | [Decision](DECISIONS/DEC-007-REBUILDABLE-SQLITE-PROJECTION.md) |
| IDX-002 | P0 | Critical | in-review | Integrated repair `47ebe2f` rejects symlinked source artifacts before reading them, records a durable `unsafe_source` index error, and makes full verification fail with `unsafe_symlink` rather than reporting current/valid. Focused invariant and installed journeys pass; redo the phase gate after the review-completion collection defect is repaired. | [Reconciliation](SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md#rebuild-and-incremental-synchronization) |
| IDX-003 | P0 | High | in-review | IDX-GATE-0 focused/schema/installed/privacy evidence passed; it remains open pending the repaired shared gate. Raw prompts, terminal/message bodies, credentials, and large logs remain excluded. | [Schema and ERD](SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md#data-model) |
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

## Bounded hierarchical orchestration

These items describe the approved bounded root orchestrator → team lead → worker feature. `DEC-005` is decided; direct orchestration remains the default compatibility path and hierarchy implementation must stay behind the feature boundary defined by `DEC-009`. Existing messaging, delegation, steering, and pane-identity work remains independently gated at the first ticket that consumes each foundation; those prerequisites may proceed in parallel with the decision and Phase 0 contract work.

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| HIER-001 | P0 | Critical | in-review | Integrated repair `205b244` rejects duplicate authority identities across root, team, and team-lead boundaries. Focused contract, installed journey, direct-boundary, release-audit, and pack-validation evidence passed; repeat HIER-GATE-0 after the review-completion collection defect is repaired. | [Hierarchical design](HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md#contracts) |
| HIER-002 | P0 | Critical | in-progress | HIER-GATE-0 rejected journal/receipt authority: team root-journal reuse and aggregate budget-overrun probes were accepted. Repair uniqueness and aggregate-budget enforcement, rerun tamper/replay/receipt checks, then repeat the gate. | [Prompt pack phase 0](../prompt-packs/hierarchical-multi-team-orchestration/phase-0/) |
| HIER-003 | P0 | Critical | blocked | Add a managed tmux session with stable root/team window IDs and worker panes scoped to the owning team; reconcile movement, reindexing, loss, and restart without duplicate launch. Blocked on accepted HIER-GATE-0 and accepted PROC-006. | [Managed tmux topology](HIERARCHICAL_MULTI_TEAM_ORCHESTRATION_DESIGN.md#tmux-and-terminal-design) |
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

## Active implementation and review

These items have no unresolved implementation prerequisite, are already integrated and awaiting acceptance, or require an explicit maintainer decision. `ready` does not imply release acceptance.

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| BKL-002 | P0 | High | in-review | Added a typed opt-in `control-file-v1` adapter, immutable request inbox, durable `queued`/`delivered`/`applied`/`rejected`/`unsupported`/`expired`/`failed` journal, correlated child bridge acknowledgement, replay/race safeguards, and an installed-wheel acceptance journey. Default and unverified executors remain `unsupported`. Acceptance still requires HARD-007, any claimed live Codex/Claude adapter evidence, and the owning phase gate. | Installed journey in `tests/acceptance/test_late_steering_journey.py` |
| PROC-001 | P0 | High | in-review | PROC Phase 0 review completed partial: selected runs lack immutable lifecycle dispositions. Re-run receipt-bound preflight acceptance after the phase closeout has durable review/acceptance evidence. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-001-authoritative-preflight.md) |
| PROC-002 | P0 | Critical | in-review | PROC Phase 0 review completed partial: retain the correlated control-bridge matrix, but rerun the phase gate after durable lifecycle disposition evidence exists. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-002-control-handshake.md) |
| PROC-003 | P1 | High | in-review | PROC Phase 0 review completed partial: observation evidence remains implemented, but the phase cannot close until lifecycle dispositions and the pending-reuse terminal outcome are independently rechecked. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-003-run-observability.md) |
| PROC-004 | P0 | Critical | in-review | Integrated repair `ff43501` makes terminal completion and explicit `--keep-alive` reuse distinct in the installed delegation journey, and proves pending reuse seals failed with a final receipt. Focused journey and review passed; repeat the phase gate after the review-completion collection defect is repaired. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-0/tickets/PROC-004-completion-validation.md) |
| PROC-005 | P1 | High | ready | Align steering, templates, hooks/reminders, and recovery references with the enforced launch, communication, observation, completion, and closeout pattern; completed handoffs require committed source and schema-valid revision-bound evidence. | [`delegation-communication-reliability`](../prompt-packs/delegation-communication-reliability/phase-1/tickets/PROC-005-operator-enforcement.md) |
| PROC-006 | P0 | Critical | in-review | Stable pane-identity behavior is implemented. Complete live-host and sealed acceptance evidence: layout changes must retain the bound pane, while termination or genuine loss must report it unavailable without rebinding. | [`tmux-pane-identity-reliability`](../prompt-packs/tmux-pane-identity-reliability/phase-0/tickets/PROC-006-pane-identity.md) |
| PROC-007 | P0 | High | in-review | Exact-root cleanliness now executes a fresh `git -C <root> status --porcelain`, preserves the operator's system/global exclude view without enabling prompts or helpers, records bounded executable/argv/exit/output-digest provenance, accepts globally ignored state, and still rejects real untracked changes. Focused installed and invariant evidence passes; pack review and broader host compatibility remain open. | [`source-preflight-snapshot-reliability`](../prompt-packs/source-preflight-snapshot-reliability/phase-0/tickets/PROC-007-source-snapshot.md) |
| MSG-005 | P1 | Critical | in-review | Implementation is integrated and under independent review. Close the remaining reconstruction finding: same-schema inconsistent or oversized supervisor status projections must be diagnosed and deterministically rebuilt rather than trusted or allowed to raise. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#failure-and-restart-behavior) |
| LIFE-001 | P0 | Critical | in-review | Integrated in 0.7.0: `force-accept` requires the exact `FORCE-ACCEPT` acknowledgement, writes a read-only receipt linked to the final seal, projects a distinct `force-accepted` state, and preserves ordinary `accept` validation. Authenticated human-only authorization remains blocked on HARD-007; independent phase acceptance remains open. | [`force-accept-override`](../prompt-packs/force-accept-override/phase-0/tickets/LIFE-001-force-accept.md) |
| POL-001 | P0 | High | in-review | Automatic Codex selection is Luna-only with bounded low/medium/high effort, deterministic `-c model_reasoning_effort=...` argv, immutable launch effort evidence, and pre-launch bypass rejection. Focused installed/invariant evidence passes; final phase evidence remains open. | [`codex-luna-effort-policy`](../prompt-packs/codex-luna-effort-policy/phase-0/tickets/POL-001-luna-effort-policy.md) |
| HARD-003 | P0 | Critical | in-progress | A prior root-bind bwrap attempt was rejected because it exposed ambient host files. The recorded design requires exact staged runtime/oracle/source mounts, private HOME/XDG, `--clearenv`, unshared network, cgroup-plus-RLIMIT controls, and fail-closed capability probes; this host cannot create bwrap's required network namespace and must reject governed local execution. Implement the narrow backend and its unavailable-path/installed journeys without weakening the boundary. | [Assessment F39-F42, F69-F73](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#5-guidance-that-should-become-deterministic-enforcement) |
| HARD-006 | P1 | High | ready | All declared implementation prerequisites are accepted. Add content classification, redaction, explicit sensitive-content opt-in, and retention/deletion policy for prompts, argv, logs, messages, provider events, telemetry, and exported reports. | [Assessment F44-F47, F64, F81-F85](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#7-security-posture-by-trust-boundary) |
| HARD-007 | P1 | Critical | ready | HARD-004 is accepted. Replace caller-selected actor labels with authenticated principals for review, acceptance, steering, and future MCP mutation, and enforce independent-review policy from immutable identity evidence. | [Assessment F48-F52, F89](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#5-guidance-that-should-become-deterministic-enforcement) |
| REL-002 | P0 | Critical | in-review | GitHub Private Vulnerability Reporting is the selected primary channel and `SECURITY.md` defines the coordinated-disclosure policy. Closeout requires a repository administrator to enable the GitHub setting and record a successful private-report/notification drill; no public issue or invented email address is an acceptable substitute. | [Public release readiness](PUBLIC_RELEASE_READINESS.md#governance-and-compatibility-blockers) |
| REL-003 | P0 | High | ready | HARD-008 is accepted. Define the supported Linux/Python/tmux/executor matrix and run opt-in live compatibility journeys on representative clean hosts. | [Testing](TESTING.md#live-compatibility) |

## Planned tmux operator experience

The detailed dependency graph, parallel lanes, and acceptance matrix are in the
[tmux operator experience sequence](TMUX_OPERATOR_EXPERIENCE_BACKLOG_SEQUENCE.md).
The [traffic-light status system](TRAFFIC_LIGHT_STATUS_SYSTEM.md) and its
[implementation addendum](TRAFFIC_LIGHT_BACKLOG_ADDENDUM.md) are additive
presentation requirements for this pack; they do not create an authoritative
lifecycle state or supersede the current dependencies below.

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| TMUXUI-001 | P1 | High | blocked | After accepted PROC-006, add one bounded authoritative operator snapshot joining durable run, inbox, and review state with one tmux pane inventory by stable pane ID. Prove deterministic attention ranking, safe sanitization, no-tmux degradation, and no location rebinding. | [`tmux-operator-experience`](../prompt-packs/tmux-operator-experience/phase-0/tickets/TMUXUI-001-operator-snapshot.md) |
| TMUXUI-002 | P1 | Medium | blocked | After TMUXUI-001, add an atomic freshness-aware projection cache and status-line renderer that performs no durable-state or tmux scan during redraw and never overwrites global status configuration implicitly. | [`tmux-operator-experience`](../prompt-packs/tmux-operator-experience/phase-1/tickets/TMUXUI-002-status-cache.md) |
| TMUXUI-003 | P1 | High | blocked | After TMUXUI-001, add an attention-sorted popup/selector with stable-pane focus, current-pane highlighting, bounded escaped preview, and deterministic fallback when `fzf` or popup support is absent. It must not alter managed layout. | [`tmux-operator-experience`](../prompt-packs/tmux-operator-experience/phase-1/tickets/TMUXUI-003-popup-navigation.md) |
| TMUXUI-004 | P1 | Medium | blocked | After TMUXUI-001, add capability detection plus opt-in, namespaced, idempotent install/uninstall assets that preserve existing tmux hooks, status format, intervals, and keybindings. Package installation alone must make no tmux changes. | [`tmux-operator-experience`](../prompt-packs/tmux-operator-experience/phase-1/tickets/TMUXUI-004-opt-in-integration.md) |
| TMUXUI-005 | P1 | High | blocked | After TMUXUI-003 and TMUXUI-004, add stale-selection revalidation, deterministic next-attention navigation, confirmations, and lifecycle/message/review actions through existing evidence-preserving services rather than direct destructive tmux commands. | [`tmux-operator-experience`](../prompt-packs/tmux-operator-experience/phase-2/tickets/TMUXUI-005-lifecycle-actions.md) |
| TMUXUI-006 | P1 | Medium | blocked | After TMUXUI-002 through TMUXUI-004, add a reusable dedicated `aw-dashboard` window with attention/tree/detail/preview views. Opening, closing, and refreshing it must not change agent capacity, work-window geometry, or run bindings. | [`tmux-operator-experience`](../prompt-packs/tmux-operator-experience/phase-2/tickets/TMUXUI-006-dashboard-window.md) |
| TMUXUI-007 | P1 | High | blocked | After TMUXUI-002 and TMUXUI-004, add namespaced event-hint refresh, burst coalescing, lazy rebuild, and low-frequency repair while preserving replayable durable authority and leaving no busy loop or orphan worker. | [`tmux-operator-experience`](../prompt-packs/tmux-operator-experience/phase-2/tickets/TMUXUI-007-refresh-repair.md) |
| TMUXUI-009 | P1 | High | blocked | After TMUXUI-005 through TMUXUI-007, close clean-wheel, fake-tmux, opt-in real-tmux/fzf, security, package-data, docs/help/man-page, install/uninstall, drift-audit, and sealed acceptance evidence without claiming the broader REL-003 compatibility matrix. | [`tmux-operator-experience`](../prompt-packs/tmux-operator-experience/phase-3/tickets/TMUXUI-009-acceptance-and-docs.md) |
| TMUXUI-008 | P2 | Medium | needs-decision | Only after the core independent gate and explicit maintainer authorization, add a first-class `@agent-workflow-role=ui` and optional embedded sidebar. Prove deterministic capacity/layout under concurrent launch and complete reversible removal. | [`tmux-operator-experience`](../prompt-packs/tmux-operator-experience/phase-4/tickets/TMUXUI-008-optional-sidebar.md) |

## Release and maintenance follow-up

These items are release mechanics or behavior-preserving maintenance. They do not create alternate ownership for HARD, MCP, messaging, or product-feature work. Active modularization work is owned by the `feature-modularization` prompt pack and must preserve stable public behavior while moving optional capabilities behind explicit feature boundaries.

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| REL-008 | P1 | High | in-review | Bootstrap, deterministic Linux/WSL2/macOS installer bundles, checksums, tag-only GitHub release publishing, and installed-product installer tests are implemented. Close with a real immutable tag/release run and representative clean-host install/uninstall evidence. Native Windows remains out of scope. | [`release-installers`](../prompt-packs/release-installers/phase-0/tickets/P0-00-baseline-and-preflight.md) |
| REL-009 | P1 | High | ready | Add an opt-in, source-controlled post-commit hook installer that triggers the local `agent-workflow-local` Jenkins job only for commits that advance local `master`; prove the queued build records the matching revision and hook failures never block a successful commit. | [Jenkins CI/CD boundary](JENKINS_CI.md) |
| MAINT-004 | P0 | Critical | in-review | Integrated repair `e817fe2` binds review ticket identity in the immutable launch contract and proves valid/mismatched read-only review collection cases. It awaits independent sealed review/acceptance evidence. | [Execution protocol](references/EXECUTION_PROTOCOL.md#completion-and-closeout) |
| MAINT-005 | P0 | High | in-review | Integrated repair `3c124bf` fails acceptance-capable reviews without an immutable recorded tier and makes generated completion criteria typed objects. Focused delegation/completion evidence, pack validation, and release audit pass; await independent sealed review/acceptance evidence. | [Execution protocol](references/EXECUTION_PROTOCOL.md#completion-and-closeout) |
| MAINT-003 | P0 | High | in-review | Integrated repair `73abdd8` imports/replays sealed terminal completion once without treating it as reusable, while explicit `--keep-alive` remains `idle_reusable`. Focused installed/invariant evidence, pack validation, and release audit pass; await independent sealed review/acceptance evidence. | [Execution protocol](references/EXECUTION_PROTOCOL.md#stop-controls) |
| MAINT-006 | P0 | Critical | in-progress | Full index verification rejects current MAINT-005 review closure because host historical run directories contain obsolete schemas and incomplete retired artifacts. The first repair merged a narrow archive-only classifier; live installed verification showed the same historical evidence remains under `state/runs`, so the follow-up must recognize non-active, unsealed legacy records without treating them as valid/current or weakening unsafe-path and current-integrity failures. Prove an installed host journey and rerun the blocked reviews. | [SQLite evidence index](SQLITE_EVIDENCE_INDEX_ARCHITECTURE.md#rebuild-and-incremental-synchronization) |
| MAINT-001 | P2 | Medium | in-progress | Behavior-preserving slices now isolate process environment/redaction policy, authoritative argparse construction, shared CLI output rendering, the complete `index`, `workflow`, `worktree`, `pack`, `orchestrator`, reusable-agent, evaluation, comparative-benchmark, session/lifecycle, supervisor, core utility, and sealed-run reporting command handlers, plus CLI argument normalization/plugin bootstrap and delegated-session filesystem artifact construction and durable operator messaging/lifecycle controls, and SQLite database identity/migration ownership and safe source discovery/stable evidence reads, plus pure read-only query construction/report shaping, behind existing facades. `agent_workflow.cli_handlers.index` owns index dispatch and domain-specific query rendering; `agent_workflow.cli_handlers.workflow` owns workflow template/service dispatch; `agent_workflow.cli_handlers.worktree` owns Git worktree dispatch; `agent_workflow.cli_handlers.pack` owns prompt-pack lifecycle dispatch and validation rendering; `agent_workflow.cli_handlers.orchestrator` owns registry/inbox/watch dispatch; `agent_workflow.cli_handlers.agent` owns durable context, task completion, candidate ranking, and reassignment dispatch; `agent_workflow.cli_handlers.eval` owns evaluation validation, templating, scoring, reporting, trial collection/comparison, Inspect, and SWE-bench export dispatch; `agent_workflow.cli_handlers.benchmark` owns comparative-benchmark validation, readiness, planning, execution, review, reporting, verification, and cleanup dispatch; `agent_workflow.cli_handlers.session` owns launch, observation, operator messaging/control, archival, restart, review, acceptance, and force-accept dispatch while preserving durable authority and pane-cap policy; `agent_workflow.cli_handlers.supervisor` owns one-shot and loop remediation dispatch while preserving policy construction and report schemas; `agent_workflow.cli_handlers.core` owns command catalogs, plugin inventory, doctor, completion, and configuration dispatch; `agent_workflow.cli_handlers.reporting` owns sealed-run assessment and evaluation-ledger output dispatch; `agent_workflow.cli_runtime` owns global-option normalization, explicit launch-command separation, version-safe configuration bootstrap, and plugin suppression/loading; `agent_workflow.session_artifacts` owns worktree excludes, completion handoff creation, state links, runner scripts, and prompt-pack discovery/identity; `agent_workflow.session_control` owns durable steer/progress/ack messaging, cursor-based replay/wait, child lifecycle denial, interrupt, terminate, and kill controls; `agent_workflow.index_schema` owns application ID, schema version, migration SQL, and header validation while `index_store` retains discovery/reconciliation/query APIs and exact database behavior. Continue with `sessions.py`, additional CLI dispatch domains, index discovery/reconciliation/query, `runner.py`, and remaining `process.py` concerns independently; do not combine refactoring with new product scope. | [2026-08-01 review](BACKLOG_AND_ARCHITECTURE_REVIEW_20260801.md#files-that-should-be-split) |

## Dependency-gated work

These items are blocked by the prerequisite named in their row, or are partially implemented but cannot close until external or security evidence exists.

| ID | Priority | Risk | State | Missing prerequisite and exit evidence | Reference |
|---|---|---:|---|---|---|
| MSG-003 | P0 | Critical | blocked | After MSG-002, HARD-004, HARD-006, HARD-007, and HARD-008, add fixed-format orchestrator wake/resume adapters that receive opaque event IDs only and cannot inject child-controlled content. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#the-supervisor-must-wake-the-orchestrator-safely) |
| MSG-004 | P1 | High | blocked | After MSG-002, MSG-003, MSG-005, and HARD-007, distinguish durable event delivery, orchestrator application acknowledgement, and linked scheduling/lifecycle action evidence through shared services. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#acknowledgement-model) |
| MSG-006 | P1 | Critical | blocked | After the integrated messaging implementation and HARD-001/HARD-002/HARD-004/HARD-006/HARD-007/HARD-008, harden identity, bounds, redaction, no-follow storage, duplicate IDs, prompt injection, notification templates, resource use, and supervisor ownership adversarially. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#security-requirements) |
| MSG-007 | P1 | High | blocked | After MSG-001 through MSG-005 and BKL-002, add installed-wheel completion/wakeup/restart/action journeys plus opt-in real tmux and supported executor compatibility tests; keep low-level tests limited to compact security/replay matrices. | [Messaging design](ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#acceptance-strategy) |
| HARD-009 | P1 | High | blocked | After HARD-003 through HARD-008, generate command/man/schema/service inventories from code; enforce backlog-to-pack ownership, valid state transitions, satisfied-prerequisite promotion, and active-versus-completed grouping; detect stale docs/skills/diagrams/future tests; and make the drift audit a release gate. | [Assessment F01-F02, F09-F10, F90-F96](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#8-public-release-direction) |
| HARD-010 | P1 | High | blocked | After FOUND-GATE-01 and ISO-GATE-01, complete transitive dependency locking and vulnerability audit, standards-based SBOM generation, wheel/source provenance, independent reproducibility checks, and authenticated release signing/attestation against the integrated hardened tree instead of custom signing or SBOM formats. | [Assessment F13-F14](FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#4-feature-and-component-inventory) |
| BKL-004 | P1 | High | in-review | The subscription-first Codex/Claude adapters, optional API adapters, readiness preflight, paired retry isolation, cohort statistics, cost semantics, and sealed reporting are implemented. After HARD-003, HARD-006, and REL-003, execute and independently accept the first controlled real-provider cohort; do not manufacture that external evidence in development. | [Operations](COMPARATIVE_BENCHMARK_OPERATIONS.md) |
| MCP-003 | P1 | Critical | blocked | After HARD-004, HARD-005, and HARD-007, add idempotent pack validation, worktree creation, bounded launch, workflow validate/start/status/resume, progress, ack, and steer tools through existing services. Preserve the current read-only capability/catalog resources; MCP launch must reuse the CLI launch service and retain launch-contract v2 command artifacts/digests rather than creating MCP-local command or launch authority. | [MCP server](MCP_SERVER.md#planned-mutation-phase) and [`mcp-server-next`](../prompt-packs/mcp-server-next/) |
| REL-004 | P1 | Critical | blocked | After all P0 HARD items, HARD-010, accepted REL-002 channel evidence, and REL-003, execute the public-preview gate: clean-source build/install/uninstall, signed artifacts, drift audit, live compatibility, threat-model review, and explicit go/no-go record. | [Public release readiness](PUBLIC_RELEASE_READINESS.md#release-gate) |
| BKL-010 | P1 | Medium | in-review | Runtime attestation, the publication container definition, content-addressed sealing, browser/font digest enforcement, viewport contract, and publication readiness gate are implemented. Build/publish the image and independently verify its immutable digest before the first publication claim. | [Operations](COMPARATIVE_BENCHMARK_OPERATIONS.md#publication-visual-runtime) |

## Comparative benchmark scoring correction

The current `priority-picker-v1` evaluator is authoritative for historical v1 reports, but its equal-share implementation, frozen matrix, version labels, browser coverage, and public-test credit are not fully aligned. The `comparative-benchmark-scoring-corrections` prompt pack owns the correction program. It must preserve v1 evidence, create a new major benchmark version for changed semantics, keep the benchmark inside the built-in `agent_workflow.benchmarking` boundary, synchronize repository and installed assets, and avoid adding a benchmark-specific plugin hook system.

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| BENCH-CORR-001 | P0 | Critical | ready | Freeze an exact machine-readable corrected scoring contract, resolve the current spec `1.1.0` versus matrix `1.0.0` identity conflict, assign every point and evidence producer, preserve v1 semantics, and define the new major-version boundary. | [Ticket](../prompt-packs/comparative-benchmark-scoring-corrections/phase-0/tickets/BENCH-CORR-001-scoring-contract.md) |
| BENCH-CORR-010 | P1 | Medium | ready | Decide whether time, tokens, and cost remain descriptive, become non-inferiority limits, or produce a separate value verdict while preserving truthful subscription/API cost fields and critical-path timing. | [Ticket](../prompt-packs/comparative-benchmark-scoring-corrections/phase-0/tickets/BENCH-CORR-010-efficiency-policy.md) |
| BENCH-CORR-002 | P0 | Critical | blocked | After BENCH-CORR-001, implement explicit per-check weighted scoring, versioned receipts, strict missing/unknown/over-award rejection, and v1 compatibility in the built-in benchmark feature. | [Ticket](../prompt-packs/comparative-benchmark-scoring-corrections/phase-1/tickets/BENCH-CORR-002-weighted-scorer.md) |
| BENCH-CORR-003 | P0 | High | blocked | After BENCH-CORR-002, expand corrected-version formula, validation, ordering, filter/sort/export, determinism, non-mutation, malformed-load, and sealed scale evaluations with mutation isolation. | [Ticket](../prompt-packs/comparative-benchmark-scoring-corrections/phase-1/tickets/BENCH-CORR-003-functional-validation-evals.md) |
| BENCH-CORR-004 | P0 | High | blocked | After BENCH-CORR-002, add deterministic browser interaction, verified download content, empty/invalid states, visible focus, no-trap, responsive, reduced-motion, and accessibility evidence without conflating runtime trust with UI quality. | [Ticket](../prompt-packs/comparative-benchmark-scoring-corrections/phase-1/tickets/BENCH-CORR-004-browser-accessibility-evals.md) |
| BENCH-CORR-005 | P1 | High | blocked | After BENCH-CORR-002, decide and implement granular versus gate-style public scoring and remove or explicitly justify duplicate public-test engineering credit. | [Ticket](../prompt-packs/comparative-benchmark-scoring-corrections/phase-1/tickets/BENCH-CORR-005-public-scoring.md) |
| BENCH-CORR-006 | P1 | High | blocked | After BENCH-CORR-001, harden blinded review bundles, rating anchors, blocker adjudication, reviewer immutability, multi-reviewer agreement, and human-time reporting. | [Ticket](../prompt-packs/comparative-benchmark-scoring-corrections/phase-2/tickets/BENCH-CORR-006-human-review.md) |
| BENCH-CORR-007 | P0 | Critical | blocked | After corrected machine/browser scoring, add golden, partial, mutation, invalid-guardrail, harness-failure, and visual calibration fixtures with source/install parity and exact expected deltas. | [Ticket](../prompt-packs/comparative-benchmark-scoring-corrections/phase-2/tickets/BENCH-CORR-007-calibration-mutations.md) |
| BENCH-CORR-008 | P1 | High | blocked | After BENCH-CORR-002, make one contract authoritative for matrices, factual docs/man tables, schemas, repository suite, installed mirror, and release-drift validation; preserve the built-in/plugin boundary. | [Ticket](../prompt-packs/comparative-benchmark-scoring-corrections/phase-2/tickets/BENCH-CORR-008-single-source-docs.md) |
| BENCH-CORR-009 | P1 | High | blocked | After calibration and drift controls, reject mixed-version cohorts, seal all scorer/evaluator/fixture/runtime/policy identities, preserve old receipts, and define additive rescore lineage. | [Ticket](../prompt-packs/comparative-benchmark-scoring-corrections/phase-3/tickets/BENCH-CORR-009-version-migration.md) |

The review-only `BENCH-CORR-GATE` follows BENCH-CORR-006, BENCH-CORR-009, and BENCH-CORR-010 and must separately accept or reject development, internal, and publication use.

## Decisions

| ID | Priority | State | Decision | Reference |
|---|---|---|---|---|
| DEC-001 | P0 | decided | Local JSONL authority, per-consumer FIFO, at-least-once append, digest-bound idempotency, rebuildable cursors, and a 2-second normal replay objective. | [Decision](DECISIONS/DEC-001-DURABLE-CONTROL.md) |
| DEC-002 | P1 | decided | Adopt subscription-backed CLI sessions as the default, optional explicit API/access-token adapters, development/internal/publication profiles, separate billed/estimated/subscription-allocation cost semantics, recorded provider-managed caching, one fresh-pair infrastructure retry, separate assistance cohorts, and a 95% paired-bootstrap winner rule. | [Decision](DECISIONS/DEC-002-COMPARATIVE-BENCHMARK-OPERATING-POLICY.md) |
| DEC-003 | P2 | deferred | Authorize multi-host orchestration only after a measured single-host failure. Preserve replayable durable records as authority; prefer JetStream unless an existing Redis dependency is mandated. | — |
| DEC-MCP-HTTP | P2 | deferred | Authorize any non-stdio MCP transport only through a separate security ADR after local adoption evidence. | — |
| DEC-004 | P1 | decided | Retain `agent-workflow` as the execution host, add a versioned trusted plugin API, and build `agent-workflow-spec` as the first sibling plugin before extracting other subsystems. | — |
| DEC-005 | P0 | decided | Adopt a bounded root orchestrator → team lead → worker hierarchy with durable authority and one managed tmux window per team. | [Decision](DECISIONS/DEC-005-HIERARCHICAL-ORCHESTRATION.md) |
| DEC-006 | P0 | decided | Use bounded deterministic self-healing: durable evidence is authoritative; automatic action must be preauthorized, idempotent, attempt-bounded, verified, and incapable of widening authority. | [Decision](DECISIONS/DEC-006-BOUNDED-SELF-HEALING.md) |
| DEC-007 | P0 | decided | Keep JSON/JSONL, immutable snapshots, and sealed receipts authoritative while adding a host-local, single-writer, fully rebuildable SQLite projection for cross-run search and analysis. | [Decision](DECISIONS/DEC-007-REBUILDABLE-SQLITE-PROJECTION.md) |
| DEC-008 | P1 | decided | Run the same task in paired `control_raw/v1` and `workflow_full/v1` worktrees, adopt the synthetic visual priority picker as the first fixture, and weight the initial composite 70% machine / 30% blinded human visual. | [Decision](DECISIONS/DEC-008-INITIAL-COMPARATIVE-BENCHMARK.md) |
| DEC-009 | P1 | decided | Keep a small authority kernel; retain higher-level capabilities as built-in features, optional extras, trusted plugins, or repository-only tooling with explicit distribution boundaries. | [Decision](DECISIONS/DEC-009-FEATURE-MODULE-BOUNDARIES.md) |

## Specification and plugin program

These tasks are designed under decided `DEC-004` and the host boundary in `DEC-009`. `PLUG-001` and `ARC-004` are owned by the `feature-modularization` prompt pack; sibling-spec tasks remain independently gated. The sibling repository remains independent and core must not import it.

| ID | Priority | Risk | State | Work and exit evidence | Reference |
|---|---|---:|---|---|---|
| PLUG-001 | P1 | High | in-review | Entry-point discovery, explicit `[plugins].enabled`, strict API/version checks, atomic typed registration, `plugins list`, `--no-plugins`, command-catalog provenance, exact schema/asset identifier collision checks, digest-bound `importlib.resources` activation, traversal/tamper rejection, and an installed fixture-plugin wheel journey are implemented. Run independent MOD-GATE-1; do not add a general hook framework until multiple plugins require ordered 1:N hooks. | [Plugin mechanism](SPEC_AUTHORING_PLUGIN_ARCHITECTURE.md#plugin-mechanism) |
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
| BKL-007 | P2 | Retain host routing as a separate optional feature module and implement it only after measured direct-delegation routing failures justify the added authority surface. |
| ARC-003 | P3 | Add a multi-host broker, shared-artifact references, and cross-trust signing only after `DEC-003`. |
| MCP-004 | P2 | Add policy-gated review/disposition and interrupt/terminate tools after `MCP-003`; preserve the capability/command-context resources and never infer authorization from catalog membership; force kill remains excluded. |
| WF-006 | P2 | Consider evidence-derived routing recommendations only after comparable real-executor cohorts exist; no online learning or vector-memory dependency. |

## Completed history

Completed task IDs are retained here only to prevent resurrection or duplicate ownership; implementation detail belongs in Git history and the changelog.

| ID | Final disposition | Evidence summary |
|---|---|---|
| BKL-001 | completed | Durable consumer cursors, reconstruction, idempotent handling, and sealed acceptance are complete. |
| BKL-011 | completed | The comparative benchmark requirement-to-evaluation matrix and frozen synthetic fixture were completed for 0.7.5. |
| MSG-001 | completed | Registry/fan-in implementation was independently verified and force-accepted with a sealed operator override. |
| MSG-002 | completed | Supervisor fan-in was independently accepted with sealed critical-tier evidence. |
| HARD-001 | completed | Bounded process execution foundation accepted. |
| HARD-002 | completed | Artifact, path, and schema integrity foundation accepted. |
| HARD-004 | completed | Immutable launch/final-receipt authority accepted; its future-test placeholder has graduated to installed acceptance coverage. |
| HARD-005 | completed | Read-only MCP privacy and path-safety boundary accepted. |
| HARD-008 | completed | Configuration, executor, and host-environment trust foundation accepted. |
| REL-001 | completed | Apache-2.0 selected; LICENSE, package metadata, and release distribution policy are configured. |
| REL-006 | completed | Jenkinsfile and local server-job setup are retained as core repository CI/CD while excluded from installed runtime and release bundles. |
| MAINT-002 | completed | Removed the duplicate MiniYAML parser and made PyYAML safe loading a declared core dependency with adversarial coverage. |
| REL-005 | completed | Structured release policy, SBOM/provenance evidence, and blocker enforcement implemented. |
| CHATGPT-EVAL-001 | completed | Evidence-first sealed-run assessment and truthful evaluation-state coverage completed. |
| CHATGPT-TDD-001 | completed | Strict future specifications established; implemented items graduate out of `tests/future`. |
| REL-007 | superseded | Clean-host compatibility is owned by REL-003; real provider cohorts are owned by BKL-004. The duplicate task is closed. |

| Release | Summary |
|---|---|
| 0.5.1 | Completion handoffs validate before reuse, invalid child bridge intents are rejected, and pending reuse cannot seal as successful. |
| 0.5.0 | Bounded self-healing supervision added with Luna-only automatic Codex policy preserved. |
| 0.3.0 | Sandbox-safe child control bridge, launcher-executable binding, source-snapshot repair, clean wheel builds, and enforceable semantic-version bump checks. |
| 0.3.0 SQLite projection design | `ARC-002` superseded by decided `DEC-007`; implementation is tracked under `IDX-001` through `IDX-007`. |
| 0.1.x | Worktrees, tmux lifecycle, durable state, prompt packs, evaluation, provider adapters, skills, and packaging foundations. |
| 0.2.0 | Workflow DAGs, approvals, result binding, aggregate receipts, templates, routing advice, and provider/trial evidence. |
| 0.2.1 | Authority, replay, locking, symlink, scorer-receipt, provider-accounting, and immutable-input hardening. |
| 0.2.2 | Acceptance-first installed-product tests, compact invariant matrices, strict future TDD journeys, CI, and public-documentation consolidation. |
| 0.2.2 maintenance | Jenkins local pipeline now provisions an isolated Python environment, installs build/test dependencies, avoids stale workspace virtualenvs, builds and locally installs the wheel, and passed build #16 with `35 passed, 2 skipped, 1 xfailed`. |
| 0.2.4 maintenance | Completed evaluation/benchmark templating and REL-005 release evidence: policy/lock validation, structured tests, CycloneDX SBOM, provenance, and blocker enforcement without closing REL-001/002/003 or HARD-010. |
| 0.7.5 comparative benchmark | Completed BKL-011 and implemented the frozen `priority-picker-v1` paired benchmark: coordinator and arm worktrees, concurrent phases, complete timing/usage/cost evidence, 100-point machine scoring, blinded visual review, 70/30 composite, verified consolidation, packaged suite export, and safe cleanup. Publication image evidence and real-provider cohort execution remain BKL-010 and BKL-004. |
| 0.7.6 benchmark operating policy | Decided DEC-002 and implemented subscription-first Codex/Claude adapters, optional API authentication, readiness checks, development/internal/publication policy profiles, fresh-pair infrastructure retries, paired bootstrap intervals, winner thresholds, truthful subscription cost semantics, and publication runtime sealing/attestation. External provider-cohort and registry-image evidence remain operator-run acceptance gates under BKL-004/BKL-010. |
| 0.2.5 spec/plugin design | Added the trusted plugin boundary and sibling `agent-workflow-spec` architecture; DEC-004 is decided while implementation tasks remain separately gated and non-executable. |
| 0.2.5 maintenance | Accepted BKL-001 durable consumer cursors and idempotent handling dispositions with restart, reconstruction, crash-window, isolation, redaction, scope, and sealed-evaluation evidence; see [final acceptance evidence](BKL-001_EVIDENCE_RECOVERY_20260728.md). |
| 0.2.5 command catalog | Added the parser-derived command catalog, role-scoped launch cards, sealed launch-contract v2 bindings, and child environment exports that reduce routine `--help` probing; validated by installed-product acceptance and invariant tests. |
| 0.2.5 MCP command context | Added bounded read-only MCP capability/catalog resources and verified per-run command context/card resources with schema validation, redacted CLI identity, no dynamic tools, and fail-closed digest checks. |
| 0.2.5 Jenkins deployment | Jenkins build #23 on `master` at `5de662c` passed the installed-product/release suite, built the wheel, and installed `agent-workflow 0.2.5` plus `mcp==1.28.1` globally through the host deployment path. |
