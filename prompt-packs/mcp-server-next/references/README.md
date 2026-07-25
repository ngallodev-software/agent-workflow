# References

Required source references in the companion archive:

- `docs/MCP_SERVER_DECISION.md` — approved decisions and phased capability map;
- `BACKLOG.md` — canonical MCP and orchestration task states;
- `src/agent_workflow/mcp/` and `tests/test_mcp_server.py` — current scaffold;
- `src/agent_workflow/{cli,config,state,messages,receipts,sessions}.py` — lifecycle
  and durable-record authorities;
- `schemas/`, `scripts/audit-release-assets.py`, and `MANIFEST.sha256` — release
  and wire-format gates;
- `src/agent_workflow/mcp/sdk/` — pinned official SDK source reference only;
- `docs/GLOBAL_AGENT_ROUTING.md` and `skills/agent-workflow-orchestrator/` —
  routing boundary and operational use.

Refresh web research from primary sources listed in the MCP decision. Record
exact stable versions and access dates. References constrain implementation;
current checked-out source remains authoritative.
