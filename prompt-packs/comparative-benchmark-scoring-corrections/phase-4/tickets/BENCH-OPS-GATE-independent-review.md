# BENCH-OPS-GATE — Independent operator-experience acceptance

**Task type:** review-only gate  
**Dependencies:** BENCH-OPS-001, BENCH-OPS-002, BENCH-OPS-003  
**Baseline:** `agent-workflow` 0.7.9

## Writable scope

Review evidence and the phase-gate report only. Do not modify implementation, tests, suite assets, or acceptance criteria in this worktree.

## Review scope

Independently inspect the integrated diff and exercise the installed product from inside tmux. Do not implement repairs in this worktree.

## Test procedure

Install from the candidate artifact outside the checkout, enter a real tmux session, run the smallest synthetic/visual journey, inspect process and pane identities, exercise blinded review and cleanup, then rerun focused invariants and the release audit.

## Required acceptance evidence

- pane count before/after launch proves exactly two additional panes in the invoking window;
- both arm outputs are visibly updating and the same pane IDs survive phase transitions;
- interrupting/replacing a pane leaves no provider child process;
- both live applications remain reachable after automated scoring reaches `awaiting_human_review`;
- status and blinded review assignments expose working URLs without arm names;
- default cleanup preserves apps/worktrees and explicit stop/removal is idempotent;
- the fast suite exports from an installed wheel, validates, has one phase below 180 seconds, and calibrates to exactly 100;
- source/package parity and release audit pass;
- historical v1 behavior and receipts remain valid.

Reject static-only proof for tmux topology or live-app survival. Record separate development, internal, and publication recommendations and any external evidence still required.
