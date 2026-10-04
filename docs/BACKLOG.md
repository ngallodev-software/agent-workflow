# Backlog

This is the **only unfinished-work register** for Agent-Workflow. Completed implementation plans, phase reports, and handoff documents belong in source-control/release history rather than the active documentation tree. Completed identifiers are intentionally absent from the sections below.

Priorities are ordered within each section. An identifier retained here may also be referenced by a machine release policy or ADR. The accepted architecture and execution sequence for the 0.9 product-surface work is [`SKILL_FIRST_SIMPLIFICATION_PLAN.md`](SKILL_FIRST_SIMPLIFICATION_PLAN.md); this backlog remains the sole status register.

## P0 — Release closeout blockers

### REL-003 — Accept clean-host compatibility evidence

Pin the intended support hosts/executor versions, execute the candidate matrix on clean hosts, seal the evidence references, and change the release compatibility status from `candidate` only when the evidence justifies a support claim.

## P1 — Release, evidence, and publication hardening

### HARD-010 — Reproducible dependency/supply-chain evidence

The committed dependency lock is currently direct-only. Add complete transitive resolution/hashes and the independent reproducibility plus authenticated signing/attestation policy required for a stronger release claim.

### HARD-006 / SUP-003 — Retention, export, and deletion policy

Define the final field-level retention/export/deletion rules for durable telemetry/evidence and any SQLite/offline-analysis export. The rebuildable index must not become a bypass around the authoritative retention policy.

### BKL-004 — Real-executor benchmark evidence gate

Complete the external/real-provider execution and acceptance evidence required before making non-synthetic benchmark claims. Preserve explicit `control_raw` versus `workflow_full` treatment identity and separate task/wrapper/effective-prompt digests.

### BKL-010 — Publication-grade visual runtime evidence

Produce the content-addressed browser image/runtime digest and verified font evidence required for publication-grade visual review. Development capture/sealing mechanics already exist; publication evidence must remain pinned and reproducible.

### BKL-011 — Re-author the agent-job small-task treatment-effect corpus

The retired `agent-job` repository contains a useful six-task human-run A/B suite that compared a competent plain prompt with a structured job/package prompt across: documentation correction, a small bugfix, a behavior-preserving refactor, test-only work, a scope-boundary stress case, and an intentionally ambiguous request.

Preserve the experimental question, not the legacy package format. Re-author these task classes against the current comparative benchmark contracts so they can measure whether Agent-Workflow discipline improves outcomes enough to justify its overhead on small work, where workflow friction matters most. Use current `control_raw` versus `workflow_full` treatment identity, pinned source/fixture/model/executor cohorts, sealed evidence, current scoring contracts, and current review policy.

Retain the strongest neutrality rules from the historical suite: do not reward structure by default; count operator/review friction as a real cost; allow control to be better; allow roughly-equal or inconclusive outcomes; and score from captured evidence rather than evaluator rhetoric. Historical task text, checkout-specific paths, Copilot-only assumptions, hand-maintained model selection, and free-form result templates are not authoritative inputs.

This corpus should also be usable as reusable prompt-pack/corpus-body benchmark data so ordinary implementation prompt packs can contribute comparable task-shape evidence without weakening benchmark isolation.

**Done when:** current versioned benchmark assets cover the six task classes (or a documented non-redundant subset), each task has frozen canonical input and deterministic/public evaluation where feasible, human reviewability/friction is recorded separately from quality, treatment leakage is prevented, and repeated real-executor runs can be consolidated under the existing comparative operating policy.


## P1 — Public integration contracts

### EXT-HOST-002 — Record authorized external Worker exit without fabricating process evidence

An external Worker can complete, publish a valid `agent task-complete` handoff,
and have its host-confirmed exit recorded by an operator, but the public
external-binding contract has no terminal-exit operation. `agent-run finalize`
therefore refuses the run because no AW-owned `process-result.json` exists.
External hosts must not fabricate a PID, return code, or process-result
artifact merely to satisfy that recovery path.

**Reproduction (2026-09-14):**

1. Prepare an external run, bind the host Worker, and call `start-external`.
2. Have the Worker commit its scoped change and publish a schema-valid
   `agent task-complete` handoff.
3. After the external Worker exits, run `agent-workflow agent-run finalize
   RUN_ID`.
4. Observe: `recovery finalization requires a durable process result or a
   confirmed dead orphan observation`; `terminate` and `interrupt` report
   that external worker lifecycle control is not configured.

**Evidence:** OSINT Suite runs `bella-lookout-slice-a-20260914`,
`bella-lookout-slice-a-redaction-20260914`, and
`bella-lookout-slice-b-20260914` had valid completion handoffs and no
AW-owned external process. The first two exposed recovery defects: an
authorized exit was classified as `executor_lost`, then recovery sealing
failed on duplicate projection fields/schema constraints. The local runtime
was patched only to continue the authorized work; those changes are not a
source-controlled Agent-Workflow fix.

**Required design:** add a narrow, authenticated/operator-authorized,
idempotent `external-exit` recording operation for a currently bound external
Worker generation. Record only host-observable terminal facts (for example,
completion reported and exit observed), not a fabricated PID, exit code, or
process result. It must reject stale generations, unbound/prepared runs,
already-sealed runs, and attempts to convert host observation into completion,
review, or acceptance. Recovery finalization may seal a run as `completed`
only when this durable exit record and a valid completion handoff both exist;
otherwise preserve the current refusal/failure behavior.

**Acceptance evidence:** integration tests cover the successful ordered path
`prepared -> bound -> running -> task-complete -> external-exit -> finalized
completed`, repeated exit-record idempotency, stale-generation rejection,
missing/invalid completion refusal, and the absence of any
`process-result.json` requirement for that successful external path. Tests
must also prove that external exit recording does not itself create
completion, review, or acceptance, and that sealed receipts/projections rebuild
without duplicate-keyword or schema failures.

**Implementation evidence (2026-09-14):** `8708d18` adds the generation-bound,
idempotent public operation and recovery path without process fabrication.
Focused invariant and CLI-product coverage passed; independent release
acceptance remains pending Jenkins evidence.

**2026-09-30 readiness update:** PR #51 / `f5a0aa4` also makes external
dispatch fail closed until the active generation has been bound and
`start-external` has recorded the run as running. The full GitHub Actions
matrix passed. The remaining work in this item is the independent external-host
R6D12/Jenkins acceptance exercise; no additional source implementation is
currently identified.

### TERM-001 — Retire external host terminals after terminal Agent Run state

Status remains open. The core implementation intentionally owns no external
terminal or process lifecycle (implementation boundary established); no
host-binding retirement signal has been implemented or independently reviewed,
and no host verification/acceptance evidence exists. A future implementation
must define a bounded, idempotent retirement signal based only on public
terminal status and cover stale PID/reuse safety, normal completion, failure,
interruption, and host restart without changing workflow authority.

**Evidence:** The 2026-08-29 execution runs `TASK-001-a3b4d261`, its retry,
and both review runs have terminal durable status with no live worker PID or
process group. The current core intentionally has no terminal-manager
dependency. The remaining visible background terminal is therefore a host
projection cleanup gap, not a surviving worker process.

### WATCH-001 — Repair watcher prompt-pack contract and independent evidence

The historical `agent-workflow-lifecycle-watch-20260829` prompt pack was
retired with the pre-0.8 pack scaffolding and is not recreated. The current
watcher integration tests are the authoritative evidence surface. Keep the
five-field NOTIFY-001 contract unless a separately approved versioned contract
supersedes it; a schema marker must not be added incidentally.

**Evidence:** `.agent-workflow-handoff/TASK-002-4d2253b8-review/result.json`,
`FINDINGS.md`, and `TASK-002-4d2253b8-final-review/result.json`.

**Current evidence (2026-09-08):** Current source preserves the canonical
exact five-field record and redacts the summary. The focused integration tests
name the live subprocess lifetime journey and the cursor-failure restart
journey directly. The latter forces a cursor-write failure after inbox
persistence, then verifies recovery and the allowed repeat notification while
the durable inbox remains singular. No historical selector/hash sidecar is
current or authoritative.

**Done when:** an independent current review and acceptance chain records the
focused tests and this revision; implementation evidence alone is not
acceptance.

### ORCH-REACT-001 — Watcher-driven deterministic workflow progression

Use the existing `orchestrator watch` process as the long-running driver that
replays durable child events, reconciles one explicitly bound workflow through
current workflow/scheduler authority, launches newly eligible work, and records
bounded durable `attention_required` evidence when no already-authorized
deterministic continuation exists. Do not add a second daemon or use LLM turns
as the clock that advances routine orchestration.

The workflow-aware path must bind an orchestrator explicitly to one workflow
run and canonical snapshot digest; it must not discover workflow authority by
scanning state directories. Inbox-only orchestrator registries remain valid.
Replay is at-least-once while workflow effects remain exactly-once through
authoritative workflow/Agent Run evidence and restart-safe reaction/cursor
handling.

The existing watcher notification callback remains advisory and may be invoked
only after durable attention evidence is committed. Callback failure cannot
roll back or authorize inbox, workflow, scheduler, review, or acceptance state.
No callback is required for deterministic progression.

**Decision:** [`DEC-009`](DECISIONS/DEC-009-WATCHER-DRIVEN-ORCHESTRATOR-PROGRESSION.md).

**Explicit non-goals:** Codex App Server wake/resume transport, generalized
host notification transport, a notification plugin framework, and Typesafe AI
decision augmentation. Those remain deferred until the deterministic
watcher/reactor path is proven.

**Done when:** a real end-to-end journey starts `orchestrator watch`, then
durably completes running node A after the watcher is already active, issues no
manual `react_once`, `workflow resume`, inbox import, status, or equivalent
tick, and observes dependent node B launch exactly once. Restart/replay must
not launch B twice. Acceptance also requires invalid completion to remain
non-progressing, inbox-only watch compatibility, durable attention before
advisory notification, callback-failure recovery, and preservation of distinct
completion/evaluation/review/acceptance gates.

### EXEC-001 — Make completed implementation evidence revision-bound

Status remains open pending independent review and acceptance. Completion
validation must reject a claimed completed implementation when its
changed files are not committed to a distinct revision, and delegated prompt
packs must instruct workers to commit before closeout. The first watcher task
and its retry demonstrate that schema-valid sidecars alone are insufficient.

**Evidence:** `TASK-001-a3b4d261` failed because changed files had no distinct
committed revision; `TASK-001-a3b4d261-retry1` failed due placeholder
completion criteria. Preserve those sealed failures as evidence rather than
rewriting them.

**Implementation evidence (2026-09-08):** Completion validation rejects both
observed failures, and transactional preparation rollback is implemented and
covered by focused tests. This is implementation evidence only; no independent
review or acceptance disposition is recorded yet. The original sealed failures
remain preserved evidence.

The transactional preparation requirement is:
`prepare()` writes run/handoff artifacts before it claims the name lease, and
can also leave an unusable `prepared` run if it fails after lifecycle
initialization but before runner creation. Add rollback for only invocation-
owned artifacts plus lease release, without altering intentional preflight
failure records or sealed runs.

### MCP-003 / HARD-007 — Authenticated, idempotent MCP mutation phase

The current MCP server remains local-stdio and read-only. Mutation work is blocked on authenticated principal semantics plus durable idempotency/replay-safe result mapping.

When authorized, bounded mutation tools may wrap existing application services for validation, worktree creation, Agent Run/workflow operations, and durable messaging. They must produce the same durable artifacts as CLI paths, preserve actor provenance, and never treat tool response delivery as steering acknowledgement. Network transport and destructive lifecycle/review operations require separate policy decisions.

## P2 — Optional host integration

### HERDR-001 — Separate Herdr plugin

Only after `ROLE-001`, `BIND-001`, and `API-001` stabilize, write and approve a separate Herdr plugin specification, then implement it as a one-way consumer of public Agent-Workflow contracts.

The plugin may own workspace/presentation, launching a prepared external worker, best-effort live delivery after persistence, focus/navigation, review presentation, and binding recovery. It must not become a core dependency, durable-message authority, review/acceptance authority, worktree-provenance authority, or source of Agent Run identity.

**2026-10-02 live Herdr launch friction — implementation still open:**
Three prepared interactive Codex GPT-6-Luna runs in Codebase Memory CLI were
successfully launched and observed working in Herdr panes `wC:p5`, `wC:p6`,
`wC:p7`. Each uses an independent worktree at base `51aa7a86`, an external
binding at generation 1, and correlated worker acknowledgement of initial
steering. This proves launch/delivery/acknowledgement for this host, not worker
completion, evaluation, review, acceptance or terminal retirement.

Observed friction to address in the separate host adapter/specification:

- **Caller context propagation:** the agent's shell tool had no `HERDR_ENV`,
  `HERDR_WORKSPACE_ID`, `HERDR_TAB_ID` or `HERDR_PANE_ID`, despite the user
  confirming Herdr and the live server showing this Codex session in `wC:p1`.
  An initial skill preflight therefore blocked launch. After explicit user
  correction, setting the flag and verifying current pane/process/cwd resolved
  it. Determine where the runtime drops context; a flag alone is not proof of
  ownership. Recover via verified host identity or report a precise mismatch,
  without silently selecting another client's focused pane.
- **Manual launch choreography:** the operator had to read native command argv,
  create shell panes, start/detect each named interactive agent, bind each run,
  record `start-external`, persist steering, submit prompts, report delivery,
  and inspect correlated acknowledgements in separate calls/custom temporary
  scripts. Provide one restart-safe host adapter operation consuming an already
  prepared contract and returning run/name/pane/generation/delivery references.
  Persist each stage so retry after any failure does not duplicate panes,
  workers or submitted prompts; preserve user focus and requested geometry.
- **Per-run permission intent:** installed Codex interactive defaults requested
  approvals (`on-request`) while the user explicitly authorized full permissions
  and `never`. A task-scoped copy of runtime configuration was needed before
  prepare so immutable argv recorded `danger-full-access` / `never`; global
  config was preserved. Provide explicit authorized per-run overrides with
  contract provenance, rather than post-prepare mutation or global edits.
- **Credential/configuration coupling:** prepare initially failed with
  `decision mode 'comparative' requires TYPESAFE_API_KEY in the runtime
  environment`, even with explicit executor/model and external interactive
  mode. Sourcing the authorized environment fixed it. Investigate whether this
  launch genuinely requires a semantic decision; do not assume a core defect
  without tracing policy. Surface the dependency before worktree/launch work,
  and support deterministic launch when policy permits. Secret availability
  in the controller must not imply availability in a new interactive pane.
- **State/provenance clarity:** `agent-run provenance` exposed `started_at`
  while external status was still `prepared`, `worker_alive` was null, and no
  Herdr worker had launched. `start-external` later supplied actual start
  evidence. Clarify preparation/process start/host activity in public views;
  no timestamps or host `working` badge may imply completion or acceptance.
- **Bidirectional synchronization:** initial and Jev follow-up steering needed
  manual persist -> Herdr prompt -> delivery report -> worker ack handling.
  Consume pending delivery through the active generation and correlate acks;
  recover after host restart, moved/closed panes, changed worker sessions and
  stale bindings. Collect bounded host observations/evidence references without
  fabricating process exits or making terminal-manager state authoritative.

The per-run JSON contracts correctly carried GPT-6-Luna and full permission
arguments; generation-bound binding/start and worker acknowledgements worked.
Reuse those public contracts rather than adding a competing lifecycle or
making Herdr a core dependency. Controller-created temporary scripts are launch
evidence/observed friction, not accepted product implementation.

**Closeout observation (2026-10-02):** both daemon/cache workers reported
successful `agent finish --result partial`, and valid current-SHA
`handoff/completion.json` existed, while the controller public summary remained
running with a blocked placeholder completion at the base SHA. After verified
Herdr pane closure, generation-bound `external-exit` and `finalize` correctly
sealed valid partial completion at `028a4bfb` / `fa5a180b` and closed assignments.
Clarify the interactive `finish` versus host-exit/finalization boundary so workers
cannot imply durable finalization from handoff publication alone. Preserve the
successful recovery path; partial completion must remain unevaluated/unaccepted.

**Acceptance for this follow-up:** the adapter/spec handles the three-worker
right-column journey with preserved focus and isolated worktrees; injected
failure/retry at every launch/delivery stage yields one binding/worker/prompt;
missing caller context and stale/moved pane identity fail safely or recover from
verified identity; authorized permissions and credential requirements are
visible before launch; delivered/unacknowledged/applied states remain distinct;
external completion/exit/review/acceptance retain their existing authority.
Require real-host evidence in addition to deterministic adapter tests. These
launches do not close `HERDR-001`, `EXT-HOST-002`, or `TERM-001`.

**Evidence:** Agent Runs `CBM-DAEMON-OWNERSHIP-20261002`,
`CBM-RESCRIPT-HANG-20261002`, `CBM-CACHE-STORES-20261002`; native launch contracts,
external binding/event journals and message-state in their run directories.
Host start/prompt/ack captures and assignment manifest:
`/home/nate/.local/state/agent-workflow/handoffs/CBM-THREE-VERTICALS-20261002/`.

## P2 — Upstream specification integration


### OPENSPEC-001 — Complete the qualified OpenSpec migration boundary

OpenSpec is the selected upstream planning/change authority. Agent-Workflow
should consume a narrow, version-qualified import surface rather than continue
growing a local SpecGen planning representation. The first implementation slice
is under review in PR #49 and targets published OpenSpec 1.13.2, built-in
`spec-driven` v1, one local Git repository/change, strict CLI validation,
content-addressed source-specification import evidence, and Agent-Workflow-owned
`native-job/v2` / `job-binding/v2` execution contracts.

Keep planning authority and execution authority separate: OpenSpec owns planning
state; Agent-Workflow owns launch, scope, evidence, evaluation, independent
review, acceptance, and sealed historical receipts. Legacy `native-job/v1`
and SpecGen-derived historical runs remain readable compatibility evidence and
must not be rewritten.

**Done when:** the Phase-0 import path is independently reviewed and accepted;
the real compatibility gate passes against the pinned published OpenSpec
release with the legacy SpecGen contract package absent; new OpenSpec-backed
runs no longer require SpecGen planning authority; and the remaining SpecGen
compatibility surface is explicitly frozen or retired without changing sealed
historical evidence. Custom OpenSpec schemas/stores and multi-repository
planning remain out of scope until separately justified.

### TYPE-001 — Expand TypeSafe only at proven semantic seams

**Status:** built-in routing provider integrated; future seams remain evidence-gated

Current comparative coverage is intentionally limited to registered runtime semantic decisions with deterministic authority preserved. Future candidates are evidence-support assessment, bounded failure classification when deterministic categories are insufficient, remediation-strategy advice over an allowed finite set, and planner/decomposition selection where a deterministic fallback and real consumer exist.

Treat additive semantic evidence separately from comparative replacement: a useful TypeSafe question does not need a fake equivalent deterministic score, but it does need an existing deterministic authority/fallback path, bounded projected state, an explicit consumer, uncertainty handling, and a receipt explaining provider failure or policy rejection. Keep lifecycle ownership, leases, duplicate prevention, executor/process facts, authorization, state transitions, evidence existence, and acceptance authority deterministic-only.

**Done when:** each promoted seam has a versioned question set, reachable production boundary, deterministic fallback/authority path, shadow evaluation evidence, explicit policy, and regression coverage preventing silent bypass.

**Checkpoint mechanism work (2026-10-01):** [DEC-010](DECISIONS/DEC-010-SEMANTIC-DECISION-CHECKPOINT.md) records the provider-neutral semantic checkpoint direction after the Agentic-Jev manager self-gating finding. The first mechanism seam is `implementation.proposal_selection/v1`: DecisionDraft -> neutral evidence projection -> semantic evidence -> mandatory reconciliation -> DecisionResolution. Phase 1 is intentionally a pure checkpoint prototype; production workflow-node gating, replay on the six known manager cases, and any disjoint preregistered effectiveness cohort remain separate later phases. LangGraph and Temporal are deferred because they would duplicate current Agent-Workflow durability/state authority for this seam.

TypeSafe packaging simplification completed in the integrated 0.11.x source: the Agent-Workflow-specific external plugin is retired in favor of a lazy optional built-in provider using official SDK primitives. Historical comparative schema namespaces remain readable only for compatibility.
