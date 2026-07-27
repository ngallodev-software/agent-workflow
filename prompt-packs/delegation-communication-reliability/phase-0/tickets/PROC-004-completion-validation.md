# PROC-004 — substantive completion handoff validation

**Backlog:** [`PROC-004`](../../../../docs/BACKLOG.md)

## Goal

Prevent a default or placeholder completion template from being accepted as a
real implementation result.

## Writable paths

- `src/agent_workflow/runner.py`, completion/collection validation services,
  and the existing completion schema only where required.
- Focused installed completion journey and compact required-field matrix.

## Acceptance

- Completion validation rejects placeholder-only reports, missing identity,
  absent revision/scope data, missing command exit codes, or absent acceptance
  evidence.
- Valid reports retain failed/skipped/unavailable commands and unresolved
  contradictions rather than converting them to success.
- Completion collection, final receipt, evaluation evidence, and ledger binding
  remain separate checks; one cannot imply another.
- A failed validation is durably reported and does not silently become a
  completed run.
- Add or update a focused installed-product test and report its exit code.

## Non-targets and stop conditions

Do not infer scores, provider usage, cost, or lifecycle acceptance from prose.
Do not redesign the final-receipt schema outside the necessary compatibility
revision. Use `templates/TICKET_COMPLETION.md`.
