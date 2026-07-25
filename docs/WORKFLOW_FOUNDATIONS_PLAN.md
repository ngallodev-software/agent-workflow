# Workflow foundations: implemented architecture and remaining evolution

**Status:** WF-001, WF-002, WF-00, WF-01, WF-02, WF-10, WF-11, WF-12, WF-20, WF-21, and WF-22 completed in release 0.2.0; authority and replay hardening completed in 0.2.1.

This document records the implemented boundary. `BACKLOG.md` remains the authority for unfinished work.

## Implemented foundation

### Dependency graph validation

Prompt-pack dependencies are validated across phases as a directed acyclic graph. Unknown, malformed, self, duplicate, and cyclic references fail validation before execution.

### Structured task result contracts

Tickets may declare a pack-local JSON Schema. The runner performs bounded regular-file reads of `result.json`, validates it, writes a collection receipt, and seals accepted result evidence. Result contracts do not create a scheduler or arbitrary file channel.

### Workflow snapshot and replay

A canonical snapshot defines workflow ID, pack provenance, nodes, dependencies, task/approval kind, launch/routing metadata, retry policy, and optional input bindings. Start stores that snapshot as a regular read-only file. Duplicate node, dependency, and task-session identifiers fail before execution. Append-only events record node transitions and bindings; existing journals are schema/sequence validated before append and read under a shared lock. Status/run files are deterministic projections rebuilt and refreshed from the snapshot and contiguous journal.

### Restart-safe scheduler

`SchedulerService` schedules only eligible nodes and subtracts already-running nodes from the parallelism budget. A callback return value cannot establish a child run: a matching regular provenance contract or valid sealed final receipt must exist before the node enters `running`. Restart/resume replays durable records, reconciles sealed terminal child outcomes, marks missing child footprints recoverable, propagates dependency failure, and reopens dependency-failed descendants when a prerequisite retry changes the dependency state. Attempts and retry lineage remain append-only.

### Receipt-backed approvals

Approval nodes reference a subject task. They complete only when the subject has a valid canonical accepted lifecycle receipt chain for the sealed child run and exact completion revision. Lifecycle receipt creation and workflow approval reconstruction derive authority from sealed terminal artifacts and ignore mutable `status.json` state, identity, tier, digest, and receipt pointers. Rejection or tampering fails the gate and propagates dependency failure.

### Bounded result binding

A task may bind named inputs from completed ancestor task results with strict RFC 6901 JSON Pointers. The source result and collection must be sealed by a canonical final receipt. Required/missing behavior, per-value size, total size, ancestry, and unsafe file types are enforced. Values are copied into a read-only binding snapshot and sealed child provenance; children never read arbitrary predecessor files dynamically.

### Aggregate workflow receipts

A terminal workflow can be sealed into a read-only receipt committing to the normalized/file snapshot digests, event journal digest/count, exact node set and states, terminal reasons, attempts/retry lineage, binding history and input digests, child final receipt/completion digests, approval digests, and workflow disposition. Verification rebuilds the value from current durable evidence and requires exact equality.

### Authorized templates

Only these deterministic expansion templates exist:

1. `pipeline`
2. `parallel-review-fan-in`
3. `implementation-independent-review`

Expansion produces the same canonical snapshot schema as hand-authored workflows.

### Explainable routing advice

Routing advice deterministically recommends exploratory, review, or implementation class from bounded node metadata and records stable explanation codes. It is advisory. Existing configured class/executor/model allowlists, interactivity, permission arguments, and no-go policy remain the enforcement authority. Recommendation/enforced selection disagreements are explicit.

## Non-targets retained

- no alternate executor or MCP-specific scheduler;
- no online learning, vector memory, or autonomous model selection;
- no arbitrary expression language or file reads in result binding;
- no approval inferred from logs, status pointers, or process success;
- no automatic merge or destructive workflow cleanup;
- no multi-host broker until a measured need and explicit decision.

## CLI

```text
agent-workflow workflow validate SNAPSHOT
agent-workflow workflow template TEMPLATE SPEC --output SNAPSHOT
agent-workflow workflow start RUN_DIR SNAPSHOT
agent-workflow workflow status RUN_DIR SNAPSHOT
agent-workflow workflow resume RUN_DIR SNAPSHOT
agent-workflow workflow seal RUN_DIR SNAPSHOT
agent-workflow workflow verify RUN_DIR SNAPSHOT
```

The supplied snapshot must match the stored started snapshot for every operation after start.

## Evidence and tests

Schemas live in `schemas/workflow-*.schema.json`, `schemas/routing-advice.schema.json`, and `schemas/workflow-input-bindings.schema.json`. Focused tests live in `tests/test_workflow.py`, `tests/test_approval.py`, `tests/test_workflow_receipt.py`, `tests/test_workflow_templates.py`, and `tests/test_routing.py`.

See [Repository Chart Pack](diagrams/REPOSITORY_CHART_PACK.md) for state, authority, binding, approval, and receipt diagrams.

## Remaining evolution

- `MCP-003`: expose safe workflow/session/message mutations through shared services with durable idempotency.
- `BKL-004`: run controlled real-executor benchmark cohorts.
- `WF-006`: consider evidence-derived routing recommendations only after comparable cohort evidence exists.
