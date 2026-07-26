# Phase 4 — security and acceptance master implementation prompt

Read current source, `BACKLOG.md`, `docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md`, this phase README, every ticket, the collision matrix, and all prior accepted gates before editing.

Coordinate only these tickets: `MSG-006`, `MSG-007`. Respect manifest dependencies and ticket-specific `HARD-*` prerequisites. Dependency-free tickets may run concurrently in isolated worktrees. Inspect and integrate the smallest compatible diffs rather than replacing shared files wholesale.

Keep durable journals authoritative, treat wakeups as hints, and require fixed opaque orchestrator notifications. Require installed-product acceptance evidence first and retain only compact security/replay matrices. Run `release-drift-auditor` after integration. Stop on ownership collision, unresolved prerequisite, cursor advancement before durable commit, unsafe child-text injection, or a second scheduler/state machine.
