# ChatGPT handoff — MCP mutation phase

Treat current source, `BACKLOG.md`, the determinism/security assessment, hardening plan, and consolidated public documentation as authoritative.

0. Stop unless `HARD-004`, `HARD-005`, and `HARD-007` are accepted and integrated. Run `python3 scripts/audit-release-assets.py` to verify pack ownership and drift.
1. Read `docs/ARCHITECTURE.md`, `docs/MCP_SERVER.md`, `docs/OPERATIONS.md`, `docs/TESTING.md`, the current CLI/service/MCP code, and this pack.
2. Execute `MCP3-00` to map every proposed tool to one transport-neutral service shared with the CLI and authenticated-principal policy. Reject any tool that requires direct state mutation or duplicate scheduling/routing logic.
3. Execute `MCP3-01` for the smallest safe local-stdio mutation surface, preserving configured roots, typed arguments, durable idempotency, stable errors, policy enforcement, immutable evidence, and principal authorization.
4. Execute `MCP3-02` as an independent review using both `phase-gate-review` and `release-drift-auditor`. Extend installed-product MCP journeys first; add invariant matrices only for general security, replay, identity, or idempotency boundaries.

Do not add HTTP/SSE, OAuth deployment, arbitrary shell/file access, direct tmux controls, raw terminal output, environment dumps, force kill, destructive tools, or MCP-local lifecycle authority.
