# Herdr-Centered Agent-Workflow Overhaul

Status: proposed architecture and migration plan  
Planning branch: herdr-overhaul-bootstrap  
Source repository: ngallodev-software/agent-workflow  
Source line: 0.11.6 master  
Target repository working name: ngallodev-software/agent-workflow-herdr  
Date: 2026-09-22

## 1. Purpose

This document defines a clean-repository overhaul of Agent-Workflow around Herdr as the execution fabric.

The objective is not to port the existing implementation mechanically. The objective is to retain the parts of Agent-Workflow that provide durable workflow governance, provenance, evidence, evaluation, review, and acceptance while deleting or externalizing host/runtime machinery that Herdr and its plugin ecosystem already provide.

The new repository must begin from the current source history for traceability, but implementation work must occur independently from the current Agent-Workflow repository. The current repository remains the stable 0.11.x line until the replacement proves the required acceptance journeys.

## 2. Product thesis

Target product boundary:

~~~
request
  -> Agent-Workflow durable plan / policy
  -> immutable Agent Run
  -> Herdr execution binding
  -> Herdr-managed coding agent
  -> typed completion/evidence
  -> Agent-Workflow evaluation
  -> review
  -> acceptance
  -> dependent work released
~~~

Agent-Workflow should become the governed workflow and evidence layer.

Herdr should own the live execution environment.

Existing Herdr plugins should own optional operator experiences when they already solve them well.

### Agent-Workflow remains authoritative for

- workflow/task/Agent Run identity;
- immutable execution and delegation contracts;
- source baseline and provenance;
- durable workflow dependency state;
- exact artifact and revision identity;
- worker completion contracts;
- content-addressed evidence and sealed receipts;
- completion/evaluation/review/acceptance separation;
- evaluation and benchmark policy;
- deterministic lifecycle and replay semantics;
- TypeSafe/Jev semantic decision seams where they remain justified;
- acceptance and rejection authority;
- auditable human gates.

### Herdr becomes authoritative for

- terminal/workspace/tab/pane topology;
- starting supported coding-agent CLIs;
- live agent naming and pane occupancy;
- prompt transport;
- agent state detection;
- wait/read/focus/interactive control;
- blocked-agent presentation;
- host process/session lifecycle;
- remote-machine execution transport;
- worktree presentation and terminal placement;
- plugin lifecycle and host event delivery.

### Existing plugins should be preferred for

- diff/review presentation;
- progress dashboards;
- notifications and mobile relay;
- worktree setup/layout convenience;
- generic project/task boards;
- generic workflow authoring/execution where its semantics are sufficient;
- agent handoff UX;
- token/cost dashboards;
- native-agent-team presentation.

Agent-Workflow must not rebuild these categories unless a documented gap blocks a required invariant.

## 3. Why a new repository

The current codebase contains two architectural generations:

1. durable workflow/evidence authority;
2. a substantial host-neutral process/runtime layer built before Herdr exposed the current agent, plugin, event, machine, and worktree surfaces.

Performing the overhaul in place would mix compatibility preservation with architectural deletion. A new repository allows:

- an explicit minimum Herdr version;
- a smaller public API;
- removal rather than deprecation of obsolete runtime abstractions;
- a clean dependency graph;
- a new test strategy centered on Herdr contracts;
- independent benchmarking against 0.11.6;
- easy abandonment if prior-art analysis shows an existing project should be adopted instead.

The old repository remains useful as the reference implementation for invariants and evidence semantics during the migration.

## 4. Non-negotiable invariants

The overhaul may reduce code but must not weaken these properties:

1. A live terminal state is never workflow acceptance authority.
2. Agent completion is distinct from evaluation, review, and acceptance.
3. Source provenance is frozen before delegated mutation.
4. Acceptance binds to an exact verified revision/artifact set.
5. Retries create lineage rather than silently rewriting prior execution identity.
6. Durable state reconstructs after host restart.
7. Duplicate scheduler/reaction execution is idempotently rejected.
8. Human gates remain explicit where policy requires them.
9. External/provider output is untrusted until validated.
10. Semantic model decisions cannot override deterministic lifecycle constraints.
11. Missing evidence is not converted to success.
12. Host state is reconstructable projection data, not durable workflow identity.

## 5. Architecture decision gates

No destructive migration work starts until the following gates have explicit records.

### Gate A — Herdr core capability verification

Verify against the installed supported Herdr version:

- agent start;
- prompt and wait semantics;
- idle/working/blocked/done/unknown states;
- agent read/get;
- pane/process control;
- machine routing;
- worktree events;
- plugin event subscriptions;
- reconnect/restart behavior;
- opaque host identifier stability.

Deliverable: HERDR_CAPABILITY_MATRIX.md with live-test evidence.

### Gate B — Workflow-engine build versus integrate

Compare the remaining Agent-Workflow scheduler semantics against:

- XiaoConstantine/herdr-workflow;
- vekexasia/pi-extensible-workflows;
- aorumbayev/herdr-workflows;
- andthezhang/herdr-dynamic-workflow;
- cyperx84/herdr-loop;
- eliasstravik/herdr-projects;
- mikhail-angelov/herdr-review-loop.

The decision must answer:

- Can an existing engine host Agent-Workflow's immutable contracts and sealed evidence without losing authority?
- Does it support deterministic replay and duplicate-execution avoidance?
- Can completion/evaluation/review/acceptance remain separate?
- Can exact revisions and artifact digests be bound to gates?
- Can Agent-Workflow remain agent/provider neutral?
- Is the license compatible?
- Is the dependency mature enough to become infrastructure?

Possible outcomes:

A. retain a reduced Agent-Workflow scheduler;
B. adapt an existing workflow engine;
C. contribute missing primitives upstream and adopt it;
D. compose several plugins around a small Agent-Workflow evidence kernel.

No generic workflow DSL should be implemented before this gate closes.

### Gate C — Review UX

Evaluate persiyanov/herdr-reviewr and JonasBaeumer/herdr-file-annotator before implementing any interactive diff/review UI.

The core may still own review records and acceptance authority. UI is not authority.

### Gate D — Observability and notification

Evaluate Herdr events plus waynewu411/herdr-event-log, progress plugins, and notification/mobile plugins before retaining any bespoke poller or host notification framework.

### Gate E — Runtime routing

Evaluate nidhi-singh02/agent-router before retaining model/executor launch-routing machinery. Agent-Workflow may retain policy constraints and decision receipts while delegating host launch selection.

## 6. Target component model

A preferred initial decomposition is:

~~~
agent-workflow-core
  contracts
  provenance
  lifecycle
  workflow authority
  evidence
  evaluation
  review
  acceptance
  receipts
  semantic decisions

agent-workflow-herdr
  Herdr binding
  dispatch
  prompt transport
  state observation
  host-event reconciliation
  remote-machine binding

agent-workflow-cli
  operator commands
  public JSON views
  recovery commands

optional integrations
  existing Herdr workflow engine
  reviewr
  dagr
  event-log
  notification plugins
  routing plugins

legacy/compatibility
  optional headless backend only if benchmarks or CI prove it remains necessary
~~~

The implementation language and package split are not fixed by this plan. The architectural boundaries are.

## 7. Candidate deletion and reduction map

The following current 0.11.6 modules are migration targets, not automatic copy-forward candidates.

| Current area | Target action | Rationale |
| --- | --- | --- |
| external_host_projection.py | delete | Herdr is the host projection |
| runner.py | remove from normal path; possibly optional legacy backend | Herdr owns agent process execution |
| process.py agent lifecycle | delete/slim | retain safe subprocess helper only for Git/checks/tools |
| executors.py | major reduction | Herdr starts supported agents; routing may be external |
| agent_identity.py live-name leasing | delete/slim | Herdr owns unique live agent names |
| external_bindings.py | replace | one small Herdr binding/reconciliation contract |
| steering.py | major reduction | durable AW message -> Herdr prompt -> transport receipt |
| messages.py control bridge | delete | no file IPC needed for normal host transport |
| agent_run_control.py PID/PGID paths | delete | live control delegated to Herdr |
| health.py process sampling | delete/slim | Herdr state/events replace /proc inference |
| supervisor.py process diagnosis | rewrite | reconcile durable AW state against Herdr state |
| orchestrator_supervisor.py | retain/slim | deterministic workflow progression remains |
| orchestrator_inbox.py | re-evaluate | may be unnecessary if reducer can reconcile authoritative run journals directly |
| worktrees.py | retain provenance; slim UX | AW verifies source identity; Herdr may create/present worktrees |
| scheduler.py/workflow.py | decision-gated | retain only if prior-art engines cannot satisfy invariants |
| lifecycle/evidence/eval/review/receipts | retain and simplify | core differentiation |

The existing runtime/host candidate set is roughly 4 KLOC before CLI/config/tests. LOC reduction is not itself a goal; eliminating duplicate authority is.

## 8. Proposed phases

### Phase 0 — Fork, freeze, and research

- create the new repository from the 0.11.6 source lineage;
- record source commit and origin;
- copy only planning/research material initially;
- complete the prior-art matrix;
- verify licenses and release maturity;
- live-test Herdr primitives;
- benchmark current 0.11.6 orchestration overhead;
- freeze required behavioral invariants.

Exit: architecture decision record chooses the dependency/reuse strategy.

### Phase 1 — Minimal evidence kernel

Extract or port only:

- Agent Run identity/contract;
- source baseline;
- append-only lifecycle;
- completion contract;
- final receipt;
- review/accept/reject;
- evidence sealing;
- minimum CLI views.

Do not port runner, process supervision, executor adapters, terminal projection, or old delivery adapters.

Exit: a manually executed Agent Run can be prepared, supplied valid completion evidence, evaluated/reviewed, accepted, and replayed.

### Phase 2 — Herdr execution adapter

Implement a narrow adapter around public Herdr CLI/socket contracts.

Minimum operations:

- resolve/create execution pane;
- start agent by kind;
- bind Agent Run to machine/session/pane/agent identity with generation;
- prompt;
- wait;
- read status/output when diagnostically required;
- record blocked/unknown;
- interrupt/terminate through supported Herdr controls;
- reconcile a binding after restart.

The adapter does not decide workflow state.

Exit: one Agent Run executes end-to-end through Herdr with no Agent-Workflow-owned coding-agent subprocess.

### Phase 3 — Durable transport and event reconciliation

Implement:

~~~
persist instruction
  -> dispatch through Herdr
  -> record transport receipt
  -> worker produces semantic acknowledgement/completion
~~~

Consume Herdr host events where appropriate, but replay Agent-Workflow durable authority after any missed event.

Delete control-file transport and PID/heartbeat inference from the new implementation.

Exit: lost live events, Herdr restart, duplicate notifications, and rebinds do not corrupt run state.

### Phase 4 — Workflow engine decision implementation

Execute the outcome of Gate B.

If retaining the scheduler:

- port only dependency/retry/replay/idempotence logic;
- remove generic host concerns;
- replace the aggregate inbox if direct reconciliation is simpler.

If integrating another engine:

- define a typed adapter;
- bind its stage/node IDs to Agent Run contracts;
- keep evidence and acceptance authority in the Agent-Workflow kernel;
- ensure plugin/engine state cannot silently authorize Agent-Workflow transitions.

Exit: multi-node dependency workflow survives restart and launches each eligible child exactly once.

### Phase 5 — Operator UX by composition

Integrate rather than rebuild:

- Dagr for DAG visualization if its contract can consume AW projection safely;
- reviewr/file-annotator for human review surfaces;
- progress/event-log for live host observation;
- notification/mobile plugins for attention routing;
- worktree setup/layout plugins for convenience;
- routing plugin when its policy fits configured deployment.

Exit: the core has no bespoke UI feature already well-solved in the ecosystem.

### Phase 6 — Evaluation and decision modes

Port only evaluation features that remain distinct:

- criteria/evidence validation;
- deterministic scoring;
- comparative evaluation;
- benchmark receipts;
- TypeSafe/Jev decision seams where semantic judgment is actually required;
- decision audit evidence.

Re-run BM3/BM4-style benchmarks against the old implementation.

### Phase 7 — Cutover

Requirements:

- all protected invariant tests pass;
- installed end-to-end Herdr journeys pass;
- restart/replay tests pass;
- remote-machine journey passes if supported;
- benchmark overhead is materially lower;
- public docs describe the reduced boundary;
- migration guide exists;
- old repository is marked maintenance/legacy only after the new line is demonstrably ready.

## 9. Testing strategy

Testing should emphasize authority boundaries rather than implementation details.

### Contract tests

- immutable Agent Run contract;
- provenance digest;
- lifecycle transitions;
- receipt sealing;
- revision-bound acceptance;
- duplicate-event handling;
- stale binding generation rejection.

### Adapter tests

Use fake Herdr command/socket responses for:

- start;
- prompt;
- working -> done;
- blocked;
- unknown;
- pane disappearance;
- machine disconnect;
- stale/replaced binding;
- Herdr restart.

### Installed acceptance journeys

At minimum:

1. single implementation run;
2. implementation -> independent review;
3. rejected review -> retry lineage;
4. two-node dependency release;
5. blocked agent requiring human action;
6. Herdr restart during a run;
7. Agent-Workflow process restart while Herdr agent remains alive;
8. completion reported but invalid evidence;
9. agent done with no valid completion contract;
10. duplicate event/reaction replay;
11. dirty baseline with explicit authorization;
12. remote worker if remote execution remains supported.

### Comparative tests

Every feature proposed for custom implementation must include a short comparison against the relevant existing Herdr plugin. “We already have code for it” is not a sufficient reason to retain it.

## 10. Data migration

The new repository does not need binary compatibility with every 0.11.x internal file.

Required compatibility is narrower:

- old sealed Agent Run evidence remains readable by a migration/reporting utility where practical;
- new runs use the new contract version;
- source repository history and release receipts remain immutable;
- benchmark results identify which implementation generated them.

Do not add compatibility shims that recreate the old execution architecture.

## 11. Security model

Herdr-managed agents normally run as the same OS user. Therefore:

- pane/worktree separation is not hostile-process containment;
- host/plugin state is not a security boundary;
- human gates are policy controls unless a protected identity/channel is used;
- plugins must be treated as trusted local code;
- third-party plugins may supply UX or transport, but cannot silently become acceptance authority.

If hostile-process containment becomes a requirement, evaluate VM/container isolation such as AgentBox-style environments separately.

## 12. Success criteria

The overhaul succeeds when:

- normal coding-agent execution is owned by Herdr, not Agent-Workflow;
- no duplicate live-agent name/PID/terminal authority remains;
- no Agent-Workflow control-file transport is required for normal operation;
- host liveness is obtained from Herdr rather than bespoke /proc inference;
- optional UX is composed from existing plugins wherever practical;
- workflow/evidence authority reconstructs without Herdr event replay;
- exact source/artifact/revision provenance survives;
- completion/evaluation/review/acceptance remain distinct;
- total setup/context/runtime overhead improves against 0.11.6;
- the resulting product can be explained as a small governed orchestration/evidence layer rather than a second terminal and agent runtime.

## 13. Immediate next actions

1. Create the target repository and seed it from this planning branch.
2. Preserve the original repository as upstream/reference.
3. Complete the live Herdr capability verification.
4. Perform focused evaluation spikes for the highest-overlap workflow engines.
5. Produce ADR-001 choosing retain-vs-integrate for workflow scheduling.
6. Only then begin Phase 1 code extraction.
