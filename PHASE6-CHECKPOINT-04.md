# Phase 6 Checkpoint 04

Cumulative changes-only overlay from the authoritative verified Phase 3 source.

## Slice

`CAP-001` MCP isolation review plus deletion-aware overlay delivery.

- Retains all prior Phase 4/5 and Phase 6 cumulative changes.
- Confirms normal CLI/scoped delegate paths load neither the MCP package nor MCP SDK.
- Retains the read-only stdio MCP adapter behind its existing optional entry point and `mcp` dependency group.
- Does not extract/wrap MCP because no measurable unused-path cost or cleaner authority boundary would result.
- Leaves `MCP-003` mutation deferred until authenticated-principal/idempotency prerequisites are authorized and implemented.
- Introduces the self-applying overlay format with cumulative deletion manifest and safe apply script.

## Measurement

Clean `/usr/bin/python3` measurements:

- import `agent_workflow.cli`: ~32–38 ms / 134 modules; no MCP package/SDK loaded;
- scoped `delegate` parser construction: ~3–6 ms / 87 modules; no MCP package/SDK loaded.

## Verification policy

The test suite was intentionally not run. No MCP runtime code changed in this slice. Python source was syntax-parsed only; the import measurements above were executed explicitly.
