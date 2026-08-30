# Backlog

This is the **only unfinished-work register** for Agent-Workflow. Completed implementation plans, phase reports, and handoff documents belong in source-control/release history rather than the active documentation tree.

Priorities are ordered within each section. An identifier retained here may also be referenced by a machine release policy or ADR. The accepted architecture and execution sequence for the 0.9 product-surface work is [`SKILL_FIRST_SIMPLIFICATION_PLAN.md`](SKILL_FIRST_SIMPLIFICATION_PLAN.md); this backlog remains the sole status register.

## P0 — 0.9 skill-first simplification

Phases 2–4 implementation are complete. `SURFACE-001`, `FLOW-001`, and `PERF-001` were removed after Phase 2 landed the role-scoped command surface, deterministic delegation facade, and common-path startup/context reductions; the facade satisfied the work originally sequenced as Phase 4. `SKILL-001` was removed after the verified Phase 3 primary-skill hardening and behavioral evals landed. Verification remains separate per project policy.

## P0 — Release closeout blockers

### REL-002 — Enable and drill private vulnerability reporting

GitHub Private Vulnerability Reporting is the selected channel, but public-preview closeout still requires administrator enablement and a successful private notification drill consistent with root `SECURITY.md` and `release/release-policy.json`.

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

## P1 — Public integration contracts

### TERM-001 — Retire external host terminals after terminal Agent Run state

Agent-Workflow correctly owns no external terminal or process lifecycle, but
external hosts can leave a background terminal projection visible after the
Agent Run has a sealed terminal outcome. Define and implement a bounded,
idempotent host-binding retirement signal based only on public terminal status;
it must never let host/UI state alter execution, completion, review, or
acceptance authority. Research must verify the observed terminal host, stale
PID/reuse safety, normal completion, failure, interruption, and host restart.

**Evidence:** The 2026-08-29 execution runs `TASK-001-a3b4d261`, its retry,
and both review runs have terminal durable status with no live worker PID or
process group. The current core intentionally has no terminal-manager
dependency. The remaining visible background terminal is therefore a host
projection cleanup gap, not a surviving worker process.

### WATCH-001 — Repair watcher prompt-pack contract and independent evidence

The `agent-workflow-lifecycle-watch-20260829` execution cannot be accepted.
Its initial implementation completions were invalid, the generated `EVAL-002`
selector collected no tests, supplied source hashes were stale, and the final
review found missing live watcher lifetime and duplicate-delivery proof. Keep
the five-field NOTIFY-001 contract unless a separately approved versioned
contract supersedes it; a schema marker must not be added incidentally.

**Evidence:** `.agent-workflow-handoff/TASK-002-4d2253b8-review/result.json`,
`FINDINGS.md`, and `TASK-002-4d2253b8-final-review/result.json`.

**Research conclusion (2026-08-29):** Current source already preserves the
canonical exact five-field record and redacts the summary. The repair is
evidence/test coverage, not a schema change. `EVAL-002` selects no tests;
replace it with concrete current test names. Because `watch()` owns process
signal handlers, prove live watcher lifetime using a subprocess rather than a
thread. Force a source-cursor write failure after inbox persistence to show the
allowed duplicate delivery/restart recovery path while the inbox remains
singular.

**Done when:** the pack precisely names its test selectors, immutable evidence
hashes match the reviewed revision, independent tests demonstrate one active
watcher across child A then B plus duplicate/restart behavior, and a fresh
completion/evaluation/review/acceptance chain is recorded.

### EXEC-001 — Make completed implementation evidence revision-bound

Completion validation must reject a claimed completed implementation when its
changed files are not committed to a distinct revision, and delegated prompt
packs must instruct workers to commit before closeout. The first watcher task
and its retry demonstrate that schema-valid sidecars alone are insufficient.

**Evidence:** `TASK-001-a3b4d261` failed because changed files had no distinct
committed revision; `TASK-001-a3b4d261-retry1` failed due placeholder
completion criteria. Preserve those sealed failures as evidence rather than
rewriting them.

**Research conclusion (2026-08-29):** Completion validation already rejects
both observed failures. The remaining defect is transactional preparation:
`prepare()` writes run/handoff artifacts before it claims the name lease, and
can also leave an unusable `prepared` run if it fails after lifecycle
initialization but before runner creation. Add rollback for only invocation-
owned artifacts plus lease release, without altering intentional preflight
failure records or sealed runs.

### COMP-001 — Preflight completion sidecars and classify their failures correctly

Workers can finish scoped implementation and tests yet submit an intuitive but
schema-invalid criterion value such as `verified` instead of `pass`. Preserve
strict evidence semantics, but add an authoritative preflight validator,
field-level corrective feedback, a bounded handoff-only repair path, and a
completion-schema failure category that cannot be misreported as a missing
command. Details and byte-bound evidence:
[`repo-analysis/AGENT_WORKFLOW_COMPLETION_HANDOFF_AND_NAME_LEASE_INCIDENT_20260830.md`](repo-analysis/AGENT_WORKFLOW_COMPLETION_HANDOFF_AND_NAME_LEASE_INCIDENT_20260830.md).

### LEASE-001 — Retire explicitly abandoned external prepared runs

External `prepared` runs without a worker currently retain preferred agent
names indefinitely: `terminate` correctly cannot control an external host but
does not supply an auditable lifecycle retirement. Add a narrowly guarded,
idempotent abandonment action that records authority before releasing the
name; do not use wall-clock expiry or manual state edits. Details and evidence:
[`repo-analysis/AGENT_WORKFLOW_COMPLETION_HANDOFF_AND_NAME_LEASE_INCIDENT_20260830.md`](repo-analysis/AGENT_WORKFLOW_COMPLETION_HANDOFF_AND_NAME_LEASE_INCIDENT_20260830.md).
### AW-GITDIR-001 — Headless linked-worktree Git administrative scope — COMPLETE

Headless Codex launches now include the resolved Git administrative directory
in their writable scope, with regression coverage for linked Git worktrees.

### BIND-001 — Host-neutral external Worker binding/reconciliation contract — COMPLETE

Implemented in Phase 5. The rebuildable binding projection, idempotent bind/rebind/unbind semantics, generation-guarded pending-delivery retrieval, and transport-attempt reporting are host-neutral and preserve the delivery/acknowledgement boundary. The paired API review found no need for host-specific binding fields.

### API-001 — Stable structured public JSON contracts — COMPLETE

Implemented in Phase 5. Existing structured prepare/status/context, workflow status, benchmark status, and external-binding outputs were retained; bounded message/ack state, completion/evaluation/review summary, and an explicit restricted provenance view were added. `docs/PUBLIC_JSON_API.md` is the integration contract. Normal role-scoped command profiles remain unchanged.

### CAP-001 — Progressive advanced-capability isolation — COMPLETE

Completed in Phase 6. Common-path parser/plugin imports were reduced; publication/visual benchmark implementation is lazy behind explicit benchmark operations; dormant OpenTelemetry/MLflow adapters and dependency surface were deleted; read-only stdio MCP was confirmed already optional and isolated; hook installation now canonicalizes historical duplicate/stale managed state; and Inspect/SWE-bench/SciPy paths are isolated to explicit evaluation operations. No package extraction was justified by measured runtime, cognitive, or maintenance benefit. See `docs/PHASE6_CAPABILITY_ISOLATION.md`.

### MCP-003 / HARD-007 — Authenticated, idempotent MCP mutation phase

The current MCP server remains local-stdio and read-only. Mutation work is blocked on authenticated principal semantics plus durable idempotency/replay-safe result mapping.

When authorized, bounded mutation tools may wrap existing application services for validation, worktree creation, Agent Run/workflow operations, and durable messaging. They must produce the same durable artifacts as CLI paths, preserve actor provenance, and never treat tool response delivery as steering acknowledgement. Network transport and destructive lifecycle/review operations require separate policy decisions.

## P2 — Optional host integration

### HERDR-001 — Separate Herdr plugin

Only after `ROLE-001`, `BIND-001`, and `API-001` stabilize, write and approve a separate Herdr plugin specification, then implement it as a one-way consumer of public Agent-Workflow contracts.

The plugin may own workspace/presentation, launching a prepared external worker, best-effort live delivery after persistence, focus/navigation, review presentation, and binding recovery. It must not become a core dependency, durable-message authority, review/acceptance authority, worktree-provenance authority, or source of Agent Run identity.

## P2 — Independent spec-generation integration

### SPEC-001 — AW-optimized spec/eval producer boundary

Integrate the independent spec-generation app/skill only through stable machine-readable spec/eval contracts. It should operate without Agent-Workflow while optionally producing AW-optimized prompt-pack/evaluation inputs; do not absorb general planning/spec generation into the already-dense core.

Agent-Workflow retains interpretation of its native target projection: it
chooses the actual implementation flow, logical roles and available models,
serial versus parallel scheduling, execution, evaluation, independent review,
and sealing. A SpecGen task DAG or parallelism annotation is evidence and a
planning opportunity, never a forced schedule or runtime routing decision.

**Done when:** the pinned SpecGen release and exact target schemas are captured
as compatibility fixtures or an approved immutable shared-contract bundle;
generated-pack conformance tests exercise the public validator and a
representative execution/review path; incompatible versions or unsupported
target fields fail closed with an actionable diagnostic. If `CONTRACT-001`
adopts the bundle, Agent-Workflow retains semantic ownership and interpretation
of its prompt-pack schema while importing shared schema/descriptor/validation
and negotiation helpers. A SpecGen-generated native target must match the
consumer's exact immutable bundle version and digest. Portable SpecGen packs
remain outside Agent-Workflow's native `prompt-pack/v1` parser until a
separately approved adapter exists. When the shared bundle changes a native
artifact, Agent-Workflow consumes only the bundle's deterministic validated
migration output; it never rewrites sealed historical runs or pack evidence.
