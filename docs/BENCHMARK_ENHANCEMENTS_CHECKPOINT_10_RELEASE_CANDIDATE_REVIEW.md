# Benchmark Enhancements Checkpoint 10 — Release-Candidate Review

Date: 2026-08-02  
Scope: comparative benchmark execution, tmux operator surface, live-review lifecycle, compact suite, scoring/review handoff, cleanup, resume, and distribution consistency.

## Executive conclusion

The benchmark subsystem now satisfies the three requested operator expectations in implementation:

1. a run creates exactly two additional panes in the invoking tmux window;
2. provider stdout and stderr remain visible while bounded durable copies are recorded;
3. live applications are started from the selected arm worktrees and preserved through browser capture, machine scoring, report generation, and blinded human review.

The compact `priority-picker-fast-v1` suite keeps the corrected paired methodology and 100-point scoring contract while limiting model execution to one 150-second phase. Deterministic paired calibration completes within the three-minute wall budget. Real Codex/Claude subscription timing remains an external installed-host gate rather than a locally proven claim.

Checkpoint 10 also closes lifecycle defects found during the release-candidate audit. These were not cosmetic: they affected truthful status, orphan prevention, and destructive-cleanup safety.

## Requirement trace

| Expectation | Implementation | Evidence | Result |
|---|---|---|---|
| Two new panes in launching window | `operator_panes.ensure_operator_panes` resolves the current window, preflights capacity, then creates two bound panes | operator invariants and readiness capacity tests | Implemented; installed tmux observation pending |
| Interactive visible runs | `tmux_runner.py` mirrors both provider streams to the foreground pane while retaining bounded logs | stream/result test and pane respawn contract | Implemented |
| Stable panes throughout run | arm pane IDs are reused across phases, retries, and final live-review display | pane binding/state files and operator invariants | Implemented |
| Live apps preserved | `start_live_review` launches one server per selected pair/arm and the automated pipeline does not stop them | lifecycle status/start/stop tests and preservation-first cleanup | Implemented |
| Human assessment support | assignments expose blinded left/right URLs and refresh URLs without changing the private mapping | review contracts | Implemented |
| Compact under-three-minute task | one model phase with a 150-second cap; paired synthetic calibration enforces `<180s` | fast-suite calibration test | Locally validated; real provider timing pending |
| Corrected scoring | explicit v2 per-check contract totals exactly 100 points | golden reference scorer reconciliation | Implemented |

## Deep findings and corrections

### RC-01 — Downstream failures were not durable in run state

Previously, execution failures were recorded by `execute_run`, but failures during live startup, browser capture, scoring, or consolidation could leave `run.json` at `executed`. That made `status` materially misleading and weakened resume diagnosis.

Checkpoint 10 records:

- `state: failed`;
- `failed_stage`;
- the stage wall time;
- the bounded error string;
- `updated_at`.

The exception is still re-raised. No failed stage is converted into apparent completion.

### RC-02 — Missing pane-result evidence could leave an overlapping provider

The coordinator waits for an atomic result file from the foreground pane helper. If that file never appeared, the arm was classified from a synthetic timeout record, but the helper/provider might still have been running until a later respawn.

Checkpoint 10 immediately respawns the owned arm pane with a terminal evidence-failure banner. `respawn-pane -k` terminates the helper, whose signal forwarding terminates the provider process group. The result is classified as infrastructure failure, allowing only the preplanned fresh paired retry.

### RC-03 — Destructive cleanup could proceed after failed server teardown

`stop_live_review` formerly returned stopped counts but not a remaining-process count. `cleanup_benchmark` checked a field not present in that response, so worktree removal could proceed even when a process resisted termination.

Checkpoint 10 adds explicit `failed` and `remaining` counts. Worktree removal now refuses whenever any live process remains. The benchmark panes are also preserved when teardown is incomplete so logs and URLs remain available for diagnosis.

### RC-04 — Explicit teardown left benchmark panes behind

Preservation is the correct default, but explicit teardown should release the operator surface. Checkpoint 10 closes only panes that are still bound to the same run and arm. A pane that has been rebound is never killed. Pane closure occurs only after all live servers are confirmed stopped.

### RC-05 — Permission-denied PID checks were unsafe

A permission error from `kill(pid, 0)` means the process exists but cannot be signaled by the current principal. It was previously treated as dead. Checkpoint 10 treats it as alive, preventing false teardown success and unsafe worktree removal.

### RC-06 — Fully stopped runtimes were reported as degraded

Live-review status now distinguishes:

- `not_started`;
- `ready`;
- `degraded`;
- `failed`;
- `stopped`.

This makes status and automation decisions correspond to the actual lifecycle.

### RC-07 — Duplicate metrics write

The arm finalizer wrote the same `metrics.json` twice. The duplicate write was removed. This had no schema effect but obscured the evidence path and created unnecessary I/O.

## Compact benchmark assessment

The fast suite is compact in execution shape, not in evaluator rigor. It still measures:

- frozen formula behavior and deterministic ranking;
- search, filtering, sorting, and export;
- malformed input, duplicate IDs, range/type validation, and scale behavior;
- public regressions;
- accessibility and UI evidence from the running application;
- scope completeness and engineering quality;
- paired timing, usage, guardrails, blinded review, and winner policy.

The task combines build and verification into one prompt and removes multi-phase coordination overhead. The 150-second limit applies to model execution, not browser capture, scoring, consolidation, or human review. Cohorts from the fast and full suites must remain separate because task identity and timing differ.

## Architecture review

The current separation is appropriate:

- `operator_panes.py` owns pane allocation, binding, reuse, and teardown;
- `tmux_runner.py` owns foreground execution, stream mirroring, signal forwarding, and atomic process results;
- `runner.py` owns paired phase orchestration and durable arm/pair evidence;
- `live_review.py` owns preserved application lifecycle and runtime-only records;
- `visual.py`, `scoring.py`, `review.py`, and `reporting.py` remain separate evaluation stages;
- `service.py` composes stages and now records stage-specific failure state.

No new plugin registry or generic abstraction is justified. The benchmark-specific surface is cohesive and uses the repository’s existing tmux, process, Git, schema, hash, and atomic-write ports.

## Validation

Checkpoint 10 local validation:

- 289 invariant tests passed;
- 24 initial lifecycle/operator/CLI/contract tests passed;
- 23 teardown-safety and operator tests passed after the second hardening pass;
- fast paired synthetic calibration remains under the configured phase and pair budgets;
- the golden reference solution still reconciles to exactly 100 points;
- package/source suite inventory remains exact.

## Remaining external gates

These cannot be honestly completed in this container:

1. run authenticated Codex and Claude subscription executors inside an installed tmux environment;
2. observe that exactly two panes are added to the invoking window and remain visible through model completion;
3. verify real provider progress streaming and cancellation behavior;
4. confirm the compact task completes under three minutes with each target model/profile;
5. inspect preserved applications in a real browser and submit independent blinded reviews;
6. execute publication-level browser/runtime attestation and independent release review.

These are evidence gates, not known implementation omissions.

## Release recommendation

The subsystem is suitable for an installed release-candidate trial. Merge should remain conditional on the real-host operator and provider gates above. No further local architectural rewrite is recommended before those trials; the next useful information must come from actual tmux, provider, browser, and human-review behavior.
