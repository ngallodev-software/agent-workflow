# Phase 2 master implementation prompt

## Role

Coordinate reviewer-integrity, scorer-calibration, and single-source-of-truth work.

## Rules

- Do not calibrate against live provider output.
- Treat golden and mutation fixtures as benchmark-owned test assets, not agent-visible task inputs.
- Preserve reviewer blinding and immutable submissions.
- Generate or validate derivative docs from the accepted contract.
- Require installed-package parity before phase acceptance.

## Completion

Produce exact calibration tables, blind-leak evidence, package/source digests, and an independent phase gate.

## 0.7.8 boundary

Use `review.py`, `reporting.py`, the corrected suite assets, packaged mirror, and `scripts/audit-release-assets.py`. Prove the benchmark remains usable without enabled plugins and that source/exported suite bytes agree.
