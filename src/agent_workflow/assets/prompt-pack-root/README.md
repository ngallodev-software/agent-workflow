# {{PACK_NAME}}

## Purpose

State the implementation outcome this pack is designed to produce.

## Source baseline

List repositories, branches/revisions, and the date the source was reviewed. The checked-out source remains authoritative when it differs from included references.

## Phase map

| Phase | Objective | Complexity | Exit dependency |
|---|---|---|---|
| 0 | | | |

## Universal delegation rules

- Execute every ticket in a fresh durable Agent Run.
- Use an isolated worktree unless the ticket is explicitly read-only.
- Read required references and current source before editing.
- Follow writable-path restrictions.
- Do not add tests without naming the contract or failure they protect.
- Stop when source contradicts the ticket in a way that could overwrite newer architecture.
- Produce a ticket completion report and preserve all command output.

## How to execute

`pack.yaml` is the single authoritative machine-readable workflow manifest for the pack. Phase directories contain prompts and explanatory material only.

See `EXECUTION_PROTOCOL.md`, `DELEGATION_RUNBOOK.md`, and each phase README.
