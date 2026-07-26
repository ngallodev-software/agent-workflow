# HARD-007 — authenticated principals and reviewer independence

**Backlog:** [`HARD-007`](../../../../BACKLOG.md)  
**Priority:** P1 / Critical  
**Assessment:** [F48-F52 and F89](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#5-guidance-that-should-become-deterministic-enforcement) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Replace caller-selected actor labels with a minimal authenticated local principal contract and enforce independent review/acceptance policy from immutable identity evidence.

## Current risk

Lifecycle and message APIs validate actor strings but do not authenticate who supplied them. A same-user caller can label itself as another actor, so review independence and future MCP mutation authorization are procedural claims rather than enforceable controls.

## Required implementation

- Define a versioned principal record derived from an authenticated local mechanism appropriate for a single-host CLI: operating-system identity plus an explicitly configured signing/credential identity when stronger separation is required.
- Bind principal ID, authentication method, key/credential reference digest, process/session context, and authorization decision into immutable lifecycle and message evidence. Never store secret key material.
- Add policy rules for implementer/reviewer separation, self-acceptance denial, override authorization, and future MCP mutation. Actor display names remain commentary, not identity.
- Migrate CLI review/accept/reject/steer/progress/ack and shared services to obtain principal context from the trusted boundary rather than user-supplied labels alone. Preserve a compatibility path for historical receipts without upgrading their assurance claim.
- Define stable authorization errors and audit records. Authorization must occur before mutation and use the exact object/revision/evidence digest being decided.
- Expose principal assurance level in status/reports without revealing credentials or unnecessary host identity.

## Writable paths

- new or existing identity/authorization service, lifecycle/messages/CLI shared services, future MCP service seam
- principal and authorization evidence schemas/migrations
- installed-product spoof/self-review/override/restart journeys and compact policy matrix
- SECURITY.md, OPERATIONS.md, ARCHITECTURE.md, MCP_SERVER.md

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

External prerequisites: FOUND-GATE-01 and ISO-GATE-01 accepted. Run in parallel with HARD-009, HARD-010, and REL-003.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- A caller cannot become a different principal by changing `--actor` text.
- The same authenticated principal that implemented a governed high-risk run cannot accept it unless an explicit audited override policy permits it.
- Restarted review/acceptance retains principal evidence and remains verifiable from immutable records.
- Historical label-only receipts remain readable but are clearly classified as unauthenticated/legacy.
- MCP-003 service tests can consume the principal/authorization seam without inventing MCP-local identity.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- Authentication secrets never enter status, logs, receipts, prompts, or MCP responses.
- Authorization is checked before mutation and is bound to the target evidence digest.
- Local same-user limitations are documented honestly; do not claim multi-user isolation without it.

## Non-targets

- Do not add HTTP OAuth, a hosted identity provider, organization accounts, RBAC database, or remote federation.
- Do not implement MCP mutation tools.
- Do not rewrite historical receipts to appear authenticated.

## Stop conditions

- HARD-004 is not accepted.
- No maintainer decision exists for the minimum assurance required for independent review; produce an ADR proposal and stop before claiming enforcement.
- The approach stores reusable secrets in repository or run state.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
