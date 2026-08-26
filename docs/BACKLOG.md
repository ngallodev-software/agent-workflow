# Backlog

This is the **only unfinished-work register** for Agent-Workflow. Completed implementation plans, phase reports, and handoff documents belong in source-control/release history rather than the active documentation tree.

Priorities are ordered within each section. An identifier retained here may also be referenced by a machine release policy or ADR. The accepted architecture and execution sequence for the 0.9 product-surface work is [`SKILL_FIRST_SIMPLIFICATION_PLAN.md`](SKILL_FIRST_SIMPLIFICATION_PLAN.md); this backlog remains the sole status register.

## P0 — 0.9 skill-first simplification

### SURFACE-001 — Minimize the normal agent-visible command surface

Make launch-scoped command catalogs role/profile scoped rather than exposing the complete parser catalog to every Agent Run. Keep implementation at <= 8 commands, review at <= 12, and introduce a normal skill/orchestrator profile at <= 20 commands / <= 5 KB while retaining the complete parser-derived catalog for explicit maintainer discovery.

### FLOW-001 — Deterministic delegation fast path

Add a thin `agent-workflow delegate` facade over the existing worktree, Agent Run prepare, and headless/external execution services. It must emit the same durable artifacts, support structured JSON, identify failed stages precisely, and never create a parallel lifecycle or implicitly review/accept work.

### PERF-001 — Agent-efficiency baseline and regression budgets

Use the committed Phase 0 baseline to drive measurable reductions without weakening correctness/evidence assertions. Highest-value targets are the 93,997-byte full machine catalog currently written into every launch, approximately 1 s repeated CLI startup for status/catalog operations, and approximately 1.994 s Agent-Workflow lifecycle overhead around a 0.086 s deterministic executor in the reference installed-product journey. Prefer role-scoped launch artifacts, lazy capability/import loading, and in-process composition of the common delegation path before adding persistent services. Do not grow the unit/invariant surface merely to measure efficiency; prefer existing installed-product journeys for dynamic timing and behavior.

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

### SKILL-001 — Harden the primary Agent-Workflow skill

Make `skills/agent-workflow/SKILL.md` sufficient to operate the current lifecycle without repository-specific tribal knowledge, following the concise skill-first boundary in `SKILL_FIRST_SIMPLIFICATION_PLAN.md`. Cover when to use/not use AW, headless versus external workers, Workflow/Task/Agent Run/Worker identity, worktree authority, steer/progress/ack, completion/evaluation/review/acceptance separation, restart lineage, evidence inspection, prompt packs, benchmarks, and recovery.

Specialized skills should reference the primary lifecycle authority rather than duplicate it. Add deterministic skill evals proving that an agent does not invoke a terminal manager, conflate delivery with acknowledgement, accept work on worker exit alone, or lose provenance when selecting external mode.

### BIND-001 — Host-neutral external Worker binding/reconciliation contract

Define a rebuildable external-worker binding projection and idempotent bind/rebind/unbind semantics. At minimum it needs Agent Run/Worker identity, opaque external runtime/worker identity, generation, binding time, and last observation time.

External observations must remain operational projection data: host state cannot become completion or acceptance authority. Define a delivery-adapter boundary that can fetch pending durable messages and report delivery attempts without auto-acknowledging them.

The contract must be implementable by more than one hypothetical host without schema changes.

### API-001 — Stable structured public JSON contracts

Review public structured output for Agent Run prepare/status, pending messages, review/evaluation summary, workflow status, benchmark status, worktree/provenance, and external bindings. Add stable documented JSON contracts where current CLI output is insufficient so integrations do not need private Python imports.

### CAP-001 — Progressive advanced-capability isolation

Keep benchmark publication machinery, index administration, MCP/plugin maintenance, release-evidence internals, hierarchy details, and telemetry integrations out of the normal skill/command profile unless requested. Measure import/startup/package cost before extracting code into separate packages; extraction is justified only by a clean one-way boundary and measurable benefit, not file-count aesthetics.

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
