# Orchestrator messaging and regression evals

## Purpose

Research, implement, and independently verify durable local parent/child
communication plus two receipt-backed regression evals. The source checkout is
authoritative; `docs/ORCHESTRATOR_MESSAGING_AND_EVALS_PLAN.md` is the decision
record.

## Source baseline

`/lump/apps/agent-workflow`, `master`, release `0.1.3`, reviewed 2026-07-23.

## Phase map

| Phase | Objective | Complexity | Exit dependency |
|---|---|---|---|
| 0 | Research existing transports and freeze contracts | Low | Primary sources and a threat model. |
| 1 | Durable messages, wait, and bounded steering | Medium | Phase 0 contract decision. |
| 2 | Metrics and deterministic JSON eval | Medium | Phase 1 sealed control evidence. |
| 3 | Pinned visual child-handoff eval | High | Phase 2 metrics/report contract. |

## Universal delegation rules

- Execute every ticket in a fresh named terminal session.
- Use an isolated worktree unless the ticket is explicitly read-only.
- Read required references and current source before editing.
- Follow writable-path restrictions.
- Do not add tests without naming the contract or failure they protect.
- Stop when source contradicts the ticket in a way that could overwrite newer architecture.
- Produce a ticket completion report and preserve all command output.
- Never claim generic live steering for a one-shot executor without a verified
  adapter and acknowledgement record.

## How to execute

See `EXECUTION_PROTOCOL.md`, `DELEGATION_RUNBOOK.md`, and each phase README.
