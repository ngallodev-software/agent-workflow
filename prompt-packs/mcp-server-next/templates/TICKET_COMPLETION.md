---
schema: agent-workflow/ticket-completion/v1
pack_id: ""
phase: ""
ticket: ""
session: ""
result: "completed|partial|failed|blocked"
base_revision: ""
head_revision: ""
---

# Ticket Completion Report

## Source baseline

| Repository/component | Revision before | Revision after | Dirty before |
|---|---|---|---|

## Scope delivered

Describe only what was actually changed.

## Files changed

```text
<git diff --name-status output>
```

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| | pass/fail/not verified | command/file |

## Tests and validation

| Command | Exit code | Contract or failure protected |
|---|---:|---|

## Tests intentionally not added

Explain why broader unit, snapshot, CLI-help, local-file, or live tests would be redundant or out of scope.

## Migration and compatibility notes

State migration behavior, rollback/recovery behavior, and intentionally unsupported legacy paths.

## Unresolved issues or source contradictions

Do not hide uncertainties.

## No-drift declaration

- [ ] No files outside writable scope changed.
- [ ] No superfluous tests were added.
- [ ] No live target collection was performed.
- [ ] No compatibility layer was added outside the ticket.
- [ ] Documentation claims were verified against current source before implementation.
