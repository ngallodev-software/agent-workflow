# BENCH-CORR-009 — Preserve comparability and define migration

**Backlog:** `BENCH-CORR-009`
**Priority:** P1 / High
**Dependencies:** BENCH-CORR-007 and BENCH-CORR-008
**Parallel lane:** migration/reporting lane
**Baseline:** `agent-workflow` 0.7.9

## Objective

Make benchmark and scorer version boundaries explicit so historical v1 evidence remains valid and corrected-version cohorts cannot be mixed accidentally with v1.

## Writable functional scope

Benchmark report/comparison/version validation, receipt/provenance fields, migration documentation, focused compatibility tests, and package assets. Do not rewrite original receipts.

## Required behavior

- Render and verify old v1 reports unchanged.
- Reject mixed-version cohort/winner calculations by default.
- Record benchmark version, scorer version, contract digest, evaluator digest, fixture digest, visual-runtime digest, and policy digest in corrected runs.
- If rescoring old worktree output is supported, write additive lineage-linked receipts and retain original scores.
- Label cross-version summaries as non-comparable unless a separately approved normalization method exists.

## Tests and evidence

Test v1-only, corrected-only, mixed-version, and optional rescore flows. Prove original files/digests remain unchanged.

## Acceptance criteria

No command or report can silently compare incompatible score semantics, and old evidence remains independently verifiable.

## Stop conditions

Stop if migration requires mutating old receipts, if version identity is inferred from file location alone, or if mixed cohorts can still declare a winner.

## 0.7.9 implementation ownership

- Version identity/validation: `src/agent_workflow/benchmarking/contracts.py`, `scoring.py`, and versioned schemas.
- Cohort compatibility and claims: `reporting.py` and `statistics.py`.
- Consolidated provenance: `consolidation.py` and report schemas.
- CLI behavior remains through `cli_handlers/benchmark.py`; keep the handler thin.
- Tests must cover v1-only, v2-only, mixed-version rejection, and additive rescore lineage.

All authority-bearing behavior remains in the built-in `agent_workflow.benchmarking` feature. Do not add a scorer/evaluator hook to the trusted plugin API or create a second registry. Pure contracts and evaluator-result interpretation should remain separable so a later, independently approved ARC-004 extraction can be evaluated without rewriting run authority.
