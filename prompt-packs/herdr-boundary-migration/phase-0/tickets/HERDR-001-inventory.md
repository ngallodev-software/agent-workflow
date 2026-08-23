# HERDR-001 — inventory and seam contract

Read `docs/HERDR_BOUNDARY_MIGRATION_PLAN.md`, `docs/BACKLOG.md`, and the
delegation/execution protocols. Use codebase-memory first against the indexed
`lump-apps-agent-workflow` and `lump-apps-herdr` projects; use bounded RTK
search for literals, manifests, schemas, and docs.

Produce a committed, schema-valid inventory artifact and completion report
covering: tmux/pane symbols and callers; session/lifecycle coupling; public
CLI/MCP surfaces; tests and release assets; Herdr plugin APIs; proposed
terminal-neutral adapter; and exact writable/non-writable paths for later
phases. Record both repositories' baseline identity and dirty state.

This is read-only with respect to source and must not index a different
worktree. Stop if current uncommitted edits overlap the proposed target paths.
