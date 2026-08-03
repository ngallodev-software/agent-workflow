# BENCH-CORR-005 — Resolve public regression and duplicate-credit semantics

**Backlog:** `BENCH-CORR-005`
**Priority:** P1 / High
**Dependencies:** BENCH-CORR-001 and BENCH-CORR-002
**Parallel lane:** public scoring lane
**Baseline:** `agent-workflow` 0.7.9

## Objective

Implement the phase-0 decision for public-suite scoring and remove or explicitly justify duplicate public-test credit in engineering quality.

## Writable functional scope

The corrected public-test scorer, engineering-quality checks, scoring contract, focused tests, generated documentation inputs, and package assets. Preserve v1 all-or-nothing behavior for v1 reports.

## Required behavior

- Implement either granular public scoring or the explicitly chosen gate scoring.
- Produce structured evidence showing which public requirements passed.
- Apply the documented result of a one-test failure.
- Remove duplicate credit or label and justify the distinct engineering signal.

## Tests and evidence

Use fixtures with zero, one, and multiple public failures. Assert exact score deltas and no unintended effect on hidden checks.

## Acceptance criteria

Code, contract, matrix, and documentation agree exactly on public-test points and engineering-quality interaction.

## Stop conditions

Stop if the scorer parses brittle human-formatted test output when structured results are available, or if v1 semantics would change.

## 0.7.9 implementation ownership

- Corrected visible tests: `benchmarks/specs/priority-picker-v2/fixture/starter/tests/public/`.
- Corrected public evaluator/scoring map: corrected suite `evaluation/evaluate.py` and the accepted scoring contract.
- Generic receipt validation: `src/agent_workflow/benchmarking/scoring.py` only as required.
- Installed mirror and controlled failure fixtures: corrected packaged suite and focused invariants.

All authority-bearing behavior remains in the built-in `agent_workflow.benchmarking` feature. Do not add a scorer/evaluator hook to the trusted plugin API or create a second registry. Pure contracts and evaluator-result interpretation should remain separable so a later, independently approved ARC-004 extraction can be evaluated without rewriting run authority.
