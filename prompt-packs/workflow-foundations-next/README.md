# workflow-foundations-next

Implement only the remaining workflow foundations authorized by `docs/WORKFLOW_FOUNDATIONS_PLAN.md`: restart-safe dependency scheduling, receipt-backed approval gates, bounded structured-result binding, three reusable graph templates, and deterministic routing explanations.

This pack must not add an external orchestrator, arbitrary workflow scripts, memory/learning infrastructure, named persona catalogs, federation, consensus mechanisms, or a second execution path. Every child run continues through `agent-workflow launch` and existing policy enforcement.


## Sequencing with MCP

Complete this pack through `WF-22` before executing Phase 3 of
`prompt-packs/mcp-server-next`. The existing read-only MCP server does not need
to be reimplemented. Remaining MCP mutation tools must consume the stable
workflow services produced here and must not duplicate scheduling, routing,
approval, or receipt logic.
