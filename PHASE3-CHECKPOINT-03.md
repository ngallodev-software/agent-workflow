# Phase 3 Checkpoint 03 — Deterministic primary-skill behavior evals

This cumulative overlay includes Phase 3 Checkpoints 01 and 02 plus the next implementation slice.

## Added in this slice

- Added a compact deterministic behavioral scenario corpus for the primary Agent-Workflow skill covering all eight Phase 3 decision/correctness requirements:
  - correct non-use;
  - headless versus external worker ownership;
  - no terminal-manager lifecycle behavior;
  - persist-before-deliver;
  - delivery is not acknowledgement;
  - worker exit is not completion/evaluation/review/acceptance;
  - external-mode source/worktree and Agent Run provenance preservation;
  - sealed-evidence recovery rather than mutation/improvisation.
- Added a small product-side validator for that corpus. It deliberately checks the primary skill contract rather than introducing an LLM judge, duplicate runtime schema, or new lifecycle authority.
- Wired the behavioral contract into the existing release asset audit alongside Checkpoint 02's live-parser skill-example validation.
- Documented the primary-skill behavioral corpus in `evals/README.md`.

## Phase 3 implementation state

The implementation work described by Phase 3 of `docs/SKILL_FIRST_SIMPLIFICATION_PLAN.md` is now represented in the cumulative overlay: primary skill hardening, specialized-skill composition/deduplication, parser-backed executable examples, and deterministic behavioral skill evals. Final Phase 3 test/release verification remains intentionally separate under the project checkpoint policy.

## Verification policy

No test suite or release-validation command was run for this checkpoint.
