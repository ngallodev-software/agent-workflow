# COMP-001 findings: completion-sidecar validation and diagnostics

Research run: comp-001-research-20260830
Base revision: 39826f0d7594c661631d9a3cc70f82f68585a3a2
Incident reference: AGENT_WORKFLOW_COMPLETION_HANDOFF_AND_NAME_LEASE_INCIDENT_20260830.md

## Executive Summary

Two independent product gaps prevent reliable completion handoff validation and operator diagnostics:

1. Completion sidecar schema-validation gap (COMP-001): Workers submit sidecars with invalid enum values ("verified" instead of "pass") because:
   - No pre-submission validator is available to workers before task-complete
   - The schema defines only ["pass", "fail", "not_verified"] for criteria[].result
   - Semantic validators run after JSON schema validation, masking exact field errors
   - Diagnostic classification conflates schema errors with missing executables

2. External run name-lease retirement gap (LEASE-001): Operator cannot release preferred names from external prepared runs:
   - status_agent_active() returns True for "prepared" status (line 52)
   - claim_agent_name() uses this check to hold names (lines 257-261)
   - External lifecycle control (agent-run terminate) cannot modify prepared runs
   - No explicit retirement action exists for dead external runs

## Issue 1: Completion Sidecar Validation and Diagnostics

### Affected Symbols

Completion validation chain:

File: src/agent_workflow/completion.py:36-146
Function: substantive_completion_errors()
Role: Semantic validator
Issue: Runs after schema validation; cannot show field-level errors to worker

File: src/agent_workflow/completion.py:209-281
Function: validate_completion_handoff()
Role: Pre-submission validator
Issue: Exists but not exported for worker use

File: src/agent_workflow/diagnostics.py:8-12
Function: _FAILURE_RULES tuple
Role: Diagnostic classifier
Issue: Rule order wrong; command_not_found matched before completion_invalid

File: src/agent_workflow/diagnostics.py:31-42
Function: classify_failure()
Role: Failure classifier
Issue: Uses _FAILURE_RULES in order; first match wins

File: schemas/completion.schema.json:64-75
Schema: criteria[].result enum
Issue: Only ["pass", "fail", "not_verified"] allowed; "verified" is invalid

### Proposed Design

COMP-001.A: Worker-facing validator
- New public API: validate_completion_sidecar(handoff_path: Path)
- Returns field-level errors with acceptable enum values
- Does NOT validate semantics (requires full launch context)
- Does NOT modify handoff

COMP-001.B: Diagnostic rule reordering
- Reorder _FAILURE_RULES in diagnostics.py
- Match completion-specific patterns (contains "criteria", "enum") BEFORE generic patterns
- S-018/S-019 errors will classify as completion_invalid, not command_not_found

COMP-001.C: Bounded correction path
- Allow handoff fixes while run in-flight (prepared/running/blocked)
- Worker detects schema error via validator
- Worker fixes enum value in handoff
- Worker calls validator again
- On success, proceeds to task-complete
- Preserve rejected sidecar as .completion.json.rejected

### Test Requirements

Test: Schema rejection of "verified"
Behavior: Submit criteria[0].result: "verified", expect schema error with path
Evidence: completion.schema.json validates enum

Test: Field-level error extraction
Behavior: Call validator, get path and acceptable values
Evidence: Validator API contract

Test: Classification precedence
Behavior: S-018/S-019 classify as completion_invalid
Evidence: Error text has "criteria" and "enum"

Test: Correction acceptance
Behavior: Fix handoff, re-validate, pass
Evidence: Worker UX

Test: Post-terminal rejection
Behavior: Attempt fix after completed, expect error
Evidence: Lifecycle safety

## Issue 2: External Run Name-Lease Retirement

### Affected Symbols

Name lease management chain:

File: src/agent_workflow/agent_identity.py:40-54
Function: status_agent_active()
Role: Liveness check
Issue: Returns True for "prepared"; treats dead external as active

File: src/agent_workflow/agent_identity.py:237-287
Function: claim_agent_name()
Role: Name reservation
Issue: Uses status_agent_active() result; holds name if check passes

File: src/agent_workflow/run_lifecycle.py
Function: authoritative_execution_status()
Role: Status query
Issue: Returns "prepared" for external runs

File: schemas/agent-name-lease.schema.json
Schema: agent-name-lease/v1
Issue: No retirement_authority field

### Proposed Design

LEASE-001.A: Retirement action
- New function: retire_external_agent(settings, agent_run_id, reason)
- Preconditions: status == "prepared", no active binding, not self-run
- Appends immutable retirement_authority lifecycle event
- Marks run as "retired" (terminal status)
- Releases preferred name only after retirement durable

LEASE-001.B: Binding helpers
- New function: has_external_binding(settings, item) -> bool
- New function: can_retire_prepared(settings, item) -> bool
- Distinguish prepared-awaiting-launch from prepared-with-dead-binding

LEASE-001.C: Schema extension
- Update agent-name-lease.schema.json with optional fields
- external_binding (provider, pool_name, worker_id, updated_at)
- retirement_authority (actor, timestamp, action, reason)
- Backward compatible; existing leases remain valid

### Test Requirements

Test: Reject bound external
Behavior: Create prepared with binding, attempt retire, expect error
Evidence: has_external_binding returns True

Test: Reject completed run
Behavior: Create completed run, attempt retire, expect error
Evidence: Status check rejects

Test: Release name
Behavior: Retire prepared run, verify lease deleted and name available
Evidence: release_agent_name succeeds

Test: Historical preservation
Behavior: Retire run, verify original record untouched
Evidence: Both original and retirement event in log

Test: Idempotent retirement
Behavior: Retire twice, second call returns same event
Evidence: Retry-safe

Test: Reject self-retirement
Behavior: Current run attempts to retire itself, expect error
Evidence: Self-protection

## Backlog Items

COMP-001: Provide field-level completion-sidecar validation

Description: Workers need pre-submission validation to catch schema-invalid enum values ("verified" vs "pass"). Export validate_completion_sidecar() API to show field paths and acceptable values.

Scope:
- New public API: validate_completion_sidecar(handoff_path)
- Reorder diagnostic rules in diagnostics.py
- Add bounded correction path (prepared/running/blocked only)
- Preserve rejected sidecar as evidence

Affected files:
- src/agent_workflow/completion.py
- src/agent_workflow/diagnostics.py
- tests/invariants/test_completion_*.py

Acceptance:
- Schema-invalid "verified" rejects with field path
- S-018/S-019 errors classify as completion_invalid
- Worker API available and documented

LEASE-001: Support explicit retirement of external prepared runs

Description: External runs stuck in "prepared" state hold preferred names indefinitely. Add explicit, auditable retirement action with immutable lifecycle events.

Scope:
- New function: retire_external_agent(settings, agent_run_id, reason)
- Add has_external_binding() and can_retire_prepared() helpers
- Update agent-name-lease.schema.json with optional retirement_authority field

Affected files:
- src/agent_workflow/agent_identity.py
- schemas/agent-name-lease.schema.json
- tests/invariants/test_agent_identity.py

Acceptance:
- Retirement succeeds for prepared external runs with no binding
- Retirement rejected for completed/running/bound runs
- Name released after retirement and becomes available
- Historical record preserved with retirement event
- Idempotent (retry-safe)

## Summary

Both gaps are isolated, have exact affected symbols, and can be fixed independently:

1. COMP-001 improves worker UX; fixes localized to completion validation and diagnostics
2. LEASE-001 improves operator workflow; fixes localized to agent identity and name-lease management

Neither requires schema-breaking changes. Both have clear test boundaries and audit trails.
