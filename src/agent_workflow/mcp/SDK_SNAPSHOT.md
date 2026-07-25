# MCP Python SDK snapshot

Research fetch: 2026-07-24.

- Repository: https://github.com/modelcontextprotocol/python-sdk
- Proposed implementation release: `mcp==1.28.1`
- Stable release revision: `777b8d06710c140e3606b0d4598e2aa48546c266`
- Stable branch comparison revision: `e8283746d01eb66fff678190e8e3da81d2f36924`
- Compared development revision: `837ef904f84658be94079ac1c00bf4d6da9a8330`
- Development-line finding: repository `main` documents SDK v2 as prerelease and
  says v1.x remains the production line.
- Approved package constraint: `mcp==1.28.1`.

This directory is a review snapshot, not yet an approved runtime vendoring
boundary. The implementation must use the package's public server/client APIs,
keep the SDK optional, and avoid copying SDK internals into `agent_workflow`.
