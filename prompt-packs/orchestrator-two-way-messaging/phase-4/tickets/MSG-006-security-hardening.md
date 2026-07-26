# MSG-006 — adversarial messaging security hardening

**Backlog:** [`MSG-006`](../../../../docs/BACKLOG.md)  
**Priority:** P1 / Critical  
**Design:** [Security requirements](../../../../docs/ORCHESTRATOR_TWO_WAY_MESSAGING_DESIGN.md#security-requirements)

## Goal

Perform a dedicated adversarial hardening pass across the integrated two-way messaging implementation. Convert all remaining guidance-only safety claims into deterministic controls or document an explicit blocker.

## Dependencies and prerequisites

- Pack dependencies: `BKL-002`, `MSG-001`, `MSG-002`, `MSG-003`, `MSG-004`, `MSG-005`.
- External prerequisites: `HARD-001`, `HARD-002`, `HARD-004`, `HARD-006`, `HARD-007`, and `HARD-008` accepted.

## Required implementation and review

- Threat-model child, orchestrator, local unprivileged process, malicious repository, malicious prompt pack, stale process, and accidental operator error.
- Enforce source-session and principal identity binding for every send, import, acknowledge, action, wake, and steer operation.
- Apply bounded record size, batch size, event rate, retry count, log size, retention duration, and inbox growth policy.
- Verify no-follow/regular-file/beneath-root handling for registry, inbox, acknowledgements, cursors, locks, adapter state, and referenced evidence.
- Attempt symlink, hard-link, traversal, replacement, partial-write, duplicate-ID, sequence rollback, oversized-line, invalid-encoding, control-character, and concurrent-writer attacks.
- Verify child-controlled content never enters shell, argv positions not designed for content, terminal notification text, channel names, file paths, or unredacted diagnostics.
- Verify fixed notification templates cannot be overridden from child/repository-controlled configuration.
- Verify a child cannot acknowledge/action its own event or wake an unrelated orchestrator.
- Verify adapter and supervisor failures remain bounded and cannot fork unlimited processes or turns.
- Add stable security diagnostics and receipt evidence without leaking sensitive bodies.
- Update `SECURITY.md`, architecture, operations, diagrams, and threat-boundary language to match actual enforcement.

## Writable paths

- Messaging implementation security fixes.
- Compact parameterized security/replay matrices.
- `SECURITY.md` and directly affected architecture/operations/diagram documents.

Run in parallel with `MSG-007`. This ticket owns security implementation and invariant matrices; `MSG-007` owns installed-product/live journeys and compatibility documentation. Coordinate filenames before editing.

## Acceptance-first evidence

- A malicious completion summary containing prompt injection, shell metacharacters, ANSI controls, newlines, and oversized text cannot alter notification commands or orchestrator input.
- Symlink/traversal/replacement attacks against every messaging artifact fail closed.
- Conflicting duplicate source/event/action IDs fail closed.
- Rate and size limits prevent unbounded disk, memory, process, or pane-input growth.
- Principal substitution and cross-orchestrator event action attempts are rejected.
- Sensitive test values are absent from user-visible errors, logs, status, receipts, and default MCP-readable metadata.
- Supervisor restart and adapter retry remain idempotent under adversarial timing.

## Non-targets

- Implementing a new generalized sandbox or principal system; use the accepted `HARD-*` substrates.
- Remote/multi-host messaging.
- Broad unrelated security cleanup.

## Stop conditions

Stop and reject the phase if any claimed control remains prompt-only, if authenticated principals are unavailable, if a child-controlled value reaches pane injection, or if bounded resource policy cannot be enforced.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include threat actors, attack matrix, reproduced defects/fixes, retained risks, exact commands, and explicit preventative-versus-detective control classification.
