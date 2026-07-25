# MCP server implementation and routing verification report

**Repository baseline:** `agent-workflow` 0.1.8 source archive supplied 2026-07-24  
**Review date:** 2026-07-24  
**Scope:** `mcp-server-next` prompt pack, global routing, tmux wakeups/layout, agent identity, interactive sessions, and model routing

## Result

Phase 1 and the locally testable portion of Phase 2 are implemented. MCP remains an optional local stdio adapter and does not become lifecycle authority. No HTTP listener, OAuth surface, arbitrary path access, raw terminal capture, shell execution, direct tmux control, destructive tool, or MCP Task lifecycle was added.

## Primary-source refresh

| Source | Version / state checked | Accessed | Implementation implication |
|---|---|---:|---|
| MCP specification, `modelcontextprotocol.io/specification/2025-11-25` | 2025-11-25 remains the published stable specification on the review date; a later 2026-07-28 release candidate was announced but was not stable | 2026-07-24 | Keep the implementation on the selected stable protocol and do not adopt draft/RC-only behavior. |
| Official Python SDK, `github.com/modelcontextprotocol/python-sdk` | Stable 1.x line; project pin remains `mcp==1.28.1` | 2026-07-24 | Use public `mcp.server.fastmcp.FastMCP` APIs; do not import or vendor private runtime modules. |
| Official SDK testing guide, bundled 1.28.1 snapshot `docs/testing.md` | Public in-memory test helper uses `create_connected_server_and_client_session(app, raise_exceptions=True)` | 2026-07-24 | Protocol-facing tests must use `ClientSession`, not `_tool_manager`, `_resource_manager`, or other private managers. |
| MCP Inspector documentation, `modelcontextprotocol.io/docs/tools/inspector` | Inspector is the official interactive server testing/debugging tool | 2026-07-24 | Inspector execution remains an operator/environment gate because Node packages and the MCP extra are unavailable in this archive environment. |
| MCP debugging guide, `modelcontextprotocol.io/docs/tools/debugging` | Stdio servers log to stderr and Inspector is the recommended first-line tool | 2026-07-24 | Server stdout remains reserved for protocol traffic; startup failures are sent to stderr. |

## Architecture review

The approved boundaries remain sound:

- durable JSON artifacts and receipts remain authoritative;
- MCP calls transport-neutral read services and pack validation only;
- repository and state roots are configured, realpath-contained, and symlink escapes are rejected;
- status output is allowlisted and excludes raw paths and error strings that may disclose local information;
- messages come only from the durable append-only log, never terminal capture;
- receipt resources return bounded names and SHA-256 digests, not arbitrary file bodies;
- MCP does not expose launch, steering, interrupt, kill, tmux, shell, environment, or HTTP surfaces;
- actor identity is instance-scoped as `mcp-stdio:<uuid>` for future audit use, without claiming a workflow run.

## Implemented files

- `src/agent_workflow/mcp/services.py`: immutable requests/pages, hard pagination bounds, stable service errors, root containment, status redaction, message/receipt listing, and pack validation.
- `src/agent_workflow/mcp/server.py`: thin FastMCP stdio adapter over the shared service boundary.
- `tests/test_mcp_services.py`: invalid IDs, missing runs, pagination limits, redaction, traversal, symlink escapes, and receipt hash behavior.
- `tests/test_mcp_server.py`: optional dependency error behavior and public protocol-facing SDK test shape.

## Recent orchestration verification

### Durable tmux wakeups

`messages.jsonl` remains authoritative. The wake channel is a versioned SHA-256 digest of the resolved run directory. `tmux wait-for` signal/wait failures and timeouts fall back to durable replay polling; no terminal text or retained signal is treated as delivery proof.

### Visible panes and fallback

Interactive launches, and non-interactive launches explicitly configured for `shared_window`, resolve the invoking tmux window and split into the configured agent column. Missing/stale tmux context falls back to a dedicated named session. Pane names and targets are persisted. Cosmetic global tmux options are now best-effort and cannot invalidate an otherwise prepared launch; concrete session/pane creation still enforces tmux availability.

### Agent naming and profiles

Preferred names are allocated only when inactive; generated names use the configured prefix and a stable numeric suffix. Explicit names must be preferred or generated-format names. Profiles can constrain class, executor, model, no-go authorization, and interactivity. Active-name reuse is rejected except for controlled restart behavior.

### Agent classes, interactive sessions, and model routing

Class policy selects default executor/model, allowed executor-model pairs, and interactive mode. Executor policy separately enforces the executor allowlist and no-go model authorization. Interactive Codex/Claude launches use their TUI entrypoints; non-interactive launches use structured/print commands. Structured execution defaults non-interactive unless explicitly overridden. Receipts and command metadata preserve agent name, class, executor, model, interactive state, and no-go authorization.

### Global routing

`docs/GLOBAL_AGENT_ROUTING.md` remains consistent with implementation: semantic classification belongs in global instructions/skills, while `agent-workflow launch` is the durable boundary. Raw host-native subagents or raw tmux processes do not receive workflow worktrees, receipts, policy, or review gates.

## Verification evidence

- Focused MCP/tmux/config/session tests: **30 passed, 1 skipped**.
- Full suite before manifest refresh: **100 passed, 1 skipped** through the release audit; the only failure was expected manifest drift from changed/new files.
- MCP protocol test and Inspector execution: **not run locally** because `mcp==1.28.1` and Node-based Inspector dependencies were unavailable in the execution environment. The test is written against the official public in-memory helper and will run when the `mcp` extra is installed.

## Residual risks and next gate

Before declaring external-host conformance complete, install the pinned MCP extra in a clean Python 3.11+ environment, run the protocol-facing test, start `agent-workflow-mcp` over stdio, and exercise list/read/call operations with the official Inspector. Keep HTTP, mutations, and lifecycle tools behind separate architecture and security gates.


## Workflow-foundation sequencing update

The completed read-only MCP server remains valid. Remaining mutating MCP tools
are intentionally blocked until canonical backlog task `WF-22` completes the
workflow scheduler, approval gates, structured result binding, aggregate
receipts, authorized templates, routing explanations, and integration review.

After that gate, MCP Phase 3 may expose bounded workflow validate/launch/status/
resume operations, but only by calling the same transport-neutral services used
by the CLI. MCP does not parse or mutate workflow state directly and does not
become a scheduler, routing authority, child launcher, approval authority, or
receipt writer of its own. See `prompt-packs/mcp-server-next/phase-3/`.
