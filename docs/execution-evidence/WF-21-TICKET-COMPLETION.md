---
schema: agent-workflow/ticket-completion/v1
pack_id: chatgpt-workflow-completion-next
phase: phase-2
ticket: WF-21
session: local-chatgpt-execution-20260724
result: completed
base_revision: c219eb7
head_revision: 2ed7b8e
---

# WF-21 Ticket Completion Report

## Source baseline

| Repository/component | Revision before | Revision after | Dirty before |
|---|---|---|---|
| agent-workflow | `c219eb7` | `2ed7b8e` | yes; source archive contained intentional workflow-preparation changes |

## Scope delivered

Implemented deterministic pure routing advice over bounded task metadata. Advice recommends the existing exploratory/review/implementation classes and their configured executor/model/interactivity, while launch-time configuration and no-go policy remain authoritative.

## Files changed

- `src/agent_workflow/routing.py`
- `schemas/routing-advice.schema.json`
- scheduler records recommendation, enforced selection, actual selection, explanation codes, and disagreements
- `tests/test_routing.py`

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| Stable rule/explanation output | pass | deterministic repeated-call tests |
| Recommendation and enforcement remain separate | pass | disagreement fields tested |
| No-go policy fails closed | pass | all-no-go candidate test |
| No online learning, embeddings, or config mutation | pass | pure service; no persistence or alternate launcher |

## Tests and validation

`PYTHONPATH=src python3 -m pytest -q tests/test_routing.py tests/test_session_launch.py` — focused routing/policy coverage passed.

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
