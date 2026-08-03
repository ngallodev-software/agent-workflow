# Operator experience and compact-suite correction addendum

## Confirmed 0.7.9 baseline gaps

The pre-correction benchmark path created detached tmux sessions for each arm, captured provider output to files, produced browser evidence from a short-lived/offline path, and closed the browser/server lifecycle before human assessment. That behavior conflicted with the intended operator workflow even when the score pipeline itself completed.

## Adopted contract

1. The invoking tmux window is the operator workspace.
2. A benchmark owns exactly two additional stable panes, one for each arm.
3. Those panes show provider output during model work and live-server URLs/logs after automated evaluation.
4. Live applications are review conveniences outside sealed evidence, but browser screenshots and score receipts remain immutable evidence.
5. Human review must be able to inspect both current applications through blinded labels.
6. Cleanup is preservation-first; destruction requires explicit server stop and worktree removal.
7. A fast suite reduces task scope and model phases, not experimental validity or scoring rigor.

## Fast-suite timing definition

“Under three minutes” applies to the model-execution critical path for one arm. The benchmark spec enforces this with one phase whose hard timeout is less than 180 seconds. Environment preflight, paired startup skew, browser capture, deterministic scoring, report generation, and human review are separately measured and must not be hidden inside that claim.

## Architectural owners

- pane creation/binding and provider streaming: `src/agent_workflow/benchmarking/operator_panes.py`, `runner.py`, and `tmux_runner.py`;
- live server lifecycle: `live_review.py` and `live_review_pane.py`;
- lifecycle CLI: benchmark parser/handler/service;
- blinded URLs: `review.py` and review schema;
- full corrected suite: `benchmarks/specs/priority-picker-v2/`;
- compact suite: `benchmarks/specs/priority-picker-fast-v1/`;
- packaged mirrors: `src/agent_workflow/assets/benchmarks/`;
- parity/release enforcement: `scripts/audit-release-assets.py`;
- focused acceptance: benchmark invariant and installed-product tests.
