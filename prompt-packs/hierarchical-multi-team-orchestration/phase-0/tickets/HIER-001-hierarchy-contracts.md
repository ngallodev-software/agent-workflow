# HIER-001 — independent review of hierarchy and team-delegation contracts

## Current state

Implementation is complete and in review. The established `agent_workflow.hierarchy` package provides schema-validated fixed-depth contracts, canonical digests, capability/budget narrowing, normalized scope validation, immutable read-only installation, idempotent verification, and installed-wheel evidence.

## Review requirements

Verify root/team/worker is the only supported authority depth; team contracts cannot widen models, commands, permissions, executors, classes, routes, budgets, or filesystem scope; hierarchy/team identities and digests are exact; undeclared teams and mismatched leads fail; contract files are regular, single-link, read-only files; symlink, traversal, tamper, conflicting reinstall, and partial contract-set cases fail closed.

## Non-targets

No journals, receipts, tmux mutation, team scheduler, external terminal adapter, team runtime, recursion, or multi-host transport. Correct demonstrated HIER-001 defects only; do not add later-phase behavior during review.

## Acceptance

Accept the HIER-001 portion of HIER-GATE-0 only when focused invariants and the installed-product contract-set journey pass and direct orchestration behavior remains unchanged.

## Writable paths

Review evidence and, only for a demonstrated HIER-001 defect, `src/agent_workflow/hierarchy/`, the two hierarchy contract schemas, focused tests, and directly related documentation.

## Tests

Run the hierarchy contract invariant suite, the installed-product hierarchy contract journey, prompt-pack validation, release-asset auditing, and direct-orchestration regression coverage appropriate to any corrective change.

## Stop conditions

Stop and reject the gate rather than weakening digest checks, capability narrowing, no-follow/read-only installation, fixed depth, exact team identity, or direct-orchestration compatibility. Do not implement HIER-002 or later-phase behavior in a HIER-001 corrective ticket.
