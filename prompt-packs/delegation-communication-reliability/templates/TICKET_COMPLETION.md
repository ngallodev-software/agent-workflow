---
schema: agent-workflow/ticket-completion/v1
pack_id: "delegation-communication-reliability"
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
| | | | |

## Scope delivered

Commit implementation, test, and documentation changes before recording a
completed handoff. The machine sidecar must use schema
`agent-workflow/completion/v1`, set `base_revision` to the launch revision and
`head_revision` to the exact post-commit `git rev-parse HEAD`, and use an
absolute path in every command `cwd`. Use only `pass`, `fail`, or `not_verified`
criterion results; a completed result has `unresolved: []`.

Describe only the implemented behavior. Placeholder text is invalid.

## Files changed and non-targets

```text
<git diff --name-status output>
```

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| | pass/fail/not verified | command, exit code, or artifact |

## Communication evidence

Record progress/ack/steer message IDs, correlation IDs, delivery/application or
rejection outcomes, and any unavailable adapter. Terminal text is not proof.

Reviewer runs must also publish a schema-valid completion sidecar with the
review commands, exit codes, and evidence actually collected. Do not treat a
Markdown report or terminal capture as a substitute.

## Tests and validation

| Command | Exit code | Contract or failure protected |
|---|---:|---|
| | | |

## Unresolved issues or source contradictions

Preserve failed, skipped, unavailable, and rejected evidence.

## No-drift declaration

- [ ] No files outside writable scope changed.
- [ ] No placeholder completion claims remain.
- [ ] No live target collection was performed.
- [ ] No terminal/TUI output was treated as delivery proof.
- [ ] Documentation claims were checked against current source.
