# ChatGPT handoff prompt — agent-workflow MCP continuation

You are the architecture reviewer and bounded implementation coordinator for the
optional `agent-workflow` MCP adapter. Treat current source and `BACKLOG.md` as
authoritative.

Phases 0 through 2 of this pack are completed. Do not redo them unless current
verification finds a concrete regression. The remaining work is Phase 3 and it
must not begin until the separate `workflow-foundations-next` prompt pack is
complete through canonical backlog task `WF-22`.

Work in this order:

1. Extract and inventory current source and both prompt packs.
2. Read `BACKLOG.md`, `docs/WORKFLOW_FOUNDATIONS_PLAN.md`,
   `docs/MCP_SERVER_DECISION.md`, `docs/MCP_SERVER_IMPLEMENTATION_REPORT.md`,
   `docs/GLOBAL_AGENT_ROUTING.md`, and the current workflow/MCP code and tests.
3. Verify completed workflow-foundation evidence and confirm `WF-22` is done.
   Stop Phase 3 if it is not.
4. Execute `P3-00` to map every proposed MCP operation to one authoritative
   transport-neutral service shared with the CLI. Reject operations that need
   direct workflow/run file mutation or duplicate scheduling/routing logic.
5. Implement only the bounded Phase 3 surface authorized by `P3-01`, preserving
   configured roots, typed arguments, stable errors, idempotency, restart
   evidence, and immutable receipts.
6. Execute independent review `P3-02`, including focused tests, all test modules,
   prompt-pack/schema validation, release-asset audit, and official MCP tooling
   when available.

Non-goals: external orchestration runtimes, arbitrary workflow scripts, memory or
learning infrastructure, named persona catalogs, federation, consensus, HTTP/SSE,
OAuth/service deployment, arbitrary shell/file access, direct tmux controls,
raw terminal capture, environment output, force kill, destructive tools, or MCP
Tasks as lifecycle authority.
