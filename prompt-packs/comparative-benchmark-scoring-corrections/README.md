# Comparative benchmark scoring corrections

## Purpose

Correct the `priority-picker-v1` scoring and evaluation contract without rewriting historical evidence. The work freezes an exact per-check contract, creates a new major benchmark version for changed semantics, expands machine and browser evaluation, calibrates scoring with golden and mutated fixtures, hardens human review, prevents source/package/documentation drift, and rejects mixed-version comparisons.

This pack is rebased to `agent-workflow` 0.7.8 and its current built-in feature/plugin architecture.

## 0.7.8 architecture boundary

The benchmark is a built-in feature under DEC-009:

- CLI grammar: `src/agent_workflow/cli_parser.py`;
- command dispatch: `src/agent_workflow/cli_handlers/benchmark.py`;
- feature implementation: `src/agent_workflow/benchmarking/`;
- source suite: `benchmarks/specs/priority-picker-v1/`;
- installed/exported mirror: `src/agent_workflow/assets/benchmarks/priority-picker-v1/`;
- schemas: `schemas/benchmark-*.schema.json`;
- acceptance/invariants: the comparative-benchmark tests under `tests/acceptance/` and `tests/invariants/`;
- release drift: `scripts/audit-release-assets.py`.

The trusted plugin host in 0.7.8 supports explicitly enabled top-level plugin commands and digest-bound schema/asset resources. It does not expose scorer/evaluator hooks. Do not create a benchmark-specific plugin registry, modify the public plugin API merely to complete this work, or extract the benchmark distribution during this pack. Keep authority-bearing execution, evidence, review, and comparison inside the built-in feature while making pure corrected contracts/evaluator interpretation separable for a later evidence-gated ARC-004 extraction.

## Source-of-truth hierarchy

1. Existing sealed v1 receipts and their recorded identities.
2. Current v1 evaluator behavior in `benchmarks/specs/priority-picker-v1/evaluation/`.
3. Current built-in scoring/reporting services in `src/agent_workflow/benchmarking/`.
4. Installed-product behavior from `benchmark suite-export` and the packaged mirror.
5. Versioned JSON Schemas and release-drift validation.
6. Documentation, the requirement matrix, and historical implementation notes.

The v1 evaluator is authoritative for old reports. It is not permission to preserve the mismatch in the corrected version.

## Confirmed baseline drift

- `benchmark-spec.json` declares `1.1.0`, while the matrix says `1.0.0`.
- Named hidden points total 43, not 45.
- Named accessibility points total 14, not 10.
- The implementation equal-shares checks within dimensions.
- The public suite is one 15-point all-or-nothing check.
- Public-test success is counted again in engineering quality.
- Browser checks prove only a subset of the named interaction/accessibility contract.
- Source and installed benchmark copies can drift unless the release audit detects it.

## Phase map

| Phase | Objective | Tickets | Parallelism |
|---|---|---|---|
| 0 | Freeze the corrected contract and efficiency policy | BENCH-CORR-001, BENCH-CORR-010 | Parallel analysis; one accepted contract/policy gate |
| 1 | Implement weighted and expanded machine/browser evaluation | BENCH-CORR-002 through BENCH-CORR-005 | 003/004/005 may run in parallel after 002 |
| 2 | Harden review, calibration, and drift prevention | BENCH-CORR-006 through BENCH-CORR-008 | Parallel where dependencies permit |
| 3 | Preserve comparability and independently accept the new version | BENCH-CORR-009, BENCH-CORR-GATE | Sequential |

## Non-targets

- Do not modify the semantics of the existing v1 suite or old receipts.
- Do not run or publish a real-provider cohort as part of scorer correction.
- Do not merge efficiency into quality points without the phase-0 policy decision.
- Do not redesign subscription/API authentication, worktree orchestration, or publication runtime trust.
- Do not add a framework, database, network service, plugin hook system, or unrelated UI.
- Do not weaken eligibility guardrails to make calibration pass.
- Do not extract the benchmark into a separate distribution during this pack.

## Required references

- `references/CURRENT_BEHAVIOR_AND_GAPS.md`
- `references/LOCATION_DISCOVERY_AND_MAPPING.md`
- `docs/COMPARATIVE_BENCHMARK_EXPLAINED.md`
- `docs/COMPARATIVE_BENCHMARK_CORRECTION_BACKLOG.md`
- `docs/FEATURE_MODULE_ARCHITECTURE.md`
- `docs/PLUGIN_API.md`
- `docs/DECISIONS/DEC-008-INITIAL-COMPARATIVE-BENCHMARK.md`
- `docs/DECISIONS/DEC-009-FEATURE-MODULE-BOUNDARIES.md`

## Execution

Follow `EXECUTION_PROTOCOL.md`, `DELEGATION_RUNBOOK.md`, phase manifests, and ticket prompts. Every implementation ticket uses an isolated worktree. A phase reviewer must be independent from the implementers whose work is accepted. Run `agent-workflow pack validate`, focused benchmark tests, installed-suite export/calibration, and `python3 scripts/audit-release-assets.py` before every integration gate.
