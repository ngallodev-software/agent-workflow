# Phase 2 — MCP-1 read-only local stdio server

Complete and harden the optional local stdio MCP server over accepted Phase 1
services using public APIs from `mcp==1.28.1`.

## Complexity and delegation

| Ticket | Tier | Risk | Dependencies | Reviewer requirement |
|---|---|---|---|---|
| P2-00 | B | Scaffold/conformance audit | Phase 1 | coordinator review |
| P2-01 | A | Server implementation | P2-00 | protocol tests |
| P2-02 | A | Security/conformance gate | P2-01 | independent reviewer |

## Ordering

Follow `task-manifest.yaml`. Do not execute dependent tickets concurrently.

Stdio only. Read-only resources plus `pack_validate`; no lifecycle mutation,
raw terminal capture, HTTP, arbitrary paths, or private SDK APIs.

Accepted Phase 1 report, official stable SDK/spec research, MCP decision, current
server/tests, package metadata, installer, and release audit.

Import without MCP extra fails with a concise optional-dependency message; import
with the extra works. Focused resources, traversal/redaction, stdio smoke,
Inspector/conformance where available, full pytest, build, and release audit pass.
