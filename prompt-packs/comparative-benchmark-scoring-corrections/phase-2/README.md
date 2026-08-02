# Phase 2 — review reliability, calibration, and drift prevention

## Objective

Harden blinded human review, prove scorer behavior with golden and mutated fixtures, and establish one authoritative scoring source for code, package assets, docs, and man pages.

## Parallelism

BENCH-CORR-006 and BENCH-CORR-008 may begin after phase 0/1 prerequisites. BENCH-CORR-007 integrates the completed scorer/evaluator work and is the phase's critical acceptance artifact.

## Exit gate

- blinding and reviewer aggregation are verified;
- every weighted check has a controlled calibration mutation;
- source and installed/exported suites score identically;
- documentation/man tables cannot drift silently from the contract.
