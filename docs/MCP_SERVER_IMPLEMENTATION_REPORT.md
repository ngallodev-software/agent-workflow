# MCP server current implementation report

**Release:** 0.2.1
**Review date:** 2026-07-24
**Scope:** implemented read-only stdio adapter and boundary verification

## Result

The current MCP integration is an optional local stdio adapter over bounded shared read services. It does not own lifecycle or workflow authority. The executable is `agent-workflow-mcp`; there is no `agent-workflow mcp` subcommand.

Implemented capabilities:

- bounded run listing and allowlisted status resources;
- durable message resources with cursors/pagination;
- receipt metadata/digest resources without arbitrary artifact reads;
- configured-root pack validation;
- traversal, symlink, missing-resource, redaction, and pagination controls;
- clear optional-dependency failure when `mcp==1.28.1` is absent.

Not implemented:

- worktree creation, launch, workflow mutation, progress/ack/steer tools;
- interrupt/terminate/kill, review/accept/reject;
- raw shell, arbitrary commands/paths, environment access, tmux APIs, terminal capture;
- HTTP, OAuth, multi-user authorization, or MCP task lifecycle.

## Dependency and protocol boundary

The target remains MCP specification `2025-11-25` with optional Python SDK `mcp==1.28.1`. Runtime code uses public `mcp.server.fastmcp.FastMCP` APIs. The unused 141-file vendored SDK source snapshot was removed in 0.2.0; dependency provenance remains in `src/agent_workflow/mcp/SDK_DEPENDENCY.md`.

Primary sources reviewed on 2026-07-24:

- https://modelcontextprotocol.io/specification/2025-11-25
- https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- https://github.com/modelcontextprotocol/python-sdk/tree/v1.28.1
- https://modelcontextprotocol.io/docs/tools/inspector

## Shared-service boundary

`src/agent_workflow/mcp/server.py` registers protocol surfaces. `src/agent_workflow/mcp/services.py` performs bounded identifier/path validation and invokes existing read authorities. The adapter does not start processes, call tmux, write session/workflow state, infer delivery, or generate lifecycle receipts.

## Workflow sequencing status

WF-22 was completed in 0.2.0 and its workflow authority/replay boundaries were hardened in 0.2.1. The workflow scheduler, approval gates, result binding, aggregate receipts, templates, routing advice, and provider evidence are now stable prerequisites. Therefore `MCP-003` has moved from blocked to ready, but no mutation capability was added in this release.

The next implementation must follow [MCP Server Implementation Proposal](MCP_SERVER_IMPLEMENTATION_PROPOSAL.md): durable idempotency first, shared application services only, safe creation/workflow/message tools before destructive/review tools, and no HTTP without a separate authorization ADR.

## Verification surfaces

- `tests/test_mcp_services.py`
- `tests/test_mcp_server.py`
- `tests/test_optional_integrations.py`
- full repository suite and release audit recorded in `docs/execution-evidence/FINAL_CRITICAL_REVIEW.md`

MCP Inspector and representative external host checks remain environment-dependent gates for the future mutation release. They are not claimed as completed by this local source pass.
