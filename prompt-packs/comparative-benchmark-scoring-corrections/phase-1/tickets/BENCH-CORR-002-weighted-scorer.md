# BENCH-CORR-002 — Implement explicit weighted scoring

**Backlog:** `BENCH-CORR-002`
**Priority:** P0 / Critical
**Dependencies:** BENCH-CORR-001
**Parallel lane:** scoring engine lane
**Baseline:** `agent-workflow` 0.7.9

## Objective

Implement the accepted corrected-version scoring contract with explicit per-check weights and deterministic score receipts.

## Writable functional scope

The current machine scorer/evaluator framework, corrected-version contract loader, scorer result schema, focused tests, and package-export assets. Preserve the v1 scorer as a separate versioned path.

## Required behavior

- Load exact weights from the authoritative contract.
- Record check maximum, earned points, state, evidence reference, and explanation.
- Reject missing, duplicate, unknown, or over-awarded checks.
- Support only contract-defined partial credit.
- Keep eligibility guardrails outside numerical quality arithmetic.
- Keep harness failure distinct from solution failure.
- Seal scorer/evaluator/contract identities in receipts.

## Tests and evidence

Test exact arithmetic, rounding, malformed results, missing evidence, contract digest mismatch, and v1 compatibility. Run an installed/exported suite against a controlled known fixture.

## Acceptance criteria

A corrected full-pass result equals exactly 100, every point is attributable to a check, and v1 reports retain their original semantics.

## Stop conditions

Stop if the implementation uses equal-share fallback, infers weights from check count, changes v1 receipts, or permits uncontracted points.

## 0.7.9 implementation ownership

- Built-in score authority: `src/agent_workflow/benchmarking/scoring.py`.
- Contract parsing/validation: `src/agent_workflow/benchmarking/contracts.py` and the accepted new schema.
- Corrected suite evaluator protocol: `benchmarks/specs/priority-picker-v2/evaluation/evaluate.py` and its installed mirror.
- Score receipt schema: new version under `schemas/`; do not reinterpret `benchmark-machine-score-v1.schema.json`.
- Focused invariants: `tests/invariants/test_comparative_benchmark_contracts.py` plus new narrowly scoped tests when separation improves readability.

All authority-bearing behavior remains in the built-in `agent_workflow.benchmarking` feature. Do not add a scorer/evaluator hook to the trusted plugin API or create a second registry. Pure contracts and evaluator-result interpretation should remain separable so a later, independently approved ARC-004 extraction can be evaluated without rewriting run authority.
