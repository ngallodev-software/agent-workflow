# BRH-002 — Host, authentication, and visual runtime readiness

**Task type:** review/evidence

From inside a real tmux pane, verify tmux, Git, Python 3.11+, Codex CLI, Claude CLI, Playwright, Chromium, and required OS process tools. Capture the invoking session/window/pane and capacity.

Prove Codex and Claude subscription sessions independently with API credential variables absent. Run `benchmark auth-check` and `benchmark readiness` for both fast-suite subscription executors. Record browser/runtime-lock attestation for the development claim.

Reject fallback authentication, missing tmux context, fewer than two available arm panes, mutable/unresolved required runtime identity, or a provider status command that cannot authenticate.

## Writable scope

Raw evidence, task result, and review reports only. Implementation changes are allowed only in a separate repair worktree after preserving a failed gate; gate tickets are review-only.

## Tests and commands

Use the exact commands and monitoring utilities named by the pack-level command matrix and this ticket. Record exit codes and raw output.

## Acceptance criteria

Every behavior named above is supported by referenced raw evidence and the structured task result validates. Missing or contradictory evidence is not accepted.

## Stop conditions

Stop and report `blocked` when a required external prerequisite is unavailable. Stop and report `rejected` when a valid execution violates a mandatory behavior. Never weaken the criterion or edit generated evidence.
