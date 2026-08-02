# MOD-GATE-2 — extraction gate

Verify the external evidence gate, one-subsystem scope, base-install independence, compatibility/rollback, release ownership, and installed-product journeys. Reject any broad monorepo split or extraction that moves authority without a stable service boundary.

## Writable paths

Review evidence only. Do not modify production source.

## Acceptance

Accept only one evidence-backed extraction with reversible migration, independent installation, preserved authority/evidence compatibility, and explicit release ownership.

## Tests

Independently install base-only, feature-enabled, upgraded, and rolled-back environments and rerun the declared core/feature journeys.

## Stop conditions

Reject broad repository splitting, multiple simultaneous extractions, missing rollback, or any extraction performed before its external evidence gate.

