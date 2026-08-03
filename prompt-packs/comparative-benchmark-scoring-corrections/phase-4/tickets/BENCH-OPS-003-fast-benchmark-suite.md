# BENCH-OPS-003 — Add a sub-three-minute compact benchmark

**Backlog:** `BENCH-OPS-003`  
**Priority:** P1 / High  
**Dependencies:** BENCH-CORR-002 through BENCH-CORR-005 and BENCH-OPS-002  
**Baseline:** `agent-workflow` 0.7.9

## Objective

Add a second built-in benchmark that retains the corrected comparative contract but sharply reduces model work so one arm's model-execution critical path is bounded below three minutes.

## Writable scope

A new sibling suite under `benchmarks/specs/`, its exact packaged mirror, versioned schemas/contracts where required, suite export, release parity checks, focused tests, and suite-specific documentation. Do not alter historical v1 task semantics.

## Required behavior

- Use a distinct benchmark ID and version; never reinterpret or alias the full suite.
- Retain identical paired task identity, isolated worktrees, randomized arm slots, bounded start skew, sealed executor/policy/runtime identities, corrected 100-point machine scoring, browser capture, live review, blinded human assessment, and 70/30 composite behavior.
- Use one model phase with `timeout_seconds < 180`; prefer a 150-second ceiling or lower.
- Begin from a mostly complete dependency-free application with a small, explicit defect set spanning functional correctness, validation, browser accessibility, and documentation.
- Keep enough independent checks to detect treatment effects; do not turn the suite into a single public-test smoke check.
- Supply subscription-first Codex/Claude executors plus optional explicit API and synthetic acceptance profiles.
- Include a fast-suite explanation, requirement/evaluation matrix, exact scoring contract, deterministic fixture, visual runtime, and byte-identical packaged mirror.
- Calibrate a golden result at exactly 100/100 and controlled defects at their exact expected deltas.

## Acceptance criteria

The spec contains exactly one model phase below 180 seconds. The evaluator rejects missing/duplicate/unknown/over-awarded evidence, the golden solution earns exactly 100, and installed `suite-export` bytes match the source suite. A real subscription-backed trial is still required before making runtime-performance claims beyond the hard timeout contract.

## Non-targets

Do not reduce human-review requirements, remove visual evidence, award points merely for process completion, combine incompatible full/fast cohorts, or claim that post-model browser/scoring/review time is part of the model's sub-three-minute bound.

## Stop conditions

Stop if the model phase timeout is 180 seconds or greater, the suite omits any paired/scoring/browser/blinded-review lifecycle, source and package bytes diverge, or the golden score cannot reconcile to exactly 100.
