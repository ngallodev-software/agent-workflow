# MAINT-001 — behavior-preserving core decomposition

**Backlog:** `MAINT-001`  
**Priority:** P2 / Medium

## Goal

Split `sessions.py`, `cli.py`, `index_store.py`, `runner.py`, and the remaining mixed concerns in `process.py` through small, independently reviewable moves while preserving public imports and behavior.

## Required implementation

- Establish a baseline with installed-product and invariant tests.
- Move one cohesive concern per change into a narrow package/module.
- Leave compatibility imports or facades where public/internal callers already depend on the old module.
- Keep authority records, evidence bytes, parser-derived command metadata, error categories, and CLI behavior unchanged.
- Record module-size and dependency direction before/after each slice.

The first accepted slice already moved process environment and redaction policy into `agent_workflow.runtime` behind the `agent_workflow.process` facade. Continue with sessions launch/observation/control/recovery, runner execution/stream/control/sealing, index migrations/discovery/reconciliation/query, and CLI command-domain builders/handlers.

## Non-targets

No feature semantics, new configuration, repository split, framework rewrite, or cosmetic file shuffling.

## Acceptance

All existing installed journeys and compact invariants pass; import compatibility is proven; the phase report identifies the next slice without requiring a broad merge.

## Writable paths

Only the module/package being split, compatibility facade imports, and focused tests/docs required to prove unchanged behavior. One cohesive concern per ticket iteration.

## Tests

Run the affected installed-product journeys, compact invariants, release asset audit, and import-compatibility checks before and after the move.

## Stop conditions

Stop if the slice requires changing evidence schemas, CLI semantics, authority behavior, configuration, or unrelated feature code.

