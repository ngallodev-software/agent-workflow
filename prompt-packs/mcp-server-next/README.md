# mcp-server-next

## Purpose

Implement only the next authorized MCP mutation phase for canonical backlog item [`MCP-003`](../../docs/BACKLOG.md). The read-only local stdio adapter and shared read services already exist. This pack adds no new orchestrator and must wrap the same application services used by the CLI.

## Hard prerequisites

Do not execute this pack until all of the following are accepted and integrated:

- `HARD-004` — immutable launch and receipt authority;
- `HARD-005` — MCP read-boundary privacy/path hardening;
- `HARD-007` — authenticated principals and reviewer-independence policy.

Presence of this pack does not make `MCP-003` ready. Canonical state is recorded in [`BACKLOG.md`](../../docs/BACKLOG.md), and `scripts/audit-release-assets.py` enforces that this is the only active pack owning `MCP-003`.

## Scope

The single phase covers:

1. service and contract baseline verification;
2. bounded idempotent mutation tools;
3. independent security, identity, parity, and drift review.

The allowed tool candidates are pack validation, worktree creation, one bounded run launch, workflow validate/start/status/resume, and durable progress/ack/steer. A candidate must be omitted when its shared service, authenticated-principal rule, idempotency contract, sandbox boundary, or durable evidence mapping is not ready. The current `capabilities`, parser-derived role catalog, verified run command-context, and command-card resources are an integrated read-only baseline and must remain available. Future launch tools must reuse the CLI launch service so launch-contract v2, command artifacts, child environment pointers, and their digests remain identical across transports.

## Non-targets

No HTTP, MCP Tasks as lifecycle authority, arbitrary shell or paths, direct tmux controls, raw terminal capture, force kill, direct state-file mutation, alternate routing/scheduling, memory infrastructure, federation, persona catalogs, or dynamic MCP-tool generation from the CLI command catalog. Catalog membership is discovery metadata and never grants authorization.

## Execution

Start with `phase-0/tickets/MCP3-00-workflow-baseline.md`. Read current source, `BACKLOG.md`, `docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md`, `docs/DETERMINISM_SECURITY_HARDENING_PLAN.md`, `docs/ARCHITECTURE.md`, `docs/MCP_SERVER.md`, `docs/OPERATIONS.md`, and `docs/TESTING.md`.

```bash
python3 scripts/audit-release-assets.py
agent-workflow pack validate prompt-packs/mcp-server-next
```

Use both the `phase-gate-review` and `release-drift-auditor` skills before acceptance.
