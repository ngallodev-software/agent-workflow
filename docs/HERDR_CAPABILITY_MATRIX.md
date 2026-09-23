# Herdr Capability and Ownership Matrix

Status: architecture input  
Date: 2026-09-22  
Baseline: Agent-Workflow 0.11.6 at 63627e6ec73fa62c18da64ffc38c5189cced6458

## Decision legend

- KEEP — durable Agent-Workflow responsibility.
- HERDR — delegate to Herdr core.
- PLUGIN — use an existing Herdr plugin/integration when practical.
- COMPARE — requires build-vs-integrate spike before implementation.
- DELETE — do not port the current implementation.
- OPTIONAL — only retain behind a separate compatibility/backend package if justified.

## Matrix

| Capability | Current Agent-Workflow | Herdr / prior art | Target owner | Decision |
| --- | --- | --- | --- | --- |
| Agent Run identity | durable run ID | Herdr has host/pane/agent IDs, not AW semantics | Agent-Workflow | KEEP |
| Task/run lineage | retry lineage | workflow projects have run IDs but different semantics | Agent-Workflow | KEEP |
| Immutable execution contract | yes | no equivalent Herdr core authority | Agent-Workflow | KEEP |
| Source baseline | yes | Herdr knows cwd/worktree | Agent-Workflow | KEEP |
| Dirty-source authorization | yes | host worktree state only | Agent-Workflow | KEEP |
| Exact accepted revision | yes | review plugins display revisions/diffs | Agent-Workflow | KEEP |
| Workspace/tab/pane topology | deliberately external but supporting glue exists | Herdr core | Herdr | HERDR |
| Coding-agent process launch | headless runner/executors | Herdr agent start | Herdr | DELETE current path |
| Live agent naming | AW logical name lease | Herdr unique live agent names | Herdr for live name; AW keeps worker ID | DELETE lease |
| Executor CLI discovery | AW executor config | Herdr supported agent kinds | Herdr | DELETE/slim |
| Model/account routing | AW aliases + TypeSafe modes | agent-router | compare/integrate | COMPARE |
| Prompt transport | control-file / external host path | Herdr agent prompt | Herdr adapter | DELETE current adapters |
| Wait for work start | process/output inference | Herdr prompt --wait activity gate | Herdr | HERDR |
| Live state | PID/log/heartbeat/permission inference | idle/working/blocked/done/unknown | Herdr | HERDR |
| Raw output inspection | executor logs | Herdr agent/pane read | Herdr for diagnostics | HERDR |
| Interrupt/terminate | PID/PGID signals | Herdr agent/pane controls | Herdr | DELETE PID control |
| Remote machines | external-host abstraction | Herdr machine API | Herdr | HERDR |
| Host binding | external worker binding journal | pane/agent/machine IDs | thin AW binding | KEEP SMALL |
| Host binding generation | yes | Herdr IDs can be replaced/moved | AW adapter | KEEP SMALL |
| Worktree creation UI | AW worktree command | Herdr worktree + many plugins | Herdr/plugins | PLUGIN |
| Worktree provenance | yes | host worktree state is not sealed provenance | Agent-Workflow | KEEP |
| Worktree bootstrap | none/general | worktree-setup/seed/bootstrap plugins | plugin | PLUGIN |
| Ticket -> worktree UX | prompt pack / external | worktree-from-linear and similar | plugin | PLUGIN |
| Durable messages | append-only AW journal | Herdr prompt is transport only | Agent-Workflow | KEEP |
| Live steering delivery | control-file/external-host adapters | Herdr prompt | Herdr adapter | DELETE adapters |
| Semantic acknowledgement | correlated AW ack | Herdr transport does not imply application | Agent-Workflow | KEEP |
| Host event stream | polling/supervisor | Herdr events.subscribe | Herdr | HERDR |
| Durable host-event replay | AW health journals | herdr-event-log pattern | plugin/adapter, non-authoritative | PLUGIN |
| PID/process sampling | /proc health | Herdr live state | none in normal path | DELETE |
| Heartbeat files | runner | Herdr state/events | none in normal path | DELETE |
| Stall observation | semantic progress + process signals | Herdr state + progress plugins | AW policy over Herdr observations | SLIM |
| Blocked permission detection | AW permission inference | Herdr blocked state | Herdr | HERDR |
| Blocked remediation | supervisor | herdr-auto-pilot and workflow engines | optional plugin + AW policy | COMPARE |
| Generic notifications | watcher callback concepts | many notify/mobile plugins | plugin | DELETE custom framework |
| Progress UI | AW status output | agent-progress, dashboards | plugin | PLUGIN |
| Token/cost UI | metrics/reporting | token dashboard/usage plugins | plugin | PLUGIN |
| Provider accounting evidence | provider evidence sealed in receipt | dashboards are observational | Agent-Workflow | KEEP |
| Generic task board | workflow views | tsk, beads | plugin | DELETE UI |
| Generic project coordinator | orchestrator inbox/supervisor | Herdr Projects | compare | COMPARE |
| Simple YAML workflow | AW workflow JSON | herdr-workflows | compare/integrate | COMPARE |
| Scripted dynamic workflow | AW scheduler | herdr-dynamic-workflow | compare | COMPARE |
| Resumable Pi workflow | AW scheduler | pi-extensible-workflows | compare | COMPARE |
| Review/retry loop | AW workflow + review | herdr-loop/review-loop | compare/integrate | COMPARE |
| Event-sourced workflow reducers | AW journals/lifecycle | XiaoConstantine/herdr-workflow | critical comparator | COMPARE |
| DAG scheduling | scheduler.py | several workflow engines | undecided | COMPARE |
| Duplicate launch avoidance | yes | varies by workflow engine | AW or selected engine | MUST PRESERVE |
| Restart/replay | yes | varies | AW or selected engine | MUST PRESERVE |
| Orchestrator aggregate inbox | 631-line subsystem | Herdr Projects uses file inbox/ticker; events available | likely delete/rewrite | COMPARE |
| Workflow visualization | CLI/status | herdr-dagr | plugin | PLUGIN |
| Diff review UI | no rich native UI | reviewr/file-annotator | plugin | PLUGIN |
| Review record authority | yes | UI/loop plugins do not provide same acceptance semantics | Agent-Workflow | KEEP |
| Independent reviewer constraint | yes/policy | some workflow projects support separate agents | Agent-Workflow or chosen reducer | KEEP |
| Completion contract | typed | workflow plugins generally return result/status | Agent-Workflow | KEEP |
| Criteria evidence | yes | some schema outputs/check helpers | Agent-Workflow | KEEP |
| Command verification evidence | yes | workflow run steps exist | Agent-Workflow | KEEP |
| Evaluation | yes | various judge helpers | Agent-Workflow | KEEP unless formally replaced |
| Comparative evaluation | plugin/built-in integration | no direct equivalent identified | Agent-Workflow | KEEP |
| TypeSafe/Jev decision audit | yes | agent-router uses TypeSafe for routing | divide by seam | COMPARE |
| Review != acceptance | explicit | not universal in plugins | Agent-Workflow | KEEP |
| Final sealed receipt | yes | no equivalent Herdr core primitive | Agent-Workflow | KEEP |
| SQLite read projection | yes | many plugins have local DBs | optional AW projection | RE-EVALUATE |
| Read-only MCP | yes | Herdr/plugin ecosystem may make it less necessary | optional | RE-EVALUATE |
| Session handoff | retry context / manual | herdr-agent-handoff | plugin for conversational UX | PLUGIN |
| Native agent teams | not primary model | herdmates | provider/host feature | PLUGIN |
| Strong sandbox/isolation | same-user execution | AgentBox-style environments | future optional | OPTIONAL |

## Module-level migration estimate

The current host/runtime-heavy modules measured during the audit total approximately 3,969 source lines before CLI/config/tests:

| Module | Approx. lines | Target |
| --- | ---: | --- |
| runner.py | 675 | remove from normal core |
| executors.py | 352 | replace with host/routing resolution |
| agent_identity.py | 486 | remove live-name lease/process checks |
| agent_run_control.py | 316 | keep durable message operations; move live control to Herdr |
| steering.py | 453 | replace delivery adapters with Herdr transport receipt |
| external_bindings.py | 429 | replace with small Herdr binding |
| external_host_projection.py | 182 | delete |
| health.py | 423 | remove process sampling; keep only durable semantic observations if needed |
| supervisor.py | 510 | rewrite as reconciliation policy |
| orchestrator_supervisor.py | 143 | retain/slim deterministic reactor |

This is not a 3,969-line deletion target. Some logic will reappear in smaller form. The target is one authority per concern.

## Thin Herdr binding proposal

The normal host binding should be close to:

~~~json
{
  "schema": "agent-workflow/herdr-binding/v1",
  "agent_run_id": "RUN-001",
  "worker_id": "worker-...",
  "generation": 1,
  "machine": "local",
  "workspace_id": "w1",
  "pane_id": "w1:p4",
  "agent_name": "aw-run-001",
  "agent_kind": "codex",
  "bound": true,
  "bound_at": "...",
  "last_reconciled_at": "..."
}
~~~

Only Agent-Workflow IDs and generation are durable authority. Herdr identifiers are replaceable host bindings.

## Target steering path

Current complexity:

~~~
AW message
 -> delivery policy
 -> control file OR external-host queue
 -> host poll
 -> report delivery
 -> worker ack
~~~

Target:

~~~
AW persist message
 -> resolve current Herdr binding generation
 -> herdr agent prompt
 -> record transport outcome
 -> worker separately reports semantic ack when required
~~~

Transport success remains distinct from semantic application.

## Target supervision path

Current normal path uses several signals:

- runner PID;
- executor PID;
- /proc;
- heartbeat;
- log growth;
- executor-event growth;
- permission journal;
- semantic progress.

Target normal path:

~~~
Herdr working
  -> active

Herdr blocked
  -> durable attention observation

Herdr idle/done
  -> reconcile completion evidence

Herdr unknown
  -> record uncertain host observation, do not infer completion

binding missing
  -> reconcile host replacement/exit against AW lifecycle

semantic-progress stale
  -> policy may nudge/escalate, but live process archaeology is not required
~~~

## Workflow-engine acceptance criteria

Any third-party workflow engine considered for authoritative scheduling must prove:

- deterministic node identity;
- exact dependency semantics;
- append-only or equivalently auditable transition history;
- idempotent duplicate event/reaction handling;
- restart/replay;
- no completion inference from prose;
- exact artifact/revision references;
- clean separation between host state and workflow state;
- ability to keep AW acceptance outside the engine;
- bounded retry semantics;
- human gate support;
- license compatibility;
- stable enough public API for a core dependency.

If none satisfies this list, the fork retains a smaller scheduler.

## UX integration principle

The fork should publish small read-only projections suitable for existing plugins rather than create new TUIs.

Preferred examples:

- Dagr-compatible DAG/run projection;
- reviewr worktree/revision launch action;
- Herdr sidebar metadata for run/acceptance state;
- standard Herdr notifications pointing to durable AW attention records.

## Final ownership rule

When deciding whether a feature belongs in the fork, ask:

1. Does it change durable workflow truth?
2. Does it authorize a transition?
3. Does it bind exact provenance/evidence?
4. Does it need to survive host replacement?
5. Would losing the plugin change whether the work is accepted?

If the answer is no to all five, it probably belongs in Herdr or a plugin, not Agent-Workflow.
