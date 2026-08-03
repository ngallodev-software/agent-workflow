# BENCH-OPS-002 — Preserve live applications for human review

**Backlog:** `BENCH-OPS-002`  
**Priority:** P0 / Critical  
**Dependencies:** BENCH-OPS-001, BENCH-CORR-004, BENCH-CORR-006  
**Baseline:** `agent-workflow` 0.7.9

## Objective

After automated execution, start and preserve a real application server for every selected pair/arm worktree so humans can assess the actual result before scoring and cleanup.

## Writable scope

`src/agent_workflow/benchmarking/live_review.py`, `live_review_pane.py`, `review.py`, lifecycle service/CLI surfaces, review/run schemas, focused tests, and directly related docs.

## Required behavior

- Launch one independently addressable server per selected pair/arm outside sealed evidence storage.
- Wait for a declared readiness URL and record PID, process group, URL, worktree, logs, and lifecycle timestamps.
- Start live servers before browser capture so automated visual evidence and humans inspect the same running application state.
- Keep servers alive after machine scoring, consolidation, reporting, and `awaiting_human_review` transition.
- Reuse the two operator panes to display current URLs and stream server logs after model execution.
- Expose lifecycle state and URLs through `benchmark status`; provide explicit idempotent `live-start` and `live-stop` commands.
- Include URLs in blinded assignments by left/right label only and refresh stale URLs without changing the private label mapping.
- Preserve servers and arm worktrees by default. Require explicit stop before destructive worktree cleanup and retain coordinator evidence.
- Persist partial startup state and useful failure details if one server cannot start.

## Acceptance criteria

Both selected arm applications remain reachable after automated scoring, current blinded assignments contain working left/right URLs, default cleanup preserves the servers and worktrees, and explicit stop/removal is safe and idempotent.

## Tests and evidence

Cover ready/degraded/stopped state, safe process-group termination, restart behavior, URL refresh, treatment blinding, default preservation, destructive-cleanup refusal, and installed live-server access. Verify live runtime files are excluded from immutable benchmark evidence and manifests except for appropriate lifecycle references.

## Non-targets

Do not embed a general web hosting platform, make live server availability a substitute for sealed screenshots, expose treatment labels to reviewers, or delete source worktrees automatically after scoring.

## Stop conditions

Stop if live review requires treatment disclosure, runtime files enter sealed score evidence, worktree deletion can occur while an app is ready, or failed startup is silently replaced with static evidence.
