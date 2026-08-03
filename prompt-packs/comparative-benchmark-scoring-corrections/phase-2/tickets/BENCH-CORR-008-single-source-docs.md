# BENCH-CORR-008 — Establish one authoritative scoring source

**Backlog:** `BENCH-CORR-008`
**Priority:** P1 / High
**Dependencies:** BENCH-CORR-001 and BENCH-CORR-002
**Parallel lane:** drift/documentation lane
**Baseline:** `agent-workflow` 0.7.9

## Objective

Prevent future drift among the scoring contract, evaluator, requirement matrix, benchmark explanation, man page, schemas, and packaged assets.

## Writable functional scope

The authoritative contract, documentation generation/validation tooling, release/drift audit, benchmark docs/man/help surfaces, package asset synchronization, and focused tests. Preserve human-authored rationale where generation is inappropriate.

## Required behavior

Generate or validate from the contract:

- requirement-to-evaluation matrix;
- dimension/check point tables;
- human rubric summary;
- benchmark explanation and man-page factual tables;
- schema check IDs/enums where practical;
- source and exported/package benchmark assets.

A changed weight or check ID must fail drift validation until every derivative is synchronized.

## Tests and evidence

Deliberately alter a contract weight in a test fixture and prove drift validation fails. Build/install/export and compare contract/evaluator asset digests.

## Acceptance criteria

No manually duplicated point table can silently disagree with the authoritative contract, and documentation identifies the exact benchmark/scorer version it explains.

## Stop conditions

Stop if generation overwrites independent rationale or if package assets remain a manually maintained divergent copy.

## 0.7.9 implementation ownership

- Authoritative contract: corrected suite under `benchmarks/specs/priority-picker-v2/`.
- Installed mirror: `src/agent_workflow/assets/benchmarks/priority-picker-v2/`.
- Drift gate: `scripts/audit-release-assets.py`.
- Documentation derivatives: `docs/COMPARATIVE_BENCHMARK_EXPLAINED.md`, `docs/COMPARATIVE_BENCHMARK_SPEC.md`, `docs/COMPARATIVE_BENCHMARK_OPERATIONS.md`, `docs/COMMAND_REFERENCE.md`, and `docs/man/agent-workflow.1`.
- Package inclusion: existing `pyproject.toml` `assets/**/*` contract; no second packaging mechanism.
- Plugin rule: do not add benchmark hooks or require an enabled plugin; future extraction remains ARC-004.

All authority-bearing behavior remains in the built-in `agent_workflow.benchmarking` feature. Do not add a scorer/evaluator hook to the trusted plugin API or create a second registry. Pure contracts and evaluator-result interpretation should remain separable so a later, independently approved ARC-004 extraction can be evaluated without rewriting run authority.
