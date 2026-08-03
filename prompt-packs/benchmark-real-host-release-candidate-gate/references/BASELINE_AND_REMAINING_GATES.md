# Baseline and remaining gates

## Accepted local baseline

Checkpoint 10 records 291 invariant tests passing, focused lifecycle/operator passes, successful compilation, exact source/package benchmark inventory, and a golden v2 score of 100 points. The implementation trace is in `docs/BENCHMARK_ENHANCEMENTS_CHECKPOINT_10_RELEASE_CANDIDATE_REVIEW.md`.

## Remaining gates

1. Authenticated Codex subscription execution inside real tmux.
2. Authenticated Claude subscription execution inside real tmux.
3. Exactly two additional panes in the invoking window, with no detached benchmark session.
4. Visible provider output during execution, not only file logs or final output.
5. Stable arm pane IDs through a three-phase full run.
6. Real cancellation proving no provider descendant survives pane/helper termination.
7. Fast-suite model path under 180 seconds for each provider profile.
8. Two live applications preserved after automated scoring and reporting.
9. Real browser inspection and configured blinded review submission.
10. Restart/stop/cleanup safety and post-cleanup evidence verification.
11. Independent final release-candidate decision.
12. Publication runtime image/digest/font attestation only if a publication claim is requested.

## Known non-defects

- Human review occurs after automated completion and is not part of the three-minute model-path target.
- Subscription provider cost may be unavailable/not attributable; it must not be converted to zero.
- Development policy has no winner declaration with one pair.
- Fast and full suite results are not directly pooled.
- Preserving live applications and worktrees is the default cleanup behavior.
