# Phase 6 Checkpoint 05

Cumulative changes-only overlay from the authoritative verified Phase 3 source.

## Slice

Hook installation canonicalization.

- Retains all prior Phase 4/5 and Phase 6 cumulative changes.
- Collapses duplicate historical Codex managed hook blocks to one canonical block.
- Canonicalizes Agent-Workflow-owned Claude hook commands across duplicate groups.
- Canonicalizes the explicitly supplied external codebase-memory gate.
- Removes retired files only from the bounded Agent-Workflow-owned hook filename set.
- Preserves unrelated user hook entries and files.
- Adds one release-level repeated-install/migration journey covering the regression.

## Verification policy

The Agent-Workflow test suite was intentionally not run. Changed Python was AST-parsed only.
