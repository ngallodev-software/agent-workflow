# Phase 6 Checkpoint 01 — Common-Path Capability Isolation

This cumulative changes-only overlay is based on the authoritative verified Phase 3 source and includes the prior cumulative Phase 4/5 changes through Checkpoint 04 plus this Phase 6 slice.

## Changes in this slice

- reconciled `CAP-001` exposure isolation against the already-small role/skill surfaces;
- measured common-path parser/import cost before changing package boundaries;
- moved command-profile names to the dependency-free CLI contract so scoped parser construction does not import command-catalog/schema-validation machinery;
- made plugin registry imports lazy for built-in commands that do not need plugin discovery;
- made plugin execution context import lazy until an actual plugin command executes;
- kept plugin-aware command behavior and the single authoritative parser intact;
- recorded Phase 6 measurements and extraction decision rules in `docs/PHASE6_CAPABILITY_ISOLATION.md`;
- marked Phase 6 / `CAP-001` in progress.

## Verification performed

Per the Phase 4+ testing policy, no test suite was run. Edited Python files were checked with non-executing AST parsing. Clean-interpreter import/parser measurements were run only to establish the Phase 6 cost signal described in the capability-isolation document.
