# DEC-009 — Watcher-driven deterministic orchestrator progression

- **Status:** decided
- **Date:** 2026-09-18
- **Scope:** initial reactive orchestration core
- **Backlog owner:** `ORCH-REACT-001`

## Decision

Agent-Workflow will make the existing `orchestrator watch` process the long-running driver for deterministic workflow progression. It will not add a second daemon, require an always-running LLM turn, or make a host-specific wake transport part of core correctness.

The existing authorities remain unchanged:

1. child Agent Run journals and sealed evidence remain authoritative for child behavior and completion;
2. the orchestrator inbox remains a durable delivery projection, not lifecycle authority;
3. workflow snapshot/event evidence and `SchedulerService` remain authoritative for workflow reconciliation and launch;
4. review and acceptance remain separate evidence gates and are never synthesized by the reactor;
5. notification delivery is advisory and cannot authorize workflow transitions.

## Workflow association

The orchestrator registry already carries an optional `workflow_id`. The initial reactor needs one additional durable locator so it can reconcile exactly one intended workflow without scanning state directories.

Use an optional adjacent binding record under the orchestrator state directory rather than widening the registry's child identity model. The record should be equivalent to:

```json
{
  "schema": "agent-workflow/orchestrator-workflow-binding/v1",
  "orchestrator_id": "<orchestrator-id>",
  "workflow_id": "<workflow-id>",
  "workflow_run_dir": "<explicit run directory>",
  "snapshot_sha256": "<canonical workflow snapshot digest>",
  "bound_at": "<timestamp>",
  "identity_digest": "sha256:<digest>"
}
```

The exact filename is implementation-owned but must be fixed and documented. The binding is valid only when:

- the orchestrator registry exists and its `workflow_id` equals the binding `workflow_id`;
- `workflow_run_dir/workflow-snapshot.json` is a regular read-only canonical snapshot;
- the snapshot's `workflow_id` matches the binding;
- the canonical snapshot digest matches `snapshot_sha256`;
- any existing `workflow-run.json` projection identifies the same workflow and snapshot digest.

A registry with `workflow_id = null` remains a valid inbox-only registry and has no workflow binding. A workflow-aware registry without a valid binding may still replay/read inbox events but must not reconcile or schedule a workflow.

The binding path is a locator to existing workflow authority, not a new authority record. The reactor must reopen and validate the canonical snapshot/run evidence before any workflow effect.

## Reactor behavior

One bounded reactor cycle should:

1. replay/import newly durable child events through the existing orchestrator inbox path;
2. validate the optional workflow binding;
3. call existing workflow/scheduler reconciliation against the bound canonical snapshot;
4. allow `SchedulerService.launch_eligible()` to release and launch work when durable evidence already determines the transition;
5. persist bounded reaction/cursor evidence sufficient to make retries idempotent;
6. classify states with no already-authorized deterministic action as durable `attention_required`.

Routine `progress` and acknowledgements may update replay/cursor state but do not create lifecycle transitions or wake an LLM merely because they arrived.

## Delivery and restart semantics

Replay is at-least-once; workflow effects must remain exactly-once.

If a workflow transition or child launch commits and the watcher crashes before its consumer cursor/reaction evidence advances, the next cycle must reconstruct the committed effect from workflow/Agent Run authority and avoid a duplicate transition or child launch.

Durable reaction evidence should identify the source inbox event, workflow identity, resulting action category, stable reason code, and the authoritative effect/evidence references needed to recognize a previously committed reaction. It must not duplicate arbitrary worker transcript content.

## Existing watcher

`orchestrator_supervisor.watch()` is the only long-running process added to the happy path. After durable inbox replay it should invoke the reactor for registries with a valid workflow binding.

Bounded watcher polling is acceptable because durable journal replay remains the correctness mechanism. The product requirement is to remove LLM/manual polling as the clock, not to eliminate process polling.

The existing single-writer supervisor lease remains required. `poll_seconds` must either have truthful operational semantics or be removed/deprecated; a validated but unused public option is not acceptable.

## Attention and notification

When current structured evidence has no safe deterministic continuation, the reactor records bounded durable `attention_required` evidence.

Only after that evidence is durable may the existing watcher invoke its optional `notification_adapter` callback. Callback failure does not roll back inbox, reaction, workflow, scheduler, review, or acceptance state. No callback is required for core operation.

The callback payload stays bounded and pointer-like: stable attention/event identity, orchestrator identity, workflow identity when present, reason code, and sequence/cursor metadata sufficient for an embedding host to fetch authoritative detail.

## Explicitly deferred

This decision does **not** design or implement:

- Codex App Server wake/resume transport;
- another host-specific wake transport;
- a generalized notification transport/plugin framework;
- Typesafe AI decision augmentation or a generic AI decision-provider interface.

Those should be designed only after the deterministic watcher/reactor path is proven in real workflows.

## Required proof

Closeout for `ORCH-REACT-001` requires a real end-to-end idle-watcher journey:

1. start a workflow with node A running and dependent node B blocked;
2. start `orchestrator watch`;
3. after the watcher is already running, durably complete A through the normal child completion path;
4. issue no manual `react_once`, `workflow resume`, inbox import, status, or other orchestration tick;
5. observe the watcher replay the child event, reconcile A, release B, and launch B exactly once;
6. restart/replay the watcher and prove B is not launched a second time.

The proof must also cover invalid completion not advancing the dependency, inbox-only watch compatibility, durable attention before advisory notification, notification failure recovery, and preservation of separate completion/evaluation/review/acceptance gates.
