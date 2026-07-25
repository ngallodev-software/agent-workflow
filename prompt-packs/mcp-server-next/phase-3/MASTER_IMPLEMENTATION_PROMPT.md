# Phase 3 master implementation prompt

Execute Phase 3 only after canonical backlog task `WF-22` is complete. Read the
current workflow service, receipts, routing policy, MCP decision, implementation
report, and all Phase 3 tickets before editing.

Implement the smallest useful mutation surface. Every MCP tool must call an
existing validated service used by the CLI or a transport-neutral service added
for both CLI and MCP. MCP must never parse or mutate workflow/run state directly.

Required tools are limited to safe validation, creation, launch, status/resume,
and durable messaging controls explicitly authorized by the tickets. Preserve
idempotency, configured-root containment, stable errors, bounded inputs/outputs,
and immutable evidence. Steering remains pending without correlated executor
acknowledgement.
