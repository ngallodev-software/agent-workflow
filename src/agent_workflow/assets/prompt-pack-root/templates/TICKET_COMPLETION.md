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

## Worker completion protocol

The Markdown report is explanatory evidence only. **Do not author
`completion.json` manually.** Agent-Workflow generates the machine completion
sidecar from constrained worker operations.

Record criterion outcomes with exact parser-enforced values:

```bash
agent criterion AGENT-RUN-ID CRITERION-ID pass --evidence "what proves it"
agent criterion AGENT-RUN-ID RECEIPT-ID pass --evidence-file path/to/host-receipt.md
```

Record controlled-environment limitations separately from gating criteria:

```bash
agent limitation AGENT-RUN-ID live-fetch --evidence "controlled DNS unavailable"
agent limitation AGENT-RUN-ID browser-launch --evidence "Chromium spawn denied by sandbox"
```

Limitations are always `not_verified` and are non-gating. They preserve harness/network constraints without mislabeling them as source failures.

Run final verification through Agent-Workflow so command identity and exit code are observed rather than reported by the model:

```bash
agent verify AGENT-RUN-ID -- pytest -q
```

Finish once through the deterministic terminal operation:

```bash
agent complete AGENT-RUN-ID --result completed
```

Review workers may additionally provide one parser-constrained disposition:

```bash
agent complete AGENT-RUN-ID --result completed --review-disposition approved
agent complete AGENT-RUN-ID --result completed --review-disposition changes_requested \
  --unresolved "specific review finding"
```

Allowed criterion results are `pass`, `fail`, and `not_verified`. Allowed
execution results are `completed`, `partial`, `failed`, and `blocked`. Review
dispositions are `approved`, `changes_requested`, and `blocked`.

Agent-Workflow derives and validates the administrative fields: Agent Run,
ticket and pack identity; launch/base revision; current HEAD; changed files;
repository-closeout binding; schema shape; and completion consistency. The
runner owns collection, final lifecycle transition, and sealing after worker
exit. Completion is never canonical host acceptance.

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
| | pass/fail/not_verified | command/file |

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
