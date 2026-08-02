# Phase 3 master implementation prompt

## Role

Coordinate version migration and independent acceptance.

## Rules

- Preserve original v1 evidence.
- Reject mixed-version winner calculations by default.
- Treat rescoring as additive evidence only.
- Require clean installed-product calibration and release/drift validation.
- The gate reviewer must not be the sole implementer of the accepted work.

## Completion

Produce migration documentation, compatibility tests, and an independent acceptance report.

## 0.7.8 boundary

Enforce version compatibility in the built-in contracts/scoring/reporting/statistics path. The independent gate must exercise the installed 0.7.8 command surface, `--no-plugins` recovery, suite export, calibration, review, reporting, and release drift.
