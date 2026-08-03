# BENCH-CORR-007 — Add golden calibration and mutation acceptance

**Backlog:** `BENCH-CORR-007`
**Priority:** P0 / Critical
**Dependencies:** BENCH-CORR-003, BENCH-CORR-004, and BENCH-CORR-005
**Parallel lane:** calibration lane
**Baseline:** `agent-workflow` 0.7.9

## Objective

Prove the corrected scorer is accurate, isolated, deterministic, and portable between source and installed/exported execution.

## Writable functional scope

Benchmark-owned golden solutions, controlled mutation fixtures, calibration runner/report, focused acceptance tests, package assets, and release checks. Do not expose calibration oracle content to benchmark agents.

## Required fixtures

- one known-good solution earning exactly 100 machine points;
- one frozen partial solution with an exact expected score;
- one controlled mutation for every weighted check;
- guardrail-invalid fixtures producing null machine scores;
- scorer-harness-failure fixtures distinct from solution failure;
- representative visual fixtures for rubric anchors and blocking defects.

## Tests and evidence

Run every fixture repeatedly, from source and from a clean installed package/exported suite. Verify score deltas, receipts, evidence digests, and deterministic outputs except declared volatile fields.

## Acceptance criteria

Every point is mutation-tested, full score is exactly 100, no mutation changes unrelated checks, and source/package results are equivalent.

## Stop conditions

Stop if calibration depends on live model behavior, if fixtures are visible to benchmark arms, or if expected scores are computed by the same unverified logic under test.

## 0.7.9 implementation ownership

- Golden and mutation assets: corrected-suite-owned `calibration/` or equivalent non-agent-visible tree under `benchmarks/specs/priority-picker-v2/`.
- Installed mirror: exact equivalent under `src/agent_workflow/assets/benchmarks/priority-picker-v2/`.
- Calibration orchestration should reuse public benchmark services rather than create a parallel runner.
- Acceptance: `tests/acceptance/test_comparative_benchmark_journey.py` or a dedicated installed-product calibration journey, plus compact mutation invariants.

All authority-bearing behavior remains in the built-in `agent_workflow.benchmarking` feature. Do not add a scorer/evaluator hook to the trusted plugin API or create a second registry. Pure contracts and evaluator-result interpretation should remain separable so a later, independently approved ARC-004 extraction can be evaluated without rewriting run authority.
