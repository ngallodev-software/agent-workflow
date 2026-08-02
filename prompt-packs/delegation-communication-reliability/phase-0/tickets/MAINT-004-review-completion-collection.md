# MAINT-004 — review completion collection identity

## Goal

Make a read-only review run seal a valid completion collection and final receipt
without weakening completion identity validation for implementation runs.

## Defect

Review launches currently omit `ticket_id` from the immutable launch contract,
while review children may include a review/ticket identifier in their completion
handoff. The collector then rejects a substantive review report as a ticket
mismatch. This blocked HIER-001, IDX-002, SUP-002, and PROC-004 phase evidence.

## Required behavior

- Define one canonical review ticket-identity rule at launch time.
- A child completion must either use the immutable launched review identity or
  omit it when the launch contract omits it; a mismatched supplied identity must
  remain rejected.
- Preserve immutable session ID, pack ID, revision, and completion schema checks.
- Add an installed-product review journey proving a clean read-only review seals
  a valid collection/final receipt; retain a negative mismatch case.

## Scope

Completion collection/launch validation, review launch handling, focused tests,
and directly related protocol/reference documentation only. No acceptance-policy
or implementation-run bypasses.

## Writable paths

`src/agent_workflow/runner.py`, `src/agent_workflow/sessions.py`, the launch
contract schemas, focused tests/fixtures, the Phase 0 manifest, and directly
related execution-protocol copies only.

## Stop conditions

Stop and reject the repair if it requires accepting a child-selected ticket,
weakening immutable session/pack/revision binding, or bypassing the ordinary
completion collector for review runs.
