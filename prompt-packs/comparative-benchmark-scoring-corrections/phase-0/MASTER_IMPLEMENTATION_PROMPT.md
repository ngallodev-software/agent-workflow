# Phase 0 master implementation prompt

## Role

Act as the benchmark contract coordinator. Execute or delegate only the tickets in the phase manifest.

## Objective

Produce one accepted, machine-readable, internally consistent contract for the corrected benchmark version and one explicit efficiency/winner policy decision.

## Rules

1. Confirm the exact 0.7.8 ownership map and source/mirror parity before edits.
2. Preserve v1 behavior and receipts.
3. Do not implement scorer changes in this phase.
4. Reconcile every point to an exact dimension and check.
5. Record unresolved alternatives rather than silently choosing contradictory semantics.
6. Require independent review before phase completion.

## Test policy

Add contract validators and compatibility tests only as required to prove arithmetic, identity, version boundaries, and v1 preservation.

## Completion

Produce ticket completion reports and an independent phase-gate report that either accepts the contract or blocks phase 1.

## 0.7.8 boundary

Use the dedicated benchmark CLI handler, built-in `agent_workflow.benchmarking` owners, source suite, installed asset mirror, and versioned schemas listed in the ownership map. Resolve the current spec `1.1.0` versus matrix `1.0.0` contradiction. Do not change v1 behavior or add plugin hooks.
