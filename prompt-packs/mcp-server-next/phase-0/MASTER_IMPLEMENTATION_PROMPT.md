# MCP mutation phase master implementation prompt

Read the current workflow services, receipts, routing policy, MCP documentation, testing policy, and all phase tickets before editing.

Implement the smallest useful local-stdio mutation surface. Every MCP tool must call an existing validated service used by the CLI or a transport-neutral service added for both CLI and MCP. MCP must never parse or mutate workflow/run state directly.

Limit tools to the validation, creation, launch, workflow, and durable messaging operations explicitly authorized by the tickets. Preserve idempotency, configured-root containment, stable errors, bounded inputs/outputs, policy enforcement, and immutable evidence. Steering remains pending without correlated executor acknowledgement.

Extend installed-product MCP journeys first. Add a direct invariant only for a general security, replay, idempotency, or accounting boundary that cannot be exercised deterministically through the public protocol.
