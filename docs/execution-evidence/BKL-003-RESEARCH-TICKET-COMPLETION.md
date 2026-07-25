---
schema: agent-workflow/ticket-completion/v1
pack_id: chatgpt-workflow-completion-next
phase: phase-3
ticket: BKL-003-RESEARCH
session: local-chatgpt-execution-20260724
result: completed
base_revision: c219eb7
head_revision: 2ed7b8e
---

# BKL-003-RESEARCH Ticket Completion Report

## Source baseline

| Repository/component | Revision before | Revision after | Dirty before |
|---|---|---|---|
| agent-workflow | `c219eb7` | `2ed7b8e` | yes; source archive contained intentional workflow-preparation changes |

## Scope delivered

Completed a primary-source research memo for provider-neutral usage evidence and current supported executor event surfaces. Facts, implementation inferences, unknown/null behavior, cached-token variants, currency/catalog rules, duplicate/retry semantics, and real-executor cohort exclusions are separated explicitly.

## Files changed

- `docs/PROVIDER_EVIDENCE_RESEARCH.md`
- supporting architecture/security/MCP research documents
- implementation checklist embodied in schemas/tests

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| Primary official sources recorded with access dates | pass | OpenAI, Anthropic, and MCP official documentation references |
| Delta/cumulative/terminal envelope specified | pass | memo and schema design |
| Cached/reasoning/cost variants and double-counting risks mapped | pass | provider mapping table and invalid-mode rules |
| Unknowns/open cohort questions are explicit | pass | BKL-004 remains open; no paid-provider result claimed |
| No runtime change in research ticket | pass | research memo is separable from subsequent implementation commit scope |

## Tests and validation

Read-only source/reference validation and prompt-pack validation passed. No fresh external research-review executor was available; this limitation is recorded rather than replaced with a fabricated receipt.

## Tests intentionally not added

No broad snapshot suite, local-user-file assertions, live paid-provider calls, or duplicate CLI-help tests were added. Coverage targets authority, replay, schema, tamper, size, and accounting seams.

## Migration and compatibility notes

Release 0.2.0 adds versioned optional fields/artifacts without rewriting older sealed runs. New runs record retry lineage in provenance. Workflow snapshots are immutable once started; substituted snapshots are rejected. MCP mutation tools remain unimplemented.

## Unresolved issues or source contradictions

A fresh independent Codex/Claude executable was unavailable in this environment. Historical independent review evidence exists for WF-00 through WF-02 and identified the original WF-10 flaw; the corrected cumulative tree was instead subjected to isolated critical review and executable tamper tests. BKL-004 real-executor cohorts remain operator-run.

## No-drift declaration

- [x] No unrelated external-project behavior was added.
- [x] No superfluous test class was added.
- [x] No live target collection or paid-provider cohort was performed.
- [x] No alternate scheduler/launcher, broker, daemon, database, or HTTP service was added.
- [x] Current documentation claims were checked against source and the live parser.
