# Implementation task: repair prompt-pack continuation blockers

## Scope

Repair the confirmed Agent-Workflow defects documented in
`AGENT_WORKFLOW_PROMPT_PACK_CONTINUATION_INCIDENT_20260829.md`:

1. A generated external `run.sh` must start a worker in every advertised mode;
   it must not pass unsupported arguments to `agent_workflow.runner`.
2. Completion validation must reject a completed implementation handoff that
   claims changed files but binds identical base and head revisions.
3. Restart/retry of the persisted external `bridge` profile must be possible,
   or preparation must fail earlier with an actionable error instead of
   advertising a restart that cannot run.

## Guardrails

- Preserve immutable Agent Run evidence and source/worktree provenance.
- Do not weaken external-host control boundaries or make bindings implicit
  execution authority.
- Do not modify OSINT Suite source or its existing worktree.
- Keep the change minimal; do not redesign the workflow system.

## Acceptance

- A generated external launch contract is executable in its documented mode and
  produces durable start evidence.
- A completed handoff with nonempty `changed_files` and identical base/head
  revisions is rejected.
- A retry for a persisted external profile either creates valid lineage or
  emits a clear, preflight error with no misleading safe restart action.
- Focused regression tests pass, as does `git diff --check`.

## Suggested tests

- Existing external-run, runner, restart, and completion-collection tests.
- One focused regression test per acceptance point; reuse fixtures/helpers.

## Completion

Commit only the scoped implementation and test changes. Publish a structured,
revision-bound completion handoff with exact commands and unresolved items.
