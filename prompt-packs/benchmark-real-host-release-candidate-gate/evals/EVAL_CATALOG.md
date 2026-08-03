# Evaluation catalog

The machine-readable authority is `evaluation-manifest.json`. The checks below are grouped by domain; all are mandatory.

## Local/package integrity — 15 points

- `LOCAL-001`: transferred source/archive identity and clean baseline.
- `LOCAL-002`: compilation and full invariants.
- `LOCAL-003`: release/distribution/documentation/installer/audit gates.
- `LOCAL-004`: installed export parity and exact 100-point golden scoring.

## Host readiness — 10 points

- `HOST-001`: Codex subscription authentication without API-key fallback.
- `HOST-002`: Claude subscription authentication without API/token fallback.
- `HOST-003`: tmux capacity, browser/runtime, and readiness.

## Codex fast — 20 points

- `CODEX-001`: exactly two same-window panes and no detached session.
- `CODEX-002`: visible changing streams and stable bindings.
- `CODEX-003`: timing and usage.
- `CODEX-004`: awaiting human review with two ready apps.

## Claude fast — 15 points

- `CLAUDE-001`: topology, visibility, and stable bindings.
- `CLAUDE-002`: timing and usage.
- `CLAUDE-003`: awaiting human review with ready apps.
- `CLAUDE-004`: truthful cohort separation.

## Full/process safety — 12 points

- `PROC-001`: three-phase stable pane reuse.
- `PROC-002`: cancellation leaves no old descendant.
- `PROC-003`: infrastructure classification and fresh retry isolation.

## Live browser/review — 15 points

- `LIVE-001`: live preservation/reachability.
- `LIVE-002`: browser, accessibility, export, and console evidence.
- `LIVE-003`: blinding and independent human review.
- `LIVE-004`: report and verification integrity.

## Lifecycle — 5 points

- `LIFE-001`: truthful idempotent stop/restart and stable mapping.
- `LIFE-002`: preservation-first and safe destructive cleanup.

## Final gate — 8 points

- `FINAL-001`: documentation/backlog/source synchronization.
- `FINAL-002`: complete hashed evidence and lineage.
- `FINAL-003`: independent acceptance.
