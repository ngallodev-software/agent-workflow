# Workflow Foundations Plan

## Decision

Extend the existing prompt-pack and durable-run model rather than adding a second orchestration system. The repository keeps its current focus: provider-neutral coding-agent launches, isolated worktrees, explicit model policy, durable control records, and immutable evidence.

The useful ideas adopted are limited to executable dependency graphs, structured task outputs, approval-gated progression, reusable graph templates, and explainable routing advice. No external orchestration runtime, vector memory, self-training, agent persona catalog, federation layer, simulated consensus, invisible hooks, or project-local mutable authority is introduced.

## Invariants

1. `agent-workflow launch` remains the only durable execution boundary.
2. Prompt-pack manifests remain declarative, reviewable inputs.
3. Append-only run evidence and sealed receipts remain authoritative.
4. A scheduler may decide when a task is eligible; it may not spawn an executor except through the existing launch service.
5. Routing recommendations are advisory. Existing class, executor, model allowlist, and no-go enforcement wins.
6. Structured results are untrusted until bounded, schema-validated, copied into the run directory, and sealed.
7. No arbitrary workflow code or expressions are executed.

## Implemented in this change set

### Dependency-graph validation

Prompt-pack validation now rejects:

- unknown dependency IDs;
- self-dependencies;
- dependency cycles;
- malformed dependency lists.

Dependencies may cross phase boundaries. This turns the existing `dependencies` field into a reliable graph contract without yet adding an autonomous scheduler.

### Structured task-result contracts

A task may declare:

```yaml
result_contract:
  schema: contracts/audit-result.schema.json
  required: true
```

For such a ticket, the launch context instructs the child to atomically write `AGENT_WORKFLOW_HANDOFF_DIR/result.json`. The runner:

- resolves the schema inside the prompt-pack root;
- rejects escaping or symlinked schema paths;
- reads a bounded, non-symlink result file;
- validates it using JSON Schema 2020-12;
- stores the accepted value as `result.json` in the run directory;
- writes `collections/task-result.json`;
- seals both artifacts when present.

The generic `agent-workflow/task-result/v1` schema is provided for simple tasks, while prompt packs may carry narrower task-specific schemas.

## Remaining minimal architecture

### 1. Dependency scheduler

Add a small workflow-run service over an already validated prompt pack.

Required behavior:

- create an immutable workflow snapshot from pack manifest and checksum;
- mark tasks `blocked`, `eligible`, `running`, or terminal from dependencies and child receipts;
- launch eligible tasks only through the existing launch domain service;
- enforce configured maximum parallelism;
- stop dependent tasks after failed, blocked, or rejected prerequisites according to explicit policy;
- reconstruct state from the snapshot and append-only workflow events after restart;
- bind each workflow node to exactly one current run and retain retry lineage.

Do not add arbitrary JavaScript/Python workflow execution, loops, timers, distributed queues, or a second task database.

### 2. Approval gates

Represent an approval gate as a declarative node that becomes satisfied only when a valid lifecycle/review receipt references the expected child final receipt digest.

Required behavior:

- no mutable boolean approval flag as authority;
- no implicit approval from task completion;
- explicit accepted/rejected disposition;
- downstream eligibility derived from durable receipt evidence.

### 3. Structured output binding

Allow a downstream task to bind selected fields from a validated predecessor result.

Constraints:

- JSON Pointer only;
- bounded serialized value size;
- no template expression language;
- snapshot the resolved inputs into the child run provenance;
- fail closed when required fields are absent.

### 4. Reusable workflow templates

Templates should be ordinary validated YAML fragments for a small set of recurring shapes: pipeline, parallel review with fan-in, and implementation followed by independent review. Templates must expand to the same workflow schema before execution.

Do not create named agent personas or broad methodology catalogs.

### 5. Explainable routing advice

Add a deterministic advisory function that recommends an existing agent class, executor, model, and interactive mode from declared task metadata and measured historical cohorts.

First release requirements:

- fixed rules only;
- stable explanation codes;
- recommendation recorded separately from enforced selection;
- policy rejection recorded when recommendation is disallowed;
- no online training, embeddings, vector database, or silent config mutation.

Evidence-derived statistical recommendations are a later enhancement only after benchmark evidence tasks BKL-003 through BKL-005 are complete.

## Explicit non-targets

- external orchestration-runtime integration;
- replacing prompt packs;
- vector or graph memory;
- self-learning or model fine-tuning;
- large catalogs of named or specialized agent personas;
- consensus algorithms for local coding agents;
- multi-host federation;
- HTTP workflow control;
- automatic background hooks that launch or reroute agents;
- arbitrary workflow scripts or condition expressions;
- hidden mutable state inside target repositories.

## Delivery order

1. Finish scheduler state model and restart-safe event journal.
2. Add approval nodes and aggregate workflow receipts.
3. Add JSON Pointer result binding.
4. Add only the three justified template shapes.
5. Add deterministic routing explanations.
6. Reassess statistical routing only after sealed benchmark evidence exists.

The linked prompt pack contains the executable remaining work.
