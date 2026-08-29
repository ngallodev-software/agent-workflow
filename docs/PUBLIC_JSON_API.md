# Stable Public JSON Contracts

Agent-Workflow integrations should use the CLI's `--json` output rather than import private Python modules or parse human-readable prose. These contracts are host-neutral views over existing durable authorities; they do not create a second lifecycle, messaging, review, evaluation, provenance, or benchmark authority.

## Common contract rule

For the commands below, `--json` emits one JSON value to stdout and errors remain normal CLI failures. Fields documented here are the supported integration surface for the v1 contract. Additive fields may appear within a schema version; consumers should ignore unknown fields. A schema identifier changes when a breaking structural change is required.

Normal agent command cards remain role-scoped and intentionally do not include integration/operator-only inspection commands merely because they are public structured interfaces.

## Delegation and Agent Run state

- `agent-workflow --json delegate ...` — compact deterministic delegation result. This remains the preferred common path.
- External prepared delegation results include a structured `launch_contract`
  with the exact runner argv, worktree, and bind/start command templates. The
  runner starts the prepared external Worker; `start-external` records its
  binding- and generation-checked lifecycle transition.
- `agent-workflow --json agent-run prepare ...` — public Agent Run preparation view; private provider/model routing and state-root paths are excluded.
- `agent-workflow --json agent-run status AGENT_RUN_ID` — public lifecycle/health view; private provider/model identity is excluded.
- `agent-workflow --json agent context AGENT_RUN_ID` — durable worker context using `agent-workflow/agent-context/v1`.

## Durable messages and acknowledgement state

`agent-workflow --json agent-run message-state AGENT_RUN_ID` emits `agent-workflow/public-message-state/v1`.

The response contains the latest visible message sequence, whether the bounded view was truncated, all visible steering requests, and the subset still pending acknowledgement. Each steering item reports transport outcome separately from acknowledgement. A transport outcome of `delivered` is not acknowledgement and does not imply the Worker applied the request.

The view is derived from the existing `messages.jsonl` and steering-delivery journal. It does not write either authority.

## Completion, evaluation, review, and acceptance summary

`agent-workflow --json agent-run summary AGENT_RUN_ID` emits `agent-workflow/public-run-summary/v1`.

The response summarizes execution, assignment completion, collected completion validation, evaluation state/score when present, and the latest immutable review/acceptance disposition. Missing evidence is represented as absent/null rather than fabricated. The command does not perform evaluation, review, or acceptance.

## Restricted worktree/source/runtime provenance

`agent-workflow --json agent-run provenance AGENT_RUN_ID` emits `agent-workflow/operator-provenance-view/v1` and sets `restricted: true`.

This is an explicit operator/integration surface. It includes worktree/source provenance and may include the resolved executor/model identity needed for auditability and reproducibility. Do not inject this response into ordinary child/orchestrator context; the normal `prepare`, `status`, `delegate`, role, workflow, and peer-message contracts retain logical-role opacity.

## External Worker binding and delivery

- `agent-workflow --json agent-run external-binding AGENT_RUN_ID` — rebuildable host-neutral binding projection.
- `agent-workflow --json agent-run bind-external ...` — idempotent bind/rebind.
- `agent-workflow --json agent-run observe-external ...` — non-authoritative host observation.
- `agent-workflow --json agent-run unbind-external ...` — idempotent unbind.
- `agent-workflow --json agent-run pending-external-delivery ...` — generation-guarded pending durable steering for the active external Worker.
- `agent-workflow --json agent-run report-external-delivery ...` — append delivery-attempt evidence without acknowledging the steering request.

Binding and delivery observations remain operational data. They cannot complete, review, accept, or reject an Agent Run.

## Workflow status

`agent-workflow --json workflow status SNAPSHOT --run-dir RUN_DIR` is the stable workflow-level structured status surface. It remains a projection of workflow/scheduler authority rather than a parallel workflow state store.

## Benchmark status

When comparative benchmark capability is intentionally in use, `agent-workflow --json benchmark status RUN` is the structured benchmark status surface. Benchmark machinery is not part of the normal agent-facing command profile and should not be loaded or explained on common-path tasks.

## Compatibility boundary

External hosts and plugins should compose these CLI contracts. They should not import `agent_workflow.*` implementation modules, read mutable status files directly, infer lifecycle state from process state, scrape terminal output, or duplicate Agent-Workflow's durable authorities in a host-owned schema.
