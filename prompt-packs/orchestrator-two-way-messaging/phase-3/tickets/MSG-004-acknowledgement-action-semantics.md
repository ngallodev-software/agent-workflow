# MSG-004 — delivery, application, and action acknowledgement semantics

**Backlog:** [`MSG-004`](../../../../BACKLOG.md)  
**Priority:** P1 / High  
**Design:** [Acknowledgement model](../../../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#acknowledgement-model)

## Goal

Make the orchestrator’s handling of a child event auditable. Distinguish adapter delivery from orchestrator application acknowledgement and from the durable scheduling/lifecycle action taken in response.

## Dependencies and prerequisites

- Pack dependencies: `MSG-002`, `MSG-003`, `MSG-005`.
- External prerequisite: `HARD-007` accepted.

## Required implementation

- Define versioned records for `event_delivered`, `event_acknowledged`, and `event_actioned` with stable event ID, authenticated principal, timestamp, disposition, and optional resulting evidence reference.
- Add public inbox operations to list/read pending events, acknowledge responsibility, and record an action through shared typed services. Exact CLI names must fit the current hierarchy and be documented/generated consistently.
- Enforce legal state transitions. Delivery does not imply acknowledgement; acknowledgement does not imply action.
- An action record must reference an existing durable result such as assignment creation, steer message, workflow event, review request, or explicit no-action disposition with reason code.
- Make each operation idempotent. Repeating the same event/principal/action key returns the prior result; conflicting reuse fails closed.
- Keep pending/acknowledged/unactioned events visible to supervisor and operators according to policy.
- Integrate with existing agent reuse and workflow scheduling services rather than adding a second assignment or dependency system.
- Support explicit dispositions such as `assigned_followup`, `accepted_completion`, `requested_review`, `deferred`, `no_action_required`, and `rejected_security`.

## Writable paths

- Orchestrator inbox/ack/action services and schemas.
- Existing scheduling/session services only through narrow shared actions.
- Public CLI/help/man surfaces.
- Installed-product acknowledgement/action journeys and compact transition matrix.

## Acceptance-first evidence

Tests must exercise the installed public command/service path first; retain only a compact low-level matrix where exhaustive replay or security cases cannot be expressed economically end to end.

- A delivered event remains pending until an authenticated orchestrator acknowledges it.
- Acknowledging without action leaves it visible as unactioned.
- Creating a follow-up assignment writes the existing assignment/steer evidence and one linked action record.
- Repeating the same action is idempotent; changing its result reference under the same idempotency key fails closed.
- A child principal cannot acknowledge or action its own child-to-parent event.
- Restart preserves each state exactly.
- Operators can distinguish adapter failures, delivered-but-unread, acknowledged-but-unactioned, and fully actioned events.

## Security acceptance

- Principal identity comes from the authenticated boundary, not `--actor` labels alone.
- Event content is read through bounded/redacted services; acknowledgement commands do not echo arbitrary bodies by default.
- Action references are validated beneath configured roots and against the expected evidence type.

## Non-targets

- Autonomous LLM scheduling policy.
- A second workflow graph or task queue.
- MCP tools; MCP-003 may later wrap these services after its own authorization gate.

## Stop conditions

Stop if the only available identity is caller-supplied text, if action evidence cannot reference a durable result, or if integration duplicates existing assignment/workflow state.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the transition table, idempotency behavior, public command examples, linked scheduling evidence, and unresolved policy choices.
