# BENCH-CORR-003 — Expand hidden functional and validation evaluations

**Backlog:** `BENCH-CORR-003`
**Priority:** P0 / High
**Dependencies:** BENCH-CORR-001 and BENCH-CORR-002
**Parallel lane:** functional evaluator lane
**Baseline:** `agent-workflow` 0.7.9

## Objective

Implement complete corrected-version machine evidence for the Priority Picker data contract, formula, ordering, filtering, sorting, export, loading, determinism, and scale behavior.

## Writable functional scope

The corrected benchmark's hidden evaluator, deterministic fixtures/oracles, contract traceability data, focused evaluator tests, and synchronized package assets. Do not expose hidden oracle content to benchmark arms.

## Required coverage

Cover integer/decimal formula cases, effort floor, rounding boundaries, every tie-break level, score/rank schema, required fields, types/ranges/statuses, booleans, empty/duplicate IDs, useful error identity, empty input, repeated determinism, non-mutation, title/description search, combined filters, supported/invalid sorts, deterministic export schema/content, fixture/malformed loading, and sealed 1,000-item performance.

## Tests and evidence

Add one controlled mutation per weighted functional check. Prove each mutation changes only intended points and evaluator exceptions are classified correctly.

## Acceptance criteria

Every corrected contract requirement has traceable hidden evidence and no hidden check relies on mutable external services.

## Stop conditions

Stop if hidden oracle files become accessible to either arm, timing is unsealed/unrepeatable, or one broad check obscures multiple independently weighted requirements.

## 0.7.9 implementation ownership

- Corrected hidden evaluator and deterministic oracles: `benchmarks/specs/priority-picker-v2/evaluation/` and benchmark-owned hidden/calibration fixtures beneath the corrected suite.
- Installed mirror: `src/agent_workflow/assets/benchmarks/priority-picker-v2/`.
- Built-in interpretation only where generic protocol support is needed: `src/agent_workflow/benchmarking/scoring.py` and `contracts.py`.
- Acceptance/invariants: comparative benchmark tests under `tests/acceptance/` and `tests/invariants/`.

All authority-bearing behavior remains in the built-in `agent_workflow.benchmarking` feature. Do not add a scorer/evaluator hook to the trusted plugin API or create a second registry. Pure contracts and evaluator-result interpretation should remain separable so a later, independently approved ARC-004 extraction can be evaluated without rewriting run authority.
