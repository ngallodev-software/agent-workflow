# codex-luna-effort-policy

## Purpose

Enforce a conservative default Codex policy: automatic agent-workflow
selection may use only `gpt-5.6-luna`, at one of `low`, `medium`, or `high`
reasoning effort. Larger work must be decomposed instead of selecting a more
capable automatic model. Manually supplied non-Codex executor commands remain
an operator choice and are not an automatic-routing escape hatch.

## Source baseline

`/lump/apps/agent-workflow`, `master` at `7970152` on 2026-07-30. The
checked-out source remains authoritative when it differs from included
references.

## Phase map

| Phase | Objective | Complexity | Exit dependency |
|---|---|---|---|
| 0 | Enforce Luna-only model and effort policy | B | Independent gate review |

## Universal delegation rules

- Execute every ticket in a fresh named terminal session.
- Use an isolated worktree unless the ticket is explicitly read-only.
- Read required references and current source before editing.
- Follow writable-path restrictions.
- Do not add tests without naming the contract or failure they protect.
- Stop when source contradicts the ticket in a way that could overwrite newer architecture.
- Produce a ticket completion report and preserve all command output.

## How to execute

See `EXECUTION_PROTOCOL.md`, `DELEGATION_RUNBOOK.md`, and each phase README.
