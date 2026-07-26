# HARD-005 — MCP read-boundary privacy and path hardening

**Backlog:** [`HARD-005`](../../../../BACKLOG.md)  
**Priority:** P0 / Critical  
**Assessment:** [F83-F88](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#46-mcp-adapter) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Harden the existing local stdio read-only MCP surface before any mutation work: metadata-minimal responses, component-wise no-follow paths, stable descriptor reads, bounded pagination/output, and opaque normalized errors.

## Current risk

The current message listing exposes complete steer/progress/ack bodies, path validation can lose the original symlink chain after resolution, receipt summaries can use weaker file iteration than lifecycle verification, and unexpected exceptions can leak local detail.

## Required implementation

- Change message listing to metadata-only by default: identity, type, actor/principal placeholder, timestamps, correlation/disposition, content length/digest, and redaction state. Do not return body text through existing tools/resources.
- Do not add a content-reading tool in this ticket. Document a future separately authorized/redacted capability only if needed.
- Replace resolve-before-validation with component-wise no-follow containment shared with HARD-002. Validate configured roots, repository/pack paths, state roots, and receipt entries without check-then-open races.
- Read receipt summaries using the same stable descriptor and validation rules as lifecycle verification. Reject irregular, writable, duplicate, malformed, or noncontiguous authoritative entries rather than silently presenting an incomplete authority view.
- Define versioned bounded result envelopes, pagination ceilings, text/array limits, and stable error categories. Unexpected failures return an opaque correlation ID; local logs are redacted.
- Launch the stdio server through a sanitized environment and make SDK absence/import safety behavior deterministic.

## Writable paths

- src/agent_workflow/mcp/** and shared no-follow/receipt helpers from HARD-002
- installed-product stdio MCP journeys and focused path/privacy matrices
- docs/MCP_SERVER.md, SECURITY.md, command/help/man surfaces only where changed

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

Depends on HARD-002. It may run in parallel with HARD-004. MCP-003 remains blocked until HARD-004, HARD-005, and HARD-007 are accepted.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- A real stdio client lists runs/status/messages/receipts and receives only allowlisted bounded fields.
- Synthetic secret text in durable messages never appears in default MCP responses, protocol errors, or logs.
- Final and intermediate symlink pack paths are rejected even when they resolve inside an allowed root.
- Receipt replacement/irregular-entry fixtures fail closed and do not produce partial authoritative summaries.
- Oversized pagination or malformed IDs return stable non-secret errors; unexpected exceptions expose only a correlation ID.
- CLI read behavior remains compatible where it shares services, without forcing MCP disclosure parity.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- No raw terminal capture, prompt, argv, environment, workdir, arbitrary artifact path, or message body in default results.
- No mutation, direct state parsing, raw filesystem browsing, or alternate lifecycle authority.
- Output bounds apply before serialization and transport write.

## Non-targets

- Do not implement MCP-003 mutation tools.
- Do not add HTTP/SSE/OAuth or remote deployment.
- Do not expose full content behind a casual boolean flag.

## Stop conditions

- HARD-002 is not accepted.
- A read cannot be produced from verified bounded data without direct state mutation or unsafe path traversal.
- The pinned MCP SDK requires a transport behavior that would broaden disclosure or mutation.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
