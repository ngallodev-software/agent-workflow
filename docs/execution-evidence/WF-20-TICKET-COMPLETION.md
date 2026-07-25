---
schema: agent-workflow/ticket-completion/v1
pack_id: chatgpt-workflow-completion-next
phase: phase-2
ticket: WF-20
session: local-chatgpt-execution-20260724
result: completed
base_revision: c219eb7
head_revision: 2ed7b8e
---

# WF-20 Ticket Completion Report

## Source baseline

| Repository/component | Revision before | Revision after | Dirty before |
|---|---|---|---|
| agent-workflow | `c219eb7` | `2ed7b8e` | yes; source archive contained intentional workflow-preparation changes |

## Scope delivered

Implemented only the three authorized deterministic graph-template expansions: pipeline, bounded parallel review with fan-in, and implementation followed by independent review. Expansion returns the same canonical workflow snapshot contract used by hand-authored workflows.

## Files changed

- `src/agent_workflow/workflow_templates.py`
- workflow template CLI parsing/help
- `tests/test_workflow_templates.py`
- command reference and workflow man page

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| All three authorized shapes | pass | each topology has structural assertions |
| Deterministic canonical expansion | pass | repeated expansion is byte-equivalent after canonical serialization |
| Invalid parameters fail closed | pass | identifiers, counts, and required fields tested |
| No methodology/persona catalog | pass | implementation exposes no extra template registry |

## Tests and validation

`PYTHONPATH=src python3 -m pytest -q tests/test_workflow_templates.py tests/test_cli_parsing.py` — focused template/CLI coverage passed.

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
