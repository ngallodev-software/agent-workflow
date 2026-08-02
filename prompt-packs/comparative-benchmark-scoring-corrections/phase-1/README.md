# Phase 1 — corrected machine and browser evaluation

## Objective

Implement explicit weighted scoring, then expand functional, browser, and public-regression evaluation under the accepted new benchmark version.

## Ordering

BENCH-CORR-002 lands first. BENCH-CORR-003, BENCH-CORR-004, and BENCH-CORR-005 may then execute in parallel in separate worktrees.

## Exit gate

- explicit weights, no equal-share fallback for the corrected version;
- complete functional and validation traceability;
- deterministic browser interaction and export evidence;
- public scoring semantics match the contract;
- v1 behavior remains unchanged.
