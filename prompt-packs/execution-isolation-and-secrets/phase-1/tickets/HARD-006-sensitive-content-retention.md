# HARD-006 — sensitive-content classification, redaction, and retention

**Backlog:** [`HARD-006`](../../../../docs/BACKLOG.md)  
**Priority:** P1 / High  
**Assessment:** [F44-F47, F64, F81-F85](../../../../docs/FEATURE_DETERMINISM_SECURITY_ASSESSMENT.md#7-security-posture-by-trust-boundary) and the [hardening plan](../../../../docs/DETERMINISM_SECURITY_HARDENING_PLAN.md)

## Goal

Define and enforce which prompt, command, log, message, provider, telemetry, report, and MCP fields may contain sensitive content; redact by default and make retention/deletion explicit.

## Current risk

Durable operational records can contain source text, credentials, prompts, command arguments, terminal output, and provider data. Current guidance tells agents not to disclose secrets, but content is not consistently classified, filtered, or expired.

## Required implementation

- Define a small classification model such as metadata, operational text, source-derived content, credential/secret, provider-sensitive, and prohibited. Apply it at ingestion and serialization boundaries, not only at display time.
- Centralize redaction using exact configured secrets plus high-confidence patterns. Preserve field presence, length, digest, and redaction reason where correlation is required. Never claim pattern scanning finds every secret.
- Set metadata-only defaults for MCP, telemetry, reports, diagnostics, and list/status views. Full content requires a named local opt-in policy and remains unavailable to MCP unless separately authorized in future work.
- Define retention periods and deletion/tombstone behavior for logs, messages, raw provider streams, prompts, spool files, telemetry buffers, and exported reports. Never delete sealed authority required for verification; separate retained digest/metadata from content payload where necessary.
- Add a local scrub/audit command or service that reports classified fields and retention state without dumping their content.
- Document what is never collected, what is retained, and what an operator must remove before sharing evidence.

## Writable paths

- shared redaction/classification/retention modules; messages, runner/logging, provider evidence, reporting, MCP, telemetry integrations
- config/schema additions for opt-in and retention policy
- installed-product synthetic-secret journeys and focused classification matrix
- SECURITY.md, SUPPORT.md, OPERATIONS.md, EVIDENCE_AND_EVALUATION.md, MCP_SERVER.md

Do not broaden this scope without a recorded stop-and-escalate decision. Changes to shared documentation, schemas, tests, or manifests are allowed only when required by the implemented behavior.

## Parallel execution and dependencies

Depends on HARD-008 within this pack and the accepted HARD-001/HARD-005 foundations externally. Run in parallel with HARD-003.

Use a dedicated worktree and session. Do not share a writable checkout with another ticket.

## Acceptance-first evidence

- Synthetic secrets injected through prompt, argv, environment, child stdout/stderr, durable messages, provider events, and report text never appear in default CLI/MCP/telemetry outputs.
- Authorized local full-content access is explicit, audited, and still applies redaction for credential-class values.
- Retention enforcement removes eligible content payloads, preserves required authority metadata/digests, and is idempotent across restart.
- Export/share journeys list included sensitive classes and refuse prohibited content.
- No test reads real host credentials or proprietary source.

A low-level test is permitted only for a compact parameterized security/replay matrix that the installed-product journey cannot exercise exhaustively. Do not restore parser-shape, mock-call, prose-wording, exact-dictionary, or broad snapshot tests.

## Security acceptance

- Redaction occurs before logs/protocol responses are emitted.
- Retention cannot invalidate sealed evidence silently.
- Telemetry exporters use field allowlists, not broad object serialization.
- Errors and correlation IDs do not embed sensitive values or host paths.

## Non-targets

- Do not build a DLP platform, model-based secret classifier, remote vault, or content search database.
- Do not expose message bodies through MCP.
- Do not delete evidence solely to make a failing security test pass.

## Stop conditions

- HARD-001/HARD-005 foundations or HARD-008 policy surface is absent.
- A retention rule would destroy authority needed to verify a run; redesign payload separation first.
- The implementation relies on sending sensitive content to an external classifier.

## Completion handoff

Use `templates/TICKET_COMPLETION.md`. Include the exact revision, changed paths, acceptance commands and exit codes, retained invariant matrices with justification, unresolved risks, and all documentation/diagram/help/schema/skill/manifest updates. Run `python3 scripts/audit-release-assets.py` before claiming completion.
