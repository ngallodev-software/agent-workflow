# P2-02 — Independent security and conformance review

## Scope and writable paths

Use class `review`; only the operator-designated review report is writable and
production source is read-only.

## Procedure and tests

Independently test malformed identifiers, URI templates, oversized limits,
traversal and symlink escapes, cross-root access, redaction, missing/tampered
receipts, missing optional SDK, cancellation, and clean stdio shutdown. Rerun
focused MCP tests, official conformance tooling where available, full pytest,
build, and release audit.

## Acceptance and stop conditions

Inspect imports and reject/stop if any private SDK API, HTTP listener, shell,
tmux, environment dump, raw capture, or destructive tool is exposed. Issue an
accept/reject report with exact revisions, commands, evidence, and residual risks.
