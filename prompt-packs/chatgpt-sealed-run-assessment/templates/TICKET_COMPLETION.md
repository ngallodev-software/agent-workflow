---
schema: agent-workflow/ticket-completion/v1
pack_id: "chatgpt-sealed-run-assessment"
phase: ""
ticket: ""
session: ""
result: "completed|partial|failed|blocked"
base_revision: ""
head_revision: ""
---

# Ticket Completion Report

## Evidence disposition

| Evidence class | Present, missing, contradictory, or not comparable | Artifact path/hash | Notes |
|---|---|---|---|
| Completion validity | | | |
| Lifecycle sealing | | | |
| Evaluation plan | | | |
| Evaluation scores/report/collection | | | |
| Ledger rows | | | |
| Phase acceptance | | | |

## Scope delivered

Describe only the evaluation-system or test-design changes actually made.

## Files changed

```text
<git diff --name-status output>
```

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| Evidence gaps remain explicit | pass/fail/not verified | command/file |
| No score or provider usage was invented | pass/fail/not verified | command/file |
| Future tests are strict and backlog-linked | pass/fail/not verified | command/file |
| Planned runtime work was not implemented | pass/fail/not verified | command/file |

## Tests and validation

| Command | Exit code | Contract or failure protected |
|---|---:|---|
| | | |

## Unresolved issues

Record missing score sets, unavailable collectors, environment limits, and any evidence that cannot be compared.

## No-drift declaration

- [ ] No planned HARD/MSG runtime feature was implemented.
- [ ] No unavailable score, provider usage, or phase acceptance was fabricated.
- [ ] Every future test is marked `xfail(strict=True)` until its implementation and acceptance prerequisites exist.
- [ ] Changed files stayed inside the ticket writable scope.
