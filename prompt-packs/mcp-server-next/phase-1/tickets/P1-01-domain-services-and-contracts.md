# P1-01 — Domain services and typed MCP contracts

## Delegation metadata

- Recommended class: `implementation`
- Dependencies: P1-00 and accepted Phase 0
- Writable paths: `src/agent_workflow/mcp/`, narrowly required shared domain
  modules, focused tests, schemas/docs directly changed by the contract

## Objective

Implement immutable typed requests/results and transport-neutral services for
bounded run listing, status, messages, receipt metadata, and pack validation.

## Acceptance criteria

Services validate identifiers, enforce configured-root containment after realpath
resolution, reject symlink escapes, paginate with hard bounds, redact prohibited
fields, and return stable error categories. MCP decorators and CLI formatting do
not contain domain policy. At least one CLI/MCP operation is proven by tests to
call the same service boundary. Existing lifecycle output remains compatible.

## Necessary tests

Focused success/failure tests for invalid IDs, missing runs, forbidden roots,
symlink escapes, pagination bounds, redaction, receipt integrity, and shared
adapter invocation; then full pytest and release audit.

## Stop conditions

Stop if reuse requires lifecycle semantic changes, schema migration, destructive
actions, or a broad state-store rewrite. Return a bounded refactor proposal.
