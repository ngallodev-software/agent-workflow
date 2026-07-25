---
schema: agent-workflow/ticket-completion/v1
pack_id: chatgpt-workflow-completion-next
phase: phase-1
ticket: WF-12
session: local-chatgpt-execution-20260724
result: completed
base_revision: c219eb7
head_revision: 2ed7b8e
---

# WF-12 Ticket Completion Report

## Source baseline

| Repository/component | Revision before | Revision after | Dirty before |
|---|---|---|---|
| agent-workflow | `c219eb7` | `2ed7b8e` | yes; source archive contained intentional workflow-preparation changes |

## Scope delivered

Implemented terminal aggregate workflow receipts and verification. The receipt commits to the canonical normalized snapshot, snapshot file, append-only event journal, exact node set/states, retry/binding history, child final/completion digests, input bindings, and revalidated canonical approval evidence.

## Files changed

- `src/agent_workflow/workflow_receipt.py`, workflow service/CLI seal and verify paths
- `schemas/workflow-receipt.schema.json`
- `tests/test_workflow_receipt.py`

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| Snapshot and event-log digests | pass | receipt rebuild verifies both digests and event count |
| Exact node/run/child/approval evidence | pass | node set and evidence rebuilt from durable state |
| Substitution, omission, duplication, and partial workflows fail | pass | explicit negative tests |
| Post-seal approval tampering fails verification | pass | canonical lifecycle evidence is revalidated during rebuild |

## Tests and validation

`PYTHONPATH=src python3 -m pytest -q tests/test_workflow_receipt.py tests/test_workflow.py` — focused receipt/replay coverage passed.

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
