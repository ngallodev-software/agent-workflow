# Phase 3 Checkpoint 01 — Primary Skill Authority

Base: `agent-workflow-0.9.0-phase2-implementation-complete-20260826.tar.zst`

Changes:
- hardens the primary `agent-workflow` skill with concise use/do-not-use guidance;
- defines the minimum durable Workflow/Task/Agent Run/Worker and headless/external model;
- makes `delegate` the ordinary delegation path and keeps provider/model routing private;
- states persist-before-deliver, delivery/acknowledgement, completion/evaluation/review/acceptance, provenance, restart-lineage, and sealed-evidence recovery invariants;
- points prompt packs and benchmarks to specialized/advanced use without expanding the ordinary lifecycle;
- thins delegated implementation and phase-gate review skills to compose with the primary lifecycle authority;
- updates prompt-pack-builder so normal pack execution uses `delegate`, retaining lower-level lifecycle commands only for recovery/diagnostics/operator control.

Deferred to later Phase 3 checkpoints:
- parser-derived validation of skill command examples;
- deterministic skill decision/correctness evals and their release gate integration;
- final Phase 3 test/release verification.

Testing: deliberately not run per Phase 3 checkpoint policy.
