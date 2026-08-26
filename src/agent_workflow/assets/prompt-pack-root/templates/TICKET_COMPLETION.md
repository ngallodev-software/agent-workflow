---
schema: agent-workflow/ticket-completion/v1
pack_id: ""
phase: ""
ticket: ""
agent_run: ""
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
  "agent_run_id": "<agent-run>",
  "ticket_id": "<ticket-or-null>",
  "pack_id": "<pack-or-null>",
  "result": "completed",
  "review_disposition": "approved",
  "base_revision": "<git-sha>",
  "head_revision": "<git-sha>",
  "changed_files": ["src/example.py"],
  "criteria": [{"id": "criterion", "result": "pass", "evidence": ["test output"]}],
  "commands": [{"argv": ["pytest", "-q"], "cwd": "/absolute/worktree", "exit_code": 0, "receipt": "1 passed"}],
  "unresolved": [],
  "usage": null,
  "repository_closeout": {"path": "repository-closeout.json", "sha256": "<sha256-of-sidecar>"}
}
```

`task-complete` rejects an absent, schema-invalid, or non-substantive sidecar
and leaves the assignment busy so it can be corrected.

For `result: completed`, list only final verification commands that passed. Do
not include exploratory, setup, staging, or unrelated failed commands in the
machine sidecar. Preserve material failures in this Markdown report and use
`partial`, `failed`, or `blocked` when they leave unresolved work.

Implementation agents must commit source, test, and documentation changes before
writing a completed sidecar. Set `base_revision` to the launch source revision
and `head_revision` to the exact post-commit `git rev-parse HEAD`; collection
rejects completed evidence that does not bind to those revisions. Every command
must use an absolute `cwd`, every criterion result must be `pass`, `fail`, or
`not_verified`, and `result: completed` requires `unresolved: []`.

Reviewers must provide the same schema-valid sidecar evidence for the review
run, including the exact commands and exit codes they actually ran. Reviewers
must also set `review_disposition` to `approved`, `changes_requested`, or
`blocked`; this field is separate from the execution `result`. A completed
review may therefore use `result: completed` with
`review_disposition: changes_requested`, failed/not-verified review criteria,
and unresolved review findings. A Markdown report is supplementary and never
replaces `completion.json`.

When repository integration is part of closeout, run `agent-workflow worktree
closeout` and place its immutable receipt at
`$AGENT_WORKFLOW_HANDOFF_DIR/repository-closeout.json`. Bind that exact file in
`completion.json` with `repository_closeout.path` and `sha256`. Collection
rejects a mismatched digest, repository root, local HEAD, or internally
inconsistent committed/pushed/merged claim. Omit the field when repository
integration is not part of the ticket evidence.

Reviewers report an accept/reject recommendation only. `review`, `accept`,
`reject`, and `force-accept` mutate canonical lifecycle state and are executed
only by the host orchestrator, never from a sandboxed reviewer.

For a non-review `completed` result, `unresolved` must be empty. A completed
review with `review_disposition: changes_requested` may list substantive review
findings there. Do not list normal host-owned merge, review, acceptance,
release, host-presentation, or unrelated follow-on work as unresolved; report those as next steps instead.

## Source baseline

| Repository/component | Revision before | Revision after | Dirty before |
|---|---|---|---|

## Worktree index and discovery

| Field | Value |
|---|---|
| Exact worktree root | |
| Index project identity | |
| Index mode | `full` or `not_run` |
| Persistence | `non_persistent`, `external_cache`, `authorized_disposable`, or `not_run` |
| External artifact root | |
| Index status | |
| Nodes / edges | |
| Artifact or digest | |
| Dirty before / after digest | |
| Local artifact owner / bytes / tree digest | |
| Cleanup policy / size-limit result | |
| Limitations, residue, or fallback | |

The index must belong to this worktree and must not dirty it by default. If the
optional service was unavailable or could not index without unauthorized local
persistence, say so and do not claim graph-backed structural analysis. A child
must not request destructive cleanup approval; repository-local artifacts are
valid only when `.codebase-memory/` was pre-authorized as a disposable tree and
the host coordinator owns cleanup.

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
