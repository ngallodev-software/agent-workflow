---
schema: agent-workflow/ticket-completion/v1
pack_id: chatgpt-workflow-completion-next
phase: phase-1
ticket: WF-10
session: local-chatgpt-execution-20260724
result: completed
base_revision: c219eb7
head_revision: 2ed7b8e
---

# WF-10 Ticket Completion Report

## Source baseline

| Repository/component | Revision before | Revision after | Dirty before |
|---|---|---|---|
| agent-workflow | `c219eb7` | `2ed7b8e` | yes; source archive contained intentional workflow-preparation changes |

## Scope delivered

Implemented receipt-backed approval gates over the canonical lifecycle receipt directory. The original delegated WF-10 commit was not accepted because it followed a mutable receipt path from `status.json`; this completion replaces that authority with contiguous regular-file/read-only chain reconstruction and also hardens lifecycle receipt creation to derive completion, tier, executor identity, and final-receipt digest from sealed terminal evidence.

## Files changed

- `src/agent_workflow/approval.py`, `src/agent_workflow/lifecycle.py`, `src/agent_workflow/scheduler.py`
- `tests/test_approval.py`, `tests/test_lifecycle.py`
- workflow/architecture/security documentation

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| Accepted and rejected paths are distinct | pass | scheduler transitions approval nodes from canonical accepted/rejected dispositions |
| Mutable approval state is not authoritative | pass | status-projection tamper test plus direct canonical receipt reconstruction |
| Tampered, unrelated, copied, omitted, duplicated, symlinked, writable, or noncontiguous receipts fail closed | pass | `tests/test_approval.py` |
| Downstream eligibility follows durable evidence | pass | scheduler approval/dependency tests |

## Tests and validation

`PYTHONPATH=src python3 -m pytest -q tests/test_lifecycle.py tests/test_approval.py tests/test_workflow_receipt.py` — 17 passed, 4 subtests passed.

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
