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

## Required machine completion sidecar

Before `agent task-complete`, write
`$AGENT_WORKFLOW_HANDOFF_DIR/completion.json`. The Markdown report is not a
substitute. Its command and criterion records must use the authoritative shape:

```json
{
  "schema": "agent-workflow/completion/v1",
  "session_id": "<session>",
  "ticket_id": "<ticket-or-null>",
  "pack_id": "<pack-or-null>",
  "result": "completed",
  "base_revision": "<git-sha>",
  "head_revision": "<git-sha>",
  "changed_files": ["src/example.py"],
  "criteria": [{"id": "criterion", "result": "pass", "evidence": ["test output"]}],
  "commands": [{"argv": ["pytest", "-q"], "cwd": "/absolute/worktree", "exit_code": 0, "receipt": "1 passed"}],
  "unresolved": [],
  "usage": null
}
```

`task-complete` rejects an absent, schema-invalid, or non-substantive sidecar
and leaves the assignment busy so it can be corrected.

Implementation agents must commit source, test, and documentation changes before
writing a completed sidecar. Set `base_revision` to the launch source revision
and `head_revision` to the exact post-commit `git rev-parse HEAD`; collection
rejects completed evidence that does not bind to those revisions. Every command
must use an absolute `cwd`, every criterion result must be `pass`, `fail`, or
`not_verified`, and `result: completed` requires `unresolved: []`.

Reviewers must provide the same schema-valid sidecar evidence for the review
run, including the exact commands and exit codes they actually ran. A Markdown
report is supplementary and never replaces `completion.json`.

For a `completed` result, `unresolved` must be empty. Do not list normal
host-owned merge, review, acceptance, release, or pane-closure work as an
unresolved item; report those as next steps in the Markdown handoff instead.

## Source baseline

| Repository/component | Revision before | Revision after | Dirty before |
|---|---|---|---|

## Worktree index and discovery

| Field | Value |
|---|---|
| Exact worktree root | |
| Index project identity | |
| Index mode | `full` |
| Index status | |
| Nodes / edges | |
| Artifact or digest | |
| Limitations or fallback | |

The index must belong to this worktree. If the optional codebase-memory service
was unavailable, say so and do not claim graph-backed structural analysis.

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
