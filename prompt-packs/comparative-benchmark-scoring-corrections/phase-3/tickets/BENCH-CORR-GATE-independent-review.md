# BENCH-CORR-GATE — Independent benchmark acceptance

**Backlog:** `BENCH-CORR-GATE`
**Priority:** P0 / Critical
**Dependencies:** BENCH-CORR-006, BENCH-CORR-009, and BENCH-CORR-010
**Parallel lane:** independent review gate
**Baseline:** `agent-workflow` 0.7.9

## Objective

Independently verify and accept or reject the corrected benchmark before it is used for real comparative claims.

## Writable scope

Review evidence and the phase-gate report only, except narrowly scoped corrective patches explicitly authorized after findings. The reviewer must not silently repair implementation while claiming independent acceptance.

## Required review

- inspect the complete integrated diff;
- verify exact 100-point arithmetic and traceability;
- verify v1 immutability and version separation;
- rerun golden and mutation calibration;
- rerun browser/download/accessibility fixtures;
- verify human-review blinding and blocker adjudication;
- verify source/package asset equality;
- verify mixed-version rejection;
- verify eligibility invalidation and harness-failure separation;
- run the clean installed-product benchmark export/calibration journey;
- run current release/drift and prompt-pack validation;
- compare generated docs/man content with the contract.

## Tests and evidence

Record exact commands, exit status, expected and actual scores, digests, and any skipped environment-dependent checks. Failed/skipped checks remain visible.

## Acceptance criteria

The gate report explicitly accepts or rejects development, internal, and publication use separately. Acceptance requires no unexplained point drift, no historical mutation, and complete calibration evidence.

## Stop conditions

Reject the gate if any check lacks a controlled mutation, if source and package results differ, if treatment identity leaks to reviewers, if mixed versions can be compared, or if docs/man tables disagree with the contract.

## 0.7.9 implementation ownership

- Writable scope is review evidence and the phase-gate report only unless a separate corrective ticket is authorized.
- Review the built-in feature, corrected suite source, installed mirror, schemas, tests, docs/man, release audit, and prompt-pack state.
- Confirm benchmark commands work from an installed wheel without plugins and under the core-only recovery route.
- Do not implement plugin extraction or broaden the public plugin API during review.

All authority-bearing behavior remains in the built-in `agent_workflow.benchmarking` feature. Do not add a scorer/evaluator hook to the trusted plugin API or create a second registry. Pure contracts and evaluator-result interpretation should remain separable so a later, independently approved ARC-004 extraction can be evaluated without rewriting run authority.
