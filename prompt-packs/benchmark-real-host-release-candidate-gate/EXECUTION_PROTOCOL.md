# Execution protocol

## 1. Evidence before interpretation

Record raw state before drawing conclusions. Every pass references a regular file inside the evidence root. Screenshots alone are insufficient where machine-readable state exists; JSON alone is insufficient for direct operator-visibility claims.

Evidence must include UTC timestamps, host identity stripped of secrets, command/exit status, installed package identity, source/archive digest, provider/executor identity, run ID, and relative evidence paths.

## 2. Separate claims and cohorts

Never combine:

- Codex and Claude runs;
- subscription and API-key runs;
- fast and full suites;
- development, internal, and publication policies;
- synthetic calibration and real-provider timing;
- machine score, human score, eligibility, efficiency, and publication readiness.

## 3. Subscription authentication

For subscription-profile runs, unset API credential variables before auth/readiness and record a redacted environment allowlist result. If auth fails, stop. Do not fall back to API keys or a different provider profile.

## 4. Tmux topology

The invoking window is the authority. Capture its window ID and pane IDs before launch. A valid launch adds exactly two panes to that window and no benchmark-specific session. The caller pane remains focused. The two arm panes must retain their IDs and run/arm bindings through phases, retries, and final live-review display.

## 5. Interactive visibility

Start pane monitoring before `benchmark run`. A valid result includes at least two distinct timestamped content hashes for each arm while its model process is active, plus an operator attestation that progress/output was visible without reading log files. Final-only output does not satisfy this gate.

## 6. Timing

For `priority-picker-fast-v1`:

- each arm model phase must be less than or equal to its sealed 150-second timeout;
- the paired model-execution critical path must be less than 180 seconds;
- browser capture, scoring, reporting, and human review are separately timed and do not excuse a model-path violation.

Use sealed run metrics, not shell perception, as the timing authority.

## 7. Process cancellation

Capture the pane helper PID, process group, and descendants before intervention. Terminate through the owned pane/helper boundary. All captured descendant PIDs must disappear. A new retry process does not prove the old process exited; compare exact PIDs and process-group IDs.

## 8. Live-review preservation

Automated completion must leave both applications ready. Verify HTTP readiness after report generation and after at least 60 seconds of idle time. Static snapshots do not satisfy live preservation. Runtime URLs may be refreshed after restart, but private left/right mapping must remain unchanged.

## 9. Human review and blinding

Review assignments and templates exposed to reviewers must not contain `control_raw`, `workflow_full`, treatment profile IDs, or private mapping paths. The independent gate reviewer must not use the private mapping while scoring. Mapping inspection is permitted only after review submission for integrity verification.

## 10. Cleanup safety

Default cleanup preserves apps/worktrees. Destructive cleanup is permitted only after verified evidence and successful live process teardown. If any PID remains or signaling is denied, worktrees and panes must remain. Only panes still bound to the same run and arm may be closed.

## 11. Defect handling

Preserve failed evidence, then classify. Do not edit acceptance thresholds. Repairs require focused regression tests and rerun evidence from a fresh run ID. The final report links both failure and repair evidence.

## 12. Completion

Acceptance requires every mandatory evaluation check to pass, 100/100, and an independent `accept` decision. `blocked` is correct when an external prerequisite is missing. `rejected` is correct when a required behavior fails after valid execution.
