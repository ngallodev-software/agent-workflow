# Roadmap

The 0.1 line is intentionally terminal-first and local-only. Future work should be driven by observed operator friction rather than speculative automation.

## Candidate 0.2 work

- Pack-level run ledger that maps phase and ticket dependencies to sessions.
- Explicit `reviewed`, `accepted`, and `rejected` lifecycle commands.
- Completion-report metadata validation.
- Optional heartbeat written by the runner in addition to log-growth observation.
- Safe worktree cleanup command with evidence-preservation checks.
- Exportable run summaries for handoff to another reviewer.

## Deferred until justified

- Multiple terminal backends.
- Remote execution.
- GitHub issue or pull-request synchronization.
- Automatic model selection.
- Automatic merging or branch deletion.
- Automatic termination of suspected stalled processes.
- Daemon, database service, or web UI.

Any new feature should preserve the current principles: bounded tickets, isolated worktrees, foregroundable sessions, immutable delegated instructions, durable evidence, narrow tests, and independent review.
