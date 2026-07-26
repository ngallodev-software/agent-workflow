# MSG-001 — orchestrator identity registry and durable aggregate inbox

**Backlog:** [`MSG-001`](../../../../docs/BACKLOG.md)  
**Priority:** P0 / Critical  
**Design:** [Shared orchestrator inbox](../../../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#add-one-shared-orchestrator-inbox)

## Goal

Create the deterministic storage and schema layer that registers an orchestrator and its child sessions, then records normalized child-to-orchestrator delivery events in one append-only aggregate inbox.

## External prerequisites

- `DEC-001` is resolved.
- `HARD-002` and `HARD-004` are accepted.

## Required implementation

- Define versioned schemas for orchestrator identity/registry entries, normalized inbox events, delivery acknowledgements, and action references.
- Store orchestrator state below the configured XDG state root using a non-sensitive stable identifier. Do not embed repository paths, usernames, prompts, ticket titles, or secrets in directory or wake-channel names.
- Register child sessions through immutable launch/session evidence. A caller-supplied `sender_session_id` is not sufficient.
- Implement an append-only, locked, fsynced `inbox.jsonl` with monotonic sequence allocation and bounded record size.
- Normalize only allowed source message kinds into inbox event kinds. Preserve source journal identity, source sequence, source message ID, and digest so delivery can be independently revalidated.
- Treat the inbox as delivery authority, not lifecycle authority. An `agent_idle` event must reference source completion/state evidence; it cannot manufacture idle state.
- Make duplicate normalized events idempotent by stable source identity and digest. Conflicting duplicate identity must fail closed.
- Add bounded read/list operations by sequence and event ID. Full content exposure must honor the sensitive-content policy; metadata-only output is the default where policy requires it.
- Provide deterministic registration/unregistration semantics for completed or abandoned child sessions without deleting source evidence.

## Writable paths

- New orchestrator registry/inbox service modules and schemas.
- CLI/service surfaces for creating/inspecting a registry only when necessary.
- Acceptance journeys and compact append/dedup/path matrices.
- Architecture and operations documentation where public behavior changes.

Run in parallel with `BKL-001`. Do not implement the supervisor loop, tmux waiting, or resume adapters in this ticket.

## Acceptance-first evidence

Tests must exercise the installed public command/service path first; retain only a compact low-level matrix where exhaustive replay or security cases cannot be expressed economically end to end.

- An installed CLI creates an orchestrator registry, registers two verified child sessions, imports one valid completion from each, and lists two ordered inbox events.
- Reimporting the same source records produces no duplicate semantic events.
- Reusing a source ID with a different digest fails closed.
- A source record that claims another session identity is rejected.
- An event cannot declare `idle_reusable` without matching source lifecycle/assignment evidence.
- Inbox reads are bounded and stable after process restart.

## Security acceptance

- Registry and inbox files reject symlinks, traversal, special files, oversized lines, invalid UTF-8 where the contract requires text, and writable substitution of sealed evidence.
- Registration binds to immutable session evidence and authenticated principal rules available after `HARD-007`; until then, the feature remains blocked from production use.
- Event summaries are classified/redacted according to `HARD-006`; unsafe content may be retained only under explicit policy and is never injected into a pane.

## Non-targets

- Shared wakeup (`MSG-002`).
- Orchestrator notification/resume (`MSG-003`).
- Scheduler action semantics (`MSG-004`).
- MCP exposure.

## Stop conditions

Stop when source authority cannot be verified from immutable evidence, schema fields duplicate mutable status projections, or a proposed API exposes unbounded message bodies by default.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include schemas, storage layout, authority table, import/dedup evidence, public interfaces expected by `MSG-002`, and drift-audit results.
