# P1-00 — MCP server architecture decision research

## Role and constraint

You are a research lead. Do not modify application runtime code, package
dependencies, schemas, skills, or configuration. Produce a cited Markdown
decision memo at `docs/MCP_SERVER_DECISION.md` plus a concise proposed backlog
update; do not apply the backlog update yourself.

## Writable paths

Only `docs/MCP_SERVER_DECISION.md` and a ticket completion report/evidence
directory designated by the operator. No other repository file may change.

## Question

Determine whether MCP is the right integration layer for `agent-workflow`, and
if so propose the smallest secure incremental server surface that makes its
durable run lifecycle, evidence, control records, prompt-pack operations, and
tmux-backed launches usable by MCP clients without falsely promising executor
steering delivery.

## Required research

Use primary sources only. Compare current MCP specification and official SDKs
for Python, TypeScript, and any officially supported alternatives; relevant
server frameworks; representative MCP clients/hosts; stdio, Streamable HTTP,
and legacy HTTP/SSE transports; authentication/authorization; tool/resource/
prompt semantics; sampling/elicitation where applicable; cancellation;
progress/logging; session lifecycle; capability negotiation; and deployment
security. Verify version and maintenance status from official sources.

Evaluate: no MCP server; a thin in-process Python MCP server wrapping existing
domain APIs; a separate local daemon/service; direct tmux exposure; and a
future broker-backed multi-host MCP gateway.

## Repository constraints

- `messages.jsonl` and sealed run receipts remain authoritative.
- MCP notifications are advisory; they cannot replace durable replay.
- Never expose arbitrary shell execution, raw `send-keys`, unrestricted path
  access, or secrets through a tool.
- A `steer` tool may persist a request but must report it as pending until a
  verified executor acknowledgement exists.
- Reuse existing validation, safe identifiers, state-root boundaries, receipts,
  and worktree protections. Do not fork lifecycle logic in an MCP handler.
- Single-host local use is the initial deployment assumption. Multi-host,
  broker, and external authentication work need explicit authorization.

## Required memo contents

1. Executive recommendation with confidence and rejected alternatives.
2. Current architecture inventory, including BKL-006 and durable-control
   boundaries.
3. SDK/framework/client matrix: license, maintenance, Python/protocol/transport
   coverage, auth hooks, testing ergonomics, operational burden, and fit.
4. Capability map separating resources from mutating tools, including inputs,
   outputs, authorization, evidence, idempotency, and excluded unsafe actions.
5. Local-stdio-first transport/deployment recommendation plus any conditional
   HTTP evolution, session, cancellation, progress, and error semantics.
6. Threat model: traversal, injection, confused deputy, cross-run access, tmux
   visibility, credentials, leakage, denial of service, destructive lifecycle.
7. Phased implementation plan with bounded tickets, tests/evals, rollback,
   versioning, and stop conditions.
8. Maintainer decisions required, and direct official sources/access dates.

## References

- `docs/AGENT_WORKFLOW_SKILL_INTEGRATION_P0.md`
- `docs/Durable_Orchestration_Delivery_Benchmarks.md`
- `docs/ARCHITECTURE.md`, `docs/COMMAND_REFERENCE.md`, and
  `docs/DELEGATION_LIFECYCLE.md`
- `BACKLOG.md`

## Acceptance criteria

The memo is actionable without an implementation patch, does not rely on
unofficial SDK claims, maps every proposed operation to durable evidence, and
makes a clear go/no-go recommendation with a minimal first phase. It rejects
any design that bypasses validation or treats tmux text as proof of delivery.
