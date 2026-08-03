# BENCH-CORR-010 — Decide efficiency treatment

**Backlog:** `BENCH-CORR-010`
**Priority:** P1 / Medium
**Dependencies:** none; may analyze in parallel with BENCH-CORR-001
**Parallel lane:** policy lane
**Baseline:** `agent-workflow` 0.7.9

## Objective

Decide how wall time, active time, tokens, and costs affect benchmark interpretation without silently mixing efficiency into the 100-point quality score.

## Required preflight

Locate current timing definitions, usage aggregation, cost semantics, cohort statistics, winner policy, report rendering, and operating policies. Verify subscription-session and optional API authentication/cost behavior.

## Writable functional scope

The benchmark operating-policy/decision surfaces, winner-policy contract, report semantics, focused policy tests, and explanatory documentation. Do not alter scorer weights or run a live provider cohort.

## Required decision

Choose and document one:

- descriptive efficiency only;
- quality winner plus efficiency non-inferiority limits;
- separate quality and value verdicts;
- a formally specified multi-objective rule.

Preserve distinct provider-billed, API-equivalent estimate, subscription allocation, and local estimate fields. Preserve critical-path wall time separately from summed process time.

## Tests and evidence

Add policy tests for missing costs, subscription semantics, timing field definitions, and any new winner/value threshold. Verify missing provider-billed cost remains null/unavailable rather than zero.

## Acceptance criteria

The policy states exactly how efficiency can and cannot change a verdict, is machine-readable, and is compatible with the phase-0 scoring contract.

## Stop conditions

Stop if the proposal hides cost inside quality points, treats subscription usage as zero cost, or compares incomparable timing definitions.

## 0.7.9 implementation ownership

- Operating-policy authority: `src/agent_workflow/benchmarking/policy.py`.
- Metrics/cost definitions: `metrics.py`, `reporting.py`, and `statistics.py`.
- Versioned suite policies: corrected-suite `policies/*.json`; preserve `priority-picker-v1/policies/`.
- Decision documentation: a new or amended explicit decision under `docs/DECISIONS/` linked from the canonical backlog.

All authority-bearing behavior remains in the built-in `agent_workflow.benchmarking` feature. Do not add a scorer/evaluator hook to the trusted plugin API or create a second registry. Pure contracts and evaluator-result interpretation should remain separable so a later, independently approved ARC-004 extraction can be evaluated without rewriting run authority.
