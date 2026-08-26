# Agent-Workflow 0.9 Skill-First Simplification Plan

**Status:** Accepted implementation direction for the 0.9 line  
**Baseline:** 0.8 headless-core rewrite plus eight-phase code simplification and documentation cleanup  
**Development version:** 0.9.0  
**Status authority:** `docs/BACKLOG.md` remains the only register of unfinished/completed work. This document defines architecture, sequencing, constraints, and acceptance criteria; it is not a second ticket tracker.

## 1. Purpose

Agent-Workflow has already completed the hardest architectural correction: it no longer owns tmux, terminal panes, terminal topology, or an interactive runtime. The durable model is now:

```text
Workflow -> Task -> Agent Run -> Worker
```

The next objective is different. The 0.9 line must make Agent-Workflow **cheap for an agent to understand and use** while retaining only the mechanisms that materially improve correctness, durability, recoverability, evidence quality, or review quality.

The governing product principle is:

> Keep the durable correctness engine; remove or hide workflow ceremony that makes an agent slower without making its result more trustworthy.

Agent-Workflow should increasingly feel like a **small agent-facing skill backed by deterministic durable services**, not like a large framework whose full feature inventory must be understood before useful work can begin.

## 2. Current-state assessment

### 2.1 What the 0.8 rewrite accomplished

The accepted headless rewrite is complete and must not be reversed:

- tmux runtime implementation is removed;
- terminal/session-manager identity is absent from the durable execution model;
- no generic terminal-host abstraction replaced tmux under another name;
- headless workers are Agent-Workflow-owned process groups;
- external workers are host-owned while Agent-Workflow remains workflow authority;
- worktree/source provenance remains durable Agent-Workflow authority;
- steering is persist-first;
- delivery is not acknowledgement;
- worker exit is not completion;
- completion, evaluation, review, and acceptance remain separate authorities;
- workflow state is restartable and replayable;
- evidence/receipts remain independently verifiable;
- Herdr is not a core dependency.

These are correctness properties. They stay.

### 2.2 What the simplification program accomplished

The completed 0.8 simplification program also removed substantial implementation waste:

- obsolete pre-0.8 compatibility branches were deleted rather than preserved;
- repeated append-only JSONL mechanics were consolidated into one journal primitive;
- Agent Run lifecycle authority was reduced to one current model;
- Agent Run preparation and terminal sealing paths were consolidated;
- canonical JSON/digest primitives were unified where semantics actually match;
- the prompt-pack format was reduced to one current root-manifest model;
- benchmark assets were deduplicated into immutable shared layers plus thin suite overrides;
- large modules were split only where independent authorities existed;
- historical documentation and repository mirrors were removed after their obligations became current tests, docs, or backlog entries.

Do not reopen those decisions merely to reduce file count further.

### 2.3 Current size is no longer the primary problem

At the 0.9 planning baseline the repository contains approximately:

- **134** product Python modules under `src/agent_workflow` excluding packaged assets;
- **91** JSON Schemas;
- **6** installed skills;
- **93** parser-derived CLI leaf commands;
- **18** active files under `docs/` before this plan is added.

The full command catalog is roughly 15.9 KB / 750 Markdown lines. More importantly, the current role cards are uneven:

| Role | Commands | Approx. Markdown size | Assessment |
| --- | ---: | ---: | --- |
| implementation | 7 | 1.5 KB | already appropriately small |
| review | 11 | 2.1 KB | already appropriately small |
| orchestrator | 58 | 10.0 KB | too broad for the normal agent path |
| all | 93 | 15.9 KB | maintainer/reference surface only |

This is the central 0.9 usability problem: **the implementation is reasonably decomposed, but the normal orchestrator/skill surface still exposes too much of it.**

### 2.4 The post-rewrite work was only partially completed

The post-Phase-0–2 design correctly identified three unfinished areas that remain relevant:

- primary skill hardening (`SKILL-001`);
- host-neutral external Worker binding/reconciliation (`BIND-001`);
- stable public structured JSON interfaces (`API-001`).

Those items remain part of the 0.9 plan. The Herdr plugin remains downstream of them.

## 3. Locked product direction

### 3.1 Agent-Workflow is a correctness kernel plus skill

The preferred product model is:

```text
coding agent
    |
    v
small Agent-Workflow skill
    |
    v
deterministic public commands / JSON contracts
    |
    v
Agent-Workflow correctness kernel
    |
    +-- durable Agent Run lifecycle
    +-- worktree/source provenance
    +-- durable messaging/replay
    +-- workflow/DAG authority
    +-- evidence/sealing
    +-- evaluation
    +-- review/acceptance
    +-- optional advanced capabilities
```

The skill decides **when and how** to use the engine. The engine remains authoritative for state, integrity, policy, and receipts.

### 3.2 The skill is guidance, not durable authority

Do not move these concerns into prose-only skill instructions:

- identifiers;
- canonical serialization;
- path containment;
- message ordering/replay;
- process ownership;
- evidence hashing/sealing;
- state transition legality;
- evaluation arithmetic;
- acceptance authorization;
- workflow DAG reconstruction.

The skill may explain or invoke these rules, but deterministic code must continue to enforce them.

### 3.3 Advanced features should be progressively disclosed

Normal delegation should not require awareness of:

- benchmark publication/runtime machinery;
- SQLite analytical indexing;
- MCP internals;
- plugin registration mechanics;
- release-evidence generation;
- hierarchy receipts unless hierarchical delegation is actually requested;
- telemetry integrations;
- advanced repair/recovery commands unless a failure occurs.

These capabilities may remain installed when they do not impose measurable startup/context cost. They should leave the default **agent-visible** surface first. Physical package extraction is a later optimization and requires evidence.

### 3.4 Do not replace tmux coupling with Herdr coupling

The dependency direction remains:

```text
Herdr plugin -> public Agent-Workflow contracts
Agent-Workflow core -X-> Herdr internals
```

Herdr may own presentation, interactive worker launch, best-effort live delivery, navigation, and rebuildable binding state. It may not own Agent Run identity, durable messages, completion/evaluation/review/acceptance authority, or source provenance.

## 4. What must remain in the core

The following features earn their complexity because they directly increase correctness, auditability, recoverability, or controlled execution quality.

### 4.1 Agent Run contract and lifecycle

Keep:

- immutable Agent Run execution contract;
- explicit Worker mode;
- headless process-group ownership;
- external prepare-only semantics;
- retry/restart lineage;
- bounded interrupt/terminate semantics;
- terminal sealing independent of UI state.

### 4.2 Worktree and source provenance

Keep:

- clean-source checks;
- source revision/baseline binding;
- authoritative worktree identity;
- closeout/integration verification;
- safe path policy.

### 4.3 Durable messaging

Keep:

- persist-first steering;
- progress;
- explicit acknowledgement;
- sequence/correlation IDs;
- replay/cursors;
- duplicate-safe recovery.

### 4.4 Workflow authority

Keep:

- immutable workflow snapshot;
- dependency eligibility;
- bounded parallelism;
- deterministic resume/replay;
- result bindings;
- approval gates;
- workflow receipts.

### 4.5 Evidence, evaluation, review, and acceptance separation

Keep the sequence logically separate:

```text
worker execution
    -> completion evidence
    -> evaluation
    -> review
    -> acceptance/rejection
```

Do not introduce a convenience path that silently collapses these authorities.

### 4.6 Security/durability primitives

Keep explicit tests and implementation for:

- path/symlink safety;
- append-only journals;
- canonical digests;
- sealed-receipt verification;
- executable/environment trust policy;
- process-group signaling;
- evaluator/accounting math;
- replay/idempotence.

These are not candidates for simplification by prose.

## 5. What should become cheaper or less visible

### 5.1 Full command discovery during normal work

A normal agent should not need to inspect the 93-command catalog.

The current launch artifacts already produce role-specific Markdown cards, but the run still binds/writes the complete machine catalog and the launch context directs the agent toward it. In 0.9, launch-scoped command material should be role-scoped by default.

**Target:**

- implementation role: remain at **<= 8 commands** and **<= 2 KB** human command card;
- review role: remain at **<= 12 commands** and **<= 3 KB**;
- normal orchestrator/skill role: reduce from **58** to **<= 20 commands** and **<= 5 KB**;
- full 93-command catalog remains available only through explicit maintainer/reference discovery.

The exact installed parser remains the ultimate command authority. Role filtering must not become a second parser or hand-written argument model.

### 5.2 Multi-command ceremony for the common delegation path

The current documented happy path requires separate worktree creation, Agent Run preparation, start, and status operations. Those boundaries are useful internally but unnecessarily expensive as repeated model decisions.

Introduce one **high-level delegation facade** for the common case. The accepted command direction is:

```text
agent-workflow delegate ...
```

It should compose existing services in-process and emit the same underlying durable artifacts. It must not shell out to lower-level CLI commands or create a parallel lifecycle implementation.

The facade may perform, as requested:

```text
validate source
-> create/resolve worktree
-> prepare Agent Run
-> start headless worker OR return external launch contract
-> return compact structured status/context
```

It must **not** auto-review or auto-accept work. Lower-level commands remain for diagnostics, recovery, specialized orchestration, and exact control.

### 5.3 Documentation lookup during an Agent Run

A worker should not need repository documentation to learn its runtime contract.

The launch context plus role-scoped command card and `agent context` output should contain the minimum complete operational information for the assigned role. The launch prompt should explicitly discourage broad documentation/CLI exploration unless the supplied contract is inconsistent or incomplete.

### 5.4 Manually authored lifecycle boilerplate in skills

The primary skill should stay concise. Do not turn skill hardening into a 500-line manual.

The skill should contain:

1. when to use Agent-Workflow;
2. when **not** to use it;
3. the minimum durable model;
4. the default delegation flow;
5. the small set of correctness invariants an agent must understand;
6. failure/recovery escalation rules;
7. pointers to specialized skills only when the task requires them.

Exact command syntax should come from the parser-derived role card wherever practical.

### 5.5 Unnecessary use of Agent-Workflow

The skill must explicitly avoid invoking Agent-Workflow when its durability/evidence machinery does not justify the overhead.

Examples where AW is normally unnecessary:

- read-only explanation or code review that requires no delegated execution;
- a single deterministic local command with no need for restart/replay/evidence;
- trivial edits where the caller already owns execution and no independent review/evidence contract is requested;
- exploratory brainstorming that has not become an implementation task.

Examples where AW is justified:

- delegated coding work;
- long-running or restart-sensitive work;
- multi-agent or dependency-ordered work;
- work needing bounded worktrees/source provenance;
- work requiring durable steering/progress;
- work requiring structured completion/evals/review;
- benchmarked or audited work.

## 6. 0.9 implementation phases

### Phase 0 — Efficiency baseline and guardrails

**Goal:** measure agent-facing cost before changing behavior.

Tasks:

1. Record parser leaf-command count and role-card size.
2. Measure launch-context bytes/tokens for implementation, review, and orchestrator roles.
3. Measure number of Agent-Workflow CLI invocations needed for representative simple delegation, review, workflow, and recovery journeys.
4. Record wall time attributable to Agent-Workflow setup/finalization separately from executor work.
5. Add an agent-efficiency fixture/eval that can compare 0.8-style operation with the 0.9 skill-first path.
6. Preserve correctness assertions for worktree provenance, durable messaging, completion validation, evidence sealing, review, and acceptance.

**Do not optimize** by deleting correctness gates simply because they consume time.

### Phase 1 — Minimize the agent-visible command surface

**Goal:** make role-scoped command contracts the normal interface.

Tasks:

1. Add a normal skill/orchestrator command profile separate from the full maintainer catalog.
2. Keep implementation and review profiles small.
3. Write the launch-scoped machine catalog already filtered to the role/profile rather than writing the complete 93-command catalog for every Agent Run.
4. Keep a digest binding between the role-scoped catalog, parser/application version, and launch receipt.
5. Ensure explicit `agent-workflow commands --role all` remains available for maintainers.
6. Update launch context so agents use the scoped card/catalog first and do not perform routine `--help` discovery.
7. Add release tests proving every profile references only real parser commands and that no required command silently disappears.

**Acceptance targets:**

- implementation: <= 8 commands;
- review: <= 12 commands;
- normal orchestrator: <= 20 commands;
- normal orchestrator card: <= 5 KB;
- no correctness-relevant command needed by a role is available only through undocumented discovery.

### Phase 2 — Make the primary skill the default product interface

**Goal:** an agent can make the right decision without repository-specific tribal knowledge.

Tasks:

1. Complete `SKILL-001` with a concise use/do-not-use decision section.
2. Make the normal flow start with the high-level delegation facade once Phase 3 lands.
3. Keep specialized skills thin and explicitly compositional.
4. Remove duplicated lifecycle prose from specialized skills where the primary skill is authoritative.
5. Generate/check command examples against the live parser during release validation.
6. Add deterministic skill evals for:
   - choosing no AW when it adds no value;
   - selecting headless versus external mode;
   - never invoking terminal-manager behavior;
   - persist-before-deliver;
   - delivery != acknowledgement;
   - worker exit != completion/acceptance;
   - preserving source/worktree provenance;
   - using recovery rather than improvising around sealed evidence.

**Constraint:** skill hardening must not materially increase normal prompt/context load. Prefer generated runtime context to prose duplication.

### Phase 3 — Add the deterministic fast path

**Goal:** reduce common delegation from several model decisions to one deterministic composition.

Implement `agent-workflow delegate` as a thin facade over current service authorities.

Required properties:

- no parallel lifecycle state machine;
- no duplicated worktree implementation;
- no duplicated prepare/start implementation;
- no implicit acceptance;
- same evidence and receipt chain as lower-level calls;
- `--json` output suitable for a skill or external host;
- idempotent behavior where an existing prepared run/worktree is supplied;
- explicit dry-run/plan capability if needed to preserve operator control;
- failure output identifies the exact failed internal stage without requiring log archaeology.

Representative headless flow becomes conceptually:

```text
agent-workflow delegate ...
-> returns agent_run_id, worktree, state, next_actions
```

Representative external flow becomes:

```text
agent-workflow delegate --worker-mode external ...
-> returns prepared launch contract; launches nothing
```

### Phase 4 — Stabilize public JSON and external Worker contracts

**Goal:** skills/plugins should not import private Python modules or scrape prose.

Complete `API-001` and `BIND-001` together.

Required structured surfaces:

- delegation/prepare result;
- Agent Run status;
- compact Agent Run context;
- pending messages and acknowledgement state;
- completion/evaluation/review summary;
- workflow status;
- worktree/source provenance;
- benchmark status only when benchmark capability is used;
- external Worker binding/reconciliation state.

External binding must remain rebuildable projection data and contain only host-neutral/opaque identity such as:

```text
agent_run_id
worker_id
worker_mode=external
external_runtime_type
external_worker_id
generation
bound_at
last_observed_at
```

Host observations never become completion, review, or acceptance authority.

### Phase 5 — Progressive capability isolation

**Goal:** advanced capabilities should impose near-zero cognitive cost when unused.

First apply **exposure isolation**, not repository churn:

- normal skill/card omits benchmark internals;
- normal skill/card omits index administration;
- normal skill/card omits MCP administration;
- normal skill/card omits plugin maintenance;
- normal skill/card omits release-evidence internals;
- hierarchy/orchestrator details appear only for multi-agent/hierarchical tasks.

Then measure import/startup/package costs. Only if a subsystem creates material runtime or maintenance cost should it be extracted into a separate plugin/package.

Candidate extraction review order:

1. publication/visual benchmark tooling;
2. telemetry integrations;
3. MCP mutation functionality if/when implemented;
4. host-specific integrations such as Herdr;
5. other optional analytics/integration surfaces with a proven independent boundary.

Do **not** extract durable lifecycle, messaging, workflow, evidence, evaluation, review, or worktree authority merely to make the core directory smaller.

### Phase 6 — Test and execution-efficiency consolidation

**Goal:** preserve authority coverage while reducing redundant execution cost.

Tasks:

1. Keep broad installed-product journeys for common lifecycle semantics.
2. Keep narrow invariants only for security, durability, replay, schema, path, state-machine, and accounting properties that are cheaper/more deterministic in isolation.
3. Continue deleting duplicate low-level tests when a stronger journey proves the same behavior.
4. Fix the acceptance-suite process/fixture teardown issue so the full acceptance layer can run monolithically and exit cleanly, not merely pass when split by file/case.
5. Track wall time as well as test count in `tests/test-authority.json` or an adjacent machine-readable budget.
6. Add a regression budget for launch/context generation so agent-facing simplification cannot silently bloat again.

Current test-count reduction is not itself a goal. **Unique authority coverage per unit of test/runtime cost** is the goal.

### Phase 7 — 0.9 closeout

0.9 is ready for release when:

1. the normal skill path does not require full-command discovery;
2. a representative simple delegation can be initiated through one high-level deterministic facade;
3. implementation/review role cards remain small;
4. the normal orchestrator role is <= 20 commands / <= 5 KB;
5. skill evals prove correct use and correct non-use;
6. external Worker binding is host-neutral and public;
7. public JSON surfaces eliminate private-import requirements for supported integrations;
8. no tmux or generic terminal-host architecture reappears;
9. Herdr remains optional and downstream;
10. invariant, acceptance, release, test-authority, release-asset, version, and documentation audits pass;
11. full acceptance execution terminates cleanly as a suite;
12. measured Agent-Workflow setup/context overhead improves versus the Phase 0 baseline without weakening the protected correctness journey.

## 7. Herdr direction after the 0.9 core surface stabilizes

Herdr integration should be a separate package/plugin built only after the 0.9 binding/API contracts are stable.

The plugin may provide:

- launch of prepared external Workers;
- workspace/pane presentation;
- best-effort immediate delivery after AW persistence;
- host binding/reconciliation;
- focus/navigation;
- progress/evidence/review presentation;
- benchmark workspace presentation;
- disposable cached UI state.

The plugin must be reconstructable from Agent-Workflow durable state plus current Herdr topology. Deleting plugin-local state must not delete workflow facts.

Do not add Herdr-specific schema fields to core simply because the first implementation uses Herdr.

## 8. Schema strategy

The 91 schema files are not a simplification target by count.

Delete a schema only when:

- no current writer emits it;
- no supported reader consumes it;
- no current sealed evidence requires it;
- no public contract claims it.

Do not merge independently versioned durable contracts into a monolithic schema merely to reduce file count.

Instead, reduce **agent exposure** to schemas:

- launch context names only the contracts relevant to the run;
- generated templates are authoritative for completion/result shape;
- agents validate through commands instead of manually reasoning over schema files;
- public JSON descriptors expose schema IDs/digests where needed.

## 9. Module strategy

The 134 Python modules are also not a target by count.

Combine/delete modules only when one of these is true:

- two modules own the same durable authority;
- one is only a compatibility facade;
- repeated serialization/persistence mechanics have reappeared;
- two interfaces cannot change independently in practice;
- an optional integration has a clean one-way dependency boundary and measurable isolation benefit.

Do not recombine `agent_runs`, evidence collection, index integrity/review, or other Phase-8-separated authorities merely to make the tree look smaller.

## 10. Performance and context budgets

0.9 should introduce explicit budgets that reflect the actual user/agent cost.

Recommended initial budgets:

| Metric | 0.9 target |
| --- | ---: |
| implementation role commands | <= 8 |
| review role commands | <= 12 |
| normal orchestrator role commands | <= 20 |
| implementation role card | <= 2 KB |
| review role card | <= 3 KB |
| normal orchestrator role card | <= 5 KB |
| normal delegation setup decisions | 1 high-level invocation plus explicit review/acceptance |
| default skill dependence on repo docs | none during a healthy run |
| terminal-host dependencies in core | 0 |
| Herdr dependencies in core | 0 |

Add runtime/wall-time targets after Phase 0 captures a stable local baseline. Avoid arbitrary timing limits before measurement.

## 11. Testing policy for 0.9 simplification

Every simplification must answer two questions:

1. **What agent/user cost is being removed?**
2. **Which correctness authority remains responsible for the behavior?**

A change is not simplification if it only moves complexity into hidden prose, a plugin, or another duplicate service.

Required protected journeys include:

- headless delegation and sealing;
- external prepare without host launch;
- persist/steer/ack/replay;
- restart lineage;
- workflow dependency/result binding and resume;
- invalid completion fails closed with useful evidence;
- review/acceptance separation;
- source/worktree provenance;
- sealed-evidence tamper detection;
- role-scoped command contract correctness;
- skill decision evals;
- fast-path equivalence to the underlying lower-level services.

## 12. Explicit non-goals

0.9 does **not** aim to:

- reach a cosmetically small module count;
- collapse durable schemas into fewer files;
- make every feature available through one giant command;
- hide failures by auto-repairing immutable evidence;
- auto-accept successful-looking work;
- remove evaluation/review boundaries to save time;
- replace Agent-Workflow durable messaging with host delivery;
- implement a generic terminal host;
- add Herdr as a core dependency;
- build the separate spec-generation system inside Agent-Workflow;
- preserve pre-0.8 compatibility.

## 13. Recommended execution order

The implementation order is locked as:

```text
0. baseline + efficiency evals
1. role-scoped surface reduction
2. primary skill + skill evals
3. deterministic delegate fast path
4. public JSON + external binding contract
5. progressive advanced-capability isolation
6. test/runtime efficiency consolidation
7. 0.9 closeout
```

Herdr plugin work begins only after Phase 4 contracts are stable enough that the plugin can be implemented without importing private Agent-Workflow modules.

## 14. Definition of success

The project has reached the intended direction when a capable coding agent can use Agent-Workflow correctly from the primary skill without learning the repository, scanning 93 commands, reading dozens of schemas, or understanding optional subsystems—and when the resulting run still has the durable provenance, replay, evidence, evaluation, review, and acceptance guarantees that justify using Agent-Workflow in the first place.

That is the 0.9 product boundary:

> **A small skill-facing interface over a durable correctness kernel.**
