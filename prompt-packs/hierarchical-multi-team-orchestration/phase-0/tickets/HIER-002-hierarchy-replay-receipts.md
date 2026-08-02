# HIER-002 — independent review of journals, replay, and receipts

## Current state

Implementation is complete and in review. `agent_workflow.hierarchy` provides append-only fsynced journals with contiguous local sequences, exact journal identities, source-journal/message idempotency, no-follow single-link file checks, strict truncation/tamper/duplicate/mixed-identity rejection, and deterministic contract-plus-journal replay. It also provides immutable team and root receipts with strict schemas and installed-wheel evidence.

Team receipts bind the exact installed delegation contract, complete explicitly declared journals, every contract-required worker output, required independent review evidence, unresolved issues, scope deviations, exact budget usage, and terminal disposition. Root receipts bind the hierarchy and contract set, root journals, the exact declared team set and team receipts, cross-team bindings, required approvals, unresolved issues, and global outcome. Receipt and evidence files must be single-link, read-only regular files; later journal appends or evidence mutation invalidate verification.

## Review requirements

- Verify journal ordering remains local rather than inventing a global sequence.
- Verify team journals cannot smuggle another team's identity and root journals cannot reference undeclared teams.
- Verify workers_started equals the exact sealed worker set, usage cannot exceed delegated budgets, and every declared required output is present.
- Verify required review and approval kinds cannot be omitted.
- Verify team-owned, review, binding, and approval evidence paths cannot be ambiguously reused.
- Verify receipt self-digests, exact contract paths, file digests, sizes, immutable modes, and team/root identities.
- Attack later appends, truncation, receipt/evidence tamper, missing evidence, duplicate descriptors, path traversal, symlinks, hard links, writable files, mixed team identity, and partial team sets.

## Non-targets

No tmux mutation, team-lead runtime, hierarchical transport, root scheduler, arbitrary recursion, daemon, or multi-host behavior. Correct demonstrated HIER-002 defects only; do not begin HIER-003.

## Writable paths

Review evidence and, only for a demonstrated HIER-002 defect, `src/agent_workflow/hierarchy/`, hierarchy authority schemas, focused tests, and directly related Phase 0 documentation.

## Tests

Run all hierarchy contract, journal/replay, and receipt invariants; all three installed-product hierarchy journeys; prompt-pack validation; release-asset auditing; and direct-orchestration regression coverage appropriate to any corrective change.

## Acceptance criteria

Accept the HIER-002 portion of HIER-GATE-0 only when deterministic replay remains unchanged, team and root receipts verify all declared evidence from installed-product code, every mutation or later append invalidates the appropriate receipt, and no runtime/tmux authority is introduced early.

## Stop conditions

Stop and reject the gate rather than weakening immutable authority, accepting mutable or partial evidence, inferring completion from process/tmux state, allowing cross-team identity drift, or implementing later-phase behavior.
