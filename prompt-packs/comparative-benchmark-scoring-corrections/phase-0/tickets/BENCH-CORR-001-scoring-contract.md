# BENCH-CORR-001 — Freeze the corrected scoring contract

**Backlog:** `BENCH-CORR-001`
**Priority:** P0 / Critical
**Dependencies:** none; may analyze in parallel with BENCH-CORR-010
**Parallel lane:** contract lane
**Baseline:** `agent-workflow` 0.7.9

## Objective

Create the authoritative machine-readable scoring contract for a new benchmark major version while preserving the exact interpretation of existing v1 reports.

## Required preflight

Complete the location discovery map. Read the current benchmark specification, requirement matrix, machine evaluator, browser evaluator, visual rubric, report/composite logic, schemas, package assets, tests, docs, and release audits.

## Writable functional scope

The benchmark contract/version surfaces, contract schema/validator, focused compatibility/arithmetic tests, decision/backlog records, and derivative documentation needed to review the decision. Do not edit the actual scorer behavior beyond what is necessary to load/validate a not-yet-active contract.

## Required decisions

- Define unique dimension and check IDs.
- Define exact per-check maximums and partial-credit semantics.
- Make every dimension sum exactly and make the machine total exactly 100.
- Resolve the current hidden 43-versus-45 gap.
- Resolve the current accessibility 14-versus-10 conflict.
- Resolve public-suite all-or-nothing versus granular scoring.
- Resolve public-test duplicate engineering credit.
- Classify every signal as quality score, eligibility guardrail, human score, efficiency metric, or winner-policy input.
- Define benchmark version, scorer version, contract digest, and compatibility policy.
- Preserve v1 evaluator behavior and report interpretation.

## Tests and evidence

Add deterministic tests proving exact arithmetic, ID uniqueness, evidence-producer mapping, missing/unknown check rejection, and v1 report compatibility. Demonstrate that mixed benchmark versions cannot be treated as directly comparable under the new contract.

## Acceptance criteria

- one accepted machine-readable contract exists;
- all point arithmetic is exact;
- no unexplained duplicate credit remains;
- v1 is immutable;
- changed semantics are assigned a new major version;
- phase-1 implementers can derive scorer behavior without guessing.

## Stop conditions

Stop if the work would overwrite historical scores, leave unallocated points, require changing old receipts, or cannot reconcile the documented matrix with an exact contract.

## 0.7.9 implementation ownership

- Read-only legacy evidence: `benchmarks/specs/priority-picker-v1/` and its installed mirror.
- Corrected source contract: expected `benchmarks/specs/priority-picker-v2/` unless the accepted phase-0 decision selects another new major ID.
- Contract validation: `src/agent_workflow/benchmarking/contracts.py` and new versioned schemas under `schemas/`.
- Compatibility/loading seams: `src/agent_workflow/benchmarking/scoring.py`, without activating corrected scoring yet.
- Decision and task authority: `docs/DECISIONS/`, `docs/BACKLOG.md`, and the benchmark correction docs.

All authority-bearing behavior remains in the built-in `agent_workflow.benchmarking` feature. Do not add a scorer/evaluator hook to the trusted plugin API or create a second registry. Pure contracts and evaluator-result interpretation should remain separable so a later, independently approved ARC-004 extraction can be evaluated without rewriting run authority.
