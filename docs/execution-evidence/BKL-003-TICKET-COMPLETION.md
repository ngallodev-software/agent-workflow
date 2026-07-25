---
schema: agent-workflow/ticket-completion/v1
pack_id: chatgpt-workflow-completion-next
phase: phase-3
ticket: BKL-003
session: local-chatgpt-execution-20260724
result: completed
base_revision: c219eb7
head_revision: 2ed7b8e
---

# BKL-003 Ticket Completion Report

## Source baseline

| Repository/component | Revision before | Revision after | Dirty before |
|---|---|---|---|
| agent-workflow | `c219eb7` | `2ed7b8e` | yes; source archive contained intentional workflow-preparation changes |

## Scope delivered

Implemented bounded raw provider stream preservation, event-level digests/sequences, explicit usage modes, provider adapters, sealed provider evidence, retry/error/control accounting, immutable trial evidence, and valid cohort comparison semantics.

## Files changed

- `src/agent_workflow/provider_evidence.py`, runner/provenance/metrics/receipt integration
- evaluation trial collection/comparison
- provider, trial, provenance, and metrics schemas
- provider/eval/runner/session tests

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| Raw bounded stream evidence is preserved before normalization | pass | 16 MiB max+1 capture, digest, byte count, completeness flag |
| Usage modes do not double-count | pass | terminal authority; mixed nonterminal modes invalidate fields |
| Duplicate/replayed events are idempotent | pass | event-digest deduplication tests |
| Unknown tokens/cost/currency remain null | pass | null tests and schema contracts |
| Provider billed and local estimate are distinct | pass | separate fields; currency/catalog comparison exclusions |
| Retry/re-steer/error and provenance digests are retained | pass | sealed provenance lineage, controls, metrics, and trial source hashes |
| Incomplete/inconsistent trials are rejected | pass | evaluation collection/comparison tests |

## Tests and validation

`PYTHONPATH=src python3 -m pytest -q tests/test_provider_evidence.py tests/test_metrics.py tests/test_eval_trials.py tests/test_eval_compare.py tests/test_runner_generation.py` — focused provider/evaluation/runner coverage passed.

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
