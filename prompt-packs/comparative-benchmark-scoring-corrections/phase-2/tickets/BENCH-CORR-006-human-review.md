# BENCH-CORR-006 — Harden blinded human review

**Backlog:** `BENCH-CORR-006`
**Priority:** P1 / High
**Dependencies:** BENCH-CORR-001
**Parallel lane:** human review lane
**Baseline:** `agent-workflow` 0.7.9

## Objective

Make human visual scoring reliable enough for internal and publication cohorts while preserving treatment blinding and immutable evidence.

## Writable functional scope

The human review assignment/submission/aggregation surfaces, visual rubric and calibration examples, reviewer evidence schemas, focused tests, and reviewer documentation. Do not alter machine quality points.

## Required behavior

- Audit reviewer bundles for treatment identity leaks in paths, metadata, HTML, screenshots, and filenames.
- Add rating-anchor examples for all visual dimensions.
- Define blocking-defect criteria and disagreement adjudication.
- Record/report inter-rater agreement for multi-reviewer cohorts.
- Handle missing, malformed, duplicate, late, or withdrawn reviews deterministically.
- Keep preference/confidence descriptive unless the accepted contract says otherwise.
- Keep human active-review time separate from agent execution timing.

## Tests and evidence

Add blind-leak, multi-reviewer aggregation, conflicting-blocker, invalid-review, immutability, and authenticated-identity tests appropriate to each claim level.

## Acceptance criteria

Reviewer identity and treatment mapping remain protected, aggregation is deterministic, and a blocking defect has one documented adjudication path.

## Stop conditions

Stop if treatment identity must be exposed to score, if reviewer edits overwrite prior submissions, or if disagreement can silently erase a blocking defect.

## 0.7.9 implementation ownership

- Review assignment/submission/aggregation: `src/agent_workflow/benchmarking/review.py`.
- Report rendering and review-completeness state: `reporting.py`.
- Corrected rubric and anchor assets: `benchmarks/specs/priority-picker-v2/visual-rubric.json` plus benchmark-owned review examples.
- Review schema: new version under `schemas/`; preserve `benchmark-human-review-v1.schema.json`.
- Tests: focused review/blinding invariants and the installed comparative-benchmark journey.

All authority-bearing behavior remains in the built-in `agent_workflow.benchmarking` feature. Do not add a scorer/evaluator hook to the trusted plugin API or create a second registry. Pure contracts and evaluator-result interpretation should remain separable so a later, independently approved ARC-004 extraction can be evaluated without rewriting run authority.
