# Code Structure Outlines

For each proposed module or interface, include:

1. ownership and authority boundary;
2. exact target path;
3. public types/functions and signatures;
4. persistence or wire-format shape;
5. error/outcome taxonomy;
6. migration and compatibility behavior;
7. tests justified by real contracts;
8. explicitly excluded adjacent work.

## Required seams

- `src/agent_workflow/mcp/contracts.py`: immutable typed request/result models for
  run listing, status, messages, receipts, pack validation, and stable errors.
- `src/agent_workflow/mcp/services.py`: transport-neutral bounded readers and
  pack validation adapters; all path containment and redaction lives here or in
  shared domain helpers, not MCP decorators.
- `src/agent_workflow/mcp/server.py`: thin FastMCP registration, actor identity,
  capability metadata, and stdio entry point. It must not call tmux or parse CLI
  text.
- `src/agent_workflow/cli.py`: preserve behavior; where practical, call the same
  service function as MCP and test the shared call boundary.
- `tests/acceptance/` installed-product MCP journeys plus focused invariant matrices: missing/invalid IDs,
  symlink escape, configured-root authorization, pagination bounds, redaction,
  receipt hashes, SDK absence, import safety, and stdio smoke/conformance.

Error outcomes must distinguish invalid input, forbidden root, missing object,
integrity failure, unsupported capability, and internal failure without leaking
paths or environment secrets. Outlines constrain implementation; they are not
permission to rewrite unrelated code.
