# P1-02 — Independent MCP-0 phase review

## Scope and writable paths

Use class `review`. Only the operator-designated review report is writable; do
not edit production source.

## Procedure and tests

Inspect the diff and trace every public service to its authority. Rerun focused
service/adapter tests, full pytest, schema validation, and release audit.

## Acceptance and stop conditions

Reject and stop on path escape, secret leakage, duplicated lifecycle logic,
private SDK imports, behavior drift, weak errors, missing bounds, or implementation
outside Phase 1. Produce a signed accept/reject report with exact commands and
revision.
