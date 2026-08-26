# Backlog

This is the **only unfinished-work register** for Agent-Workflow. Completed implementation plans, phase reports, and handoff documents belong in source-control/release history rather than the active documentation tree.

Priorities are ordered within each section. An identifier retained here may also be referenced by a machine release policy or ADR.

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

Make `skills/agent-workflow/SKILL.md` sufficient to operate the 0.8 lifecycle without repository-specific tribal knowledge. Cover when to use/not use AW, headless versus external workers, Workflow/Task/Agent Run/Worker identity, worktree authority, steer/progress/ack, completion/evaluation/review/acceptance separation, restart lineage, evidence inspection, prompt packs, benchmarks, and recovery.

Specialized skills should reference the primary lifecycle authority rather than duplicate it. Add deterministic skill evals proving that an agent does not invoke a terminal manager, conflate delivery with acknowledgement, accept work on worker exit alone, or lose provenance when selecting external mode.

### BIND-001 — Host-neutral external Worker binding/reconciliation contract

Define a rebuildable external-worker binding projection and idempotent bind/rebind/unbind semantics. At minimum it needs Agent Run/Worker identity, opaque external runtime/worker identity, generation, binding time, and last observation time.

External observations must remain operational projection data: host state cannot become completion or acceptance authority. Define a delivery-adapter boundary that can fetch pending durable messages and report delivery attempts without auto-acknowledging them.

The contract must be implementable by more than one hypothetical host without schema changes.

### API-001 — Stable structured public JSON contracts

Review public structured output for Agent Run prepare/status, pending messages, review/evaluation summary, workflow status, benchmark status, worktree/provenance, and external bindings. Add stable documented JSON contracts where current CLI output is insufficient so integrations do not need private Python imports.

### MCP-003 / HARD-007 — Authenticated, idempotent MCP mutation phase

The current MCP server remains local-stdio and read-only. Mutation work is blocked on authenticated principal semantics plus durable idempotency/replay-safe result mapping.

When authorized, bounded mutation tools may wrap existing application services for validation, worktree creation, Agent Run/workflow operations, and durable messaging. They must produce the same durable artifacts as CLI paths, preserve actor provenance, and never treat tool response delivery as steering acknowledgement. Network transport and destructive lifecycle/review operations require separate policy decisions.

## P2 — Optional host integration

### HERDR-001 — Separate Herdr plugin

Only after `BIND-001` and `API-001` stabilize, write and approve a separate Herdr plugin specification, then implement it as a one-way consumer of public Agent-Workflow contracts.

The plugin may own workspace/presentation, launching a prepared external worker, best-effort live delivery after persistence, focus/navigation, review presentation, and binding recovery. It must not become a core dependency, durable-message authority, review/acceptance authority, worktree-provenance authority, or source of Agent Run identity.

## P2 — Independent spec-generation integration

### SPEC-001 — AW-optimized spec/eval producer boundary

Integrate the independent spec-generation app/skill only through stable machine-readable spec/eval contracts. It should operate without Agent-Workflow while optionally producing AW-optimized prompt-pack/evaluation inputs; do not absorb general planning/spec generation into the already-dense core.
