# MCP mutation phase master implementation prompt

> **Execution prerequisite:** Do not execute this ticket until `HARD-004`, `HARD-005`, and `HARD-007` are accepted and integrated. `MCP-003` is the only backlog item owned by this pack.

Read the current workflow services, receipts, routing policy, MCP documentation, testing policy, and all phase tickets before editing.

Implement the smallest useful local-stdio mutation surface. Every MCP tool must call an existing validated service used by the CLI or a transport-neutral service added for both CLI and MCP. MCP must never parse or mutate workflow/run state directly. Treat the current read-only capability manifest, parser-derived role catalogs, and verified per-run command context/cards as compatibility requirements, not as authorization or a source for dynamically generated tools.

Limit tools to the validation, creation, launch, workflow, and durable messaging operations explicitly authorized by the tickets. Preserve idempotency, configured-root containment, stable errors, bounded inputs/outputs, policy enforcement, and immutable evidence. MCP `launch` and workflow child launch must call the same shared launch service as the CLI and produce launch-contract v2 with `command-catalog.json`, the role-scoped `command-card.md`, child environment pointers, and verified digests. Steering remains pending without correlated executor acknowledgement.

Extend installed-product MCP journeys first. Include one parity journey proving existing capability/catalog/run-command resources still work and that an MCP-launched child has the same command-context binding as a CLI-launched child. Add a direct invariant only for a general security, replay, idempotency, or accounting boundary that cannot be exercised deterministically through the public protocol.
