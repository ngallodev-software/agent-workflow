# MCP3-02 — independent workflow-aware MCP review

> **Execution prerequisite:** Do not execute this ticket until `HARD-004`, `HARD-005`, and `HARD-007` are accepted and integrated. `MCP-003` is the only backlog item owned by this pack.

## Goal

Independently verify that the MCP mutation phase is a thin adapter and did not create a second workflow, routing, lifecycle, or evidence authority.

## Review requirements

- Trace every MCP mutation to its authoritative service and durable record.
- Verify workflow child runs still pass through the existing launch boundary.
- Verify approval and aggregate receipt semantics are reused unchanged.
- Test idempotency, restart recovery, authorization, traversal/symlink defenses,
  bounded pagination/output, cancellation, and stable error mapping.
- Run official Inspector/conformance tooling when available and record skips
  honestly when dependencies are unavailable.
- Run installed-product MCP journeys, required invariant matrices, prompt-pack validation, schema checks, and the release-asset audit.

## Writable paths

Review evidence and narrowly scoped fixes only. Do not expand the MCP surface.

## Exit evidence

A review report identifies every tested tool, service mapping, durable artifact,
security result, skipped external check, and remaining deferred capability.

## Acceptance criteria

- Every exposed tool has one shared authoritative service and tested durable result.
- Workflow operations preserve child launch, approval, routing, and receipt boundaries.
- Security, idempotency, restart, and release checks pass or have explicit blocked evidence.
- The review identifies no alternate workflow or lifecycle authority inside MCP.

## Stop conditions

Stop and reject the MCP mutation phase if any tool bypasses shared services, weakens configured-root
or policy enforcement, overstates steering delivery, or cannot produce durable evidence.
Do not broaden scope to resolve unrelated failures.
