# Phase 1 — MCP-0 domain seams and typed contracts

Extract the smallest reusable, transport-neutral MCP domain surface and prove the
CLI/MCP adapters share it without changing lifecycle semantics.

## Complexity and delegation

| Ticket | Tier | Risk | Dependencies | Reviewer requirement |
|---|---|---|---|---|
| P1-00 | B | Read-only seam audit | Phase 0 | coordinator review |
| P1-01 | A | Cross-module implementation | P1-00 | focused tests |
| P1-02 | A | Independent phase gate | P1-01 | separate reviewer |

## Ordering

Follow `task-manifest.yaml`. Do not execute dependent tickets concurrently.

No HTTP, tmux exposure, destructive tools, arbitrary filesystem APIs, or broad
CLI rewrite. Preserve schemas and durable evidence semantics.

Phase 0 outputs, MCP decision, code structure outline, current state/messages/
receipts/pack services, MCP scaffold, tests, and schemas.

Focused contract/service tests, existing CLI tests, full pytest, schema checks,
release audit, and independent diff review all pass.
