# Repository agent guidance

Use this file as the repository-level steering index.

Always read `docs/BACKLOG.md` before changing scope or task status. Treat it as the only unfinished-work register.

For delegated implementation, phase gates, or lifecycle control, read `docs/references/DELEGATION_RUNBOOK.md` and `docs/references/EXECUTION_PROTOCOL.md` only when that workflow is in scope. Use the `agent-workflow-orchestrator`, `phase-gate-review`, and `release-drift-auditor` skills as applicable.

For output standards, read the relevant template under `templates/` or the active prompt pack's `templates/` directory. Do not treat steering references as universal instructions.

Use codebase-memory-mcp first for structural code discovery. Use RTK-wrapped commands for shell inspection and preserve isolated worktrees for delegated changes.

For every new agent worktree, read [`docs/references/WORKTREE_PREFLIGHT.md`](docs/references/WORKTREE_PREFLIGHT.md) and perform the full-index preflight before structural discovery or code edits. Index the exact worktree, never the main checkout or another worktree, and record readiness/counts in the handoff. This is an optional operator-tool procedure: do not make the package or runtime depend on the MCP service.
