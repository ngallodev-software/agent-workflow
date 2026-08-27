# External Worker binding contract

External-worker binding is a **host-neutral operational projection** for an Agent Run prepared with `worker_mode=external`. It identifies which externally hosted Worker currently corresponds to the Agent Run without making the host a lifecycle authority.

The public projection schema is `agent-workflow/external-worker-binding/v1` and contains:

- `agent_run_id`;
- Agent-Workflow `worker_id`;
- opaque `external_runtime_type` and `external_worker_id`;
- monotonically increasing `generation`;
- `bound_at` and `last_observed_at`;
- `bound`.

The external runtime values are opaque strings. Core does not interpret provider/model identity from them and the contract does not require any host-specific schema fields.

The durable authority is the run-local append-only `external-worker-bindings.jsonl` journal. Current binding state is rebuilt from that journal; there is no independent mutable binding database to keep synchronized.

Public CLI operations are intentionally outside normal role-scoped command cards:

```text
agent-workflow --json agent-run bind-external AGENT_RUN_ID RUNTIME_TYPE EXTERNAL_WORKER_ID
agent-workflow --json agent-run external-binding AGENT_RUN_ID
agent-workflow --json agent-run observe-external AGENT_RUN_ID
agent-workflow --json agent-run unbind-external AGENT_RUN_ID
```

`bind-external` is idempotent for the already-active runtime/worker pair. Binding a different pair creates the next generation. `unbind-external` is idempotent when no binding is active. `observe-external` only advances `last_observed_at` for an active binding.

A host observation **must never** mark an Agent Run complete, reviewed, accepted, rejected, failed, or acknowledged. Completion/evaluation/review/acceptance and durable steering acknowledgement remain owned by their existing Agent-Workflow authorities.

This contract deliberately does not define terminal layout, process IDs, provider/model routing, window/session identity, or host-specific launch semantics. Optional hosts consume this contract rather than extending it.


## Delivery-adapter boundary

For an Agent Run prepared with `worker_mode=external`, durable parent-to-child
steering uses the host-neutral `external-host-v1` delivery adapter. Persisting
a steer request queues it for the external host rather than marking it
unsupported.

An active binding generation is required for both public delivery operations:

```text
agent-workflow --json agent-run pending-external-delivery AGENT_RUN_ID --generation GENERATION
agent-workflow --json agent-run report-external-delivery AGENT_RUN_ID MESSAGE_ID --generation GENERATION --attempt ATTEMPT --outcome delivered --reason REASON
```

`pending-external-delivery` is a read-only view over the authoritative durable
message log and steering-delivery journal. Fetching a message does not mark it
delivered, applied, or acknowledged. The result schema is
`agent-workflow/external-worker-pending-delivery/v1` and identifies the Agent
Run, Agent-Workflow Worker, active binding generation, immutable message
payload/digest, and current delivery evidence.

`report-external-delivery` records transport evidence in the existing
append-only steering-delivery journal. The caller supplies a positive attempt
number so replay of the same attempt is idempotent. The result schema is
`agent-workflow/external-worker-delivery-result/v1`. A `delivered` result means
only that the host reports successful transport; it does **not** create an
Agent Run acknowledgement. `failed` records a terminal transport failure for
that request.

A host must use the current binding generation. Requests from a stale or
unbound generation are rejected, preventing a replaced host Worker from
mutating current delivery evidence. The host remains unable to mark work
complete, reviewed, accepted, rejected, or otherwise transition Agent Run
lifecycle through this adapter.
