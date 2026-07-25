# P2-01 — Read-only local stdio MCP server

## Delegation metadata

- Recommended class: `implementation`
- Dependencies: accepted Phase 1 and P2-00
- Writable paths: `src/agent_workflow/mcp/`, MCP-focused tests, narrowly required
  package/installer/docs/schema files

## Objective and contract

Register bounded run list/status/messages/receipt and pack resources plus the
read-only `pack_validate` tool with FastMCP public APIs. Run only over stdio. Use
actor identity `mcp-stdio:<server-instance-id>`, declare capabilities accurately,
and map service errors without leaking filesystem or environment secrets.

## Tests and acceptance

Test registration, typed success/errors, URI and ID validation, pagination hard
limits, traversal/symlink denial, redaction, optional dependency absence, public
SDK imports, stdio initialization and one resource/tool request. Run official
Inspector/conformance tooling if supported locally and preserve versions/output.
Then run full pytest, build, and release audit.

## Stop conditions

Stop before adding mutation, HTTP/SSE, OAuth, raw capture, direct tmux, arbitrary
shell/path input, private SDK APIs, or MCP Tasks as lifecycle authority.
