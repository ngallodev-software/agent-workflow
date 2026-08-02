# MAINT-005 — review lifecycle enforcement

## Goal

Make acceptance-capable review runs record a trustworthy tier and produce
schema-valid completion criteria before their collections are sealed.

## Defect

Review runs can reach the ordinary acceptance command without a recorded tier,
and the generated completion template lets reviewers provide string criteria.
Both defects produce invalid or unacceptably incomplete review evidence after
otherwise substantive inspection.

## Required behavior

- An acceptance-capable review must require or deterministically derive an
  immutable launch tier.
- The generated review completion template and validation contract must make
  every criterion an object with its required identifier, result, and evidence;
  malformed string criteria must remain rejected before collection.
- Prove an installed tiered read-only review reaches valid collection, a sealed
  final receipt, `review`, and `accept`.
- Preserve rejection for missing tier and malformed criteria. Do not weaken
  implementation completion identity, authority, or normal acceptance gates.

## Scope

Review launch/collection validation, completion templates, focused installed
and invariant tests, and directly related protocol references only.

## Writable paths

`src/agent_workflow/sessions.py`, `src/agent_workflow/runner.py`, completion
templates and schemas, focused tests/fixtures, this Phase 0 manifest, and
directly related execution-protocol references only.

## Acceptance evidence

- Focused tests cover missing tier rejection, malformed string criteria
  rejection, and the successful tiered review-to-accept path.
- The installed product journey records a valid completion collection and
  final receipt before the host review and acceptance transitions.
- Pack validation and release-drift audit pass from the source checkout.

## Stop conditions

Stop and reject the change if it infers a tier from mutable child input,
accepts a reviewer-selected identity, treats terminal text as completion proof,
or bypasses immutable collection/receipt verification.
