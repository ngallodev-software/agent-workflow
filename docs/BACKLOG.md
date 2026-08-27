# Backlog

This is the **only unfinished-work register** for Agent-Workflow. Completed implementation plans, phase reports, and handoff documents belong in source-control/release history rather than the active documentation tree.

Priorities are ordered within each section. An identifier retained here may also be referenced by a machine release policy or ADR. The accepted architecture and execution sequence for the 0.9 product-surface work is [`SKILL_FIRST_SIMPLIFICATION_PLAN.md`](SKILL_FIRST_SIMPLIFICATION_PLAN.md); this backlog remains the sole status register.

## P0 — 0.9 skill-first simplification

Phases 2–4 implementation are complete. `SURFACE-001`, `FLOW-001`, and `PERF-001` were removed after Phase 2 landed the role-scoped command surface, deterministic delegation facade, and common-path startup/context reductions; the facade satisfied the work originally sequenced as Phase 4. `SKILL-001` was removed after the verified Phase 3 primary-skill hardening and behavioral evals landed. Verification remains separate per project policy.

### TEST-001 — Monolithic acceptance-suite teardown reliability

Fix the process/fixture teardown behavior that can leave the full acceptance invocation running after individually passing journeys. The complete acceptance layer must pass and terminate cleanly as one suite for 0.9 closeout.

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
