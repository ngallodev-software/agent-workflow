# Herdr Ecosystem and Prior-Art Assessment

Status: research baseline for the Herdr-centered Agent-Workflow fork  
Date: 2026-09-22  
Scope: Herdr core capabilities, public Herdr plugins, adjacent Herdr-oriented workflow projects, and overlapping orchestration/evidence systems.

## 1. Executive finding

The Herdr ecosystem already covers far more of Agent-Workflow's current runtime and operator surface than the existing Agent-Workflow Herdr backlog assumed.

The new repository should not begin by porting the current host/runtime implementation. It should begin by preserving only the governance/evidence invariants and proving which existing Herdr projects can supply the remaining execution, workflow, review, progress, notification, routing, and worktree capabilities.

The market/ecosystem is especially strong in:

- launching and observing coding agents;
- multi-agent workflow execution;
- review loops;
- project/thread coordination;
- worktree creation/setup;
- diff review;
- agent progress;
- notification/mobile surfaces;
- agent routing;
- handoff and session continuity;
- DAG visualization.

The strongest remaining Agent-Workflow differentiation appears to be:

- immutable Agent Run and execution contracts;
- exact source provenance;
- sealed/content-addressed evidence;
- exact revision/artifact binding;
- deterministic lifecycle/replay/idempotence;
- strict completion != evaluation != review != acceptance separation;
- evaluation and benchmark receipts;
- bounded semantic decision seams;
- durable acceptance/rejection authority.

Even this remaining space has close prior art. XiaoConstantine/herdr-workflow is a particularly important comparator because its specification independently converges on event-sourced reducers, immutable typed artifacts, exact Git-object review, human gates, deterministic restart, and publication authorization.

The fork must therefore prove its distinct scope before implementing a new workflow engine.

## 2. Research method

The search included:

1. Herdr core CLI/plugin/event/worktree/machine capabilities.
2. GitHub repositories tagged with the public herdr-plugin topic.
3. Herdr-oriented projects that are not native plugins but drive Herdr.
4. Workflow, orchestration, review, routing, progress, notification, worktree, and handoff searches.
5. Direct README/spec/manifest review for the closest candidates.

Approximately one hundred public repositories surfaced under the herdr-plugin topic during this pass. The projects below are the ones with material overlap.

This is an architectural prior-art review, not a security audit. Before adopting any dependency, the fork must separately verify:

- license;
- release/tag history;
- maintainer activity;
- dependency chain;
- security posture;
- supported Herdr versions;
- test coverage;
- cross-platform behavior;
- actual behavior against the installed Herdr version.

## 3. Herdr core: capabilities we should not reimplement

Herdr itself already supplies the execution primitives around which the fork should be built:

- workspace/tab/pane topology;
- raw pane command execution;
- supported coding-agent detection;
- unique live agent names;
- agent start;
- prompt submission;
- wait for working/blocked/settled state;
- agent read/get;
- blocked-state detection;
- focus/navigation;
- machine/SSH routing;
- worktree operations;
- plugin actions/panes/events/startup hooks;
- socket event subscriptions.

Herdr's live agent states include idle, working, blocked, done, and unknown.

Herdr's plugin model supports executable plugin packages with:

- build steps;
- startup hooks;
- actions;
- panes;
- events;
- invocation context;
- plugin-owned config/state directories.

Important limitation: Herdr event subscription is a live stream, not durable replay. Agent-Workflow must therefore never make correctness depend solely on receiving every Herdr event. Host events may accelerate reconciliation; durable Agent-Workflow state remains replay authority.

Important limitation: Herdr plugin startup hooks are initialization hooks rather than a supervised daemon abstraction. A long-lived process remains plugin-owned.

## 4. Highest-priority workflow/orchestration comparators

### 4.1 XiaoConstantine/herdr-workflow

Repository:
https://github.com/XiaoConstantine/herdr-workflow

Status observed:
Draft v0.7; M1 runtime implementation in progress.

License:
The reviewed README states that no license has been selected. Treat the project as architectural prior art only until licensing changes. Do not copy source.

Why it matters:

This is the closest architectural comparator found.

Its specification describes:

- composable workflow stages;
- deterministic reducers;
- event-sourced state transitions;
- typed immutable artifacts;
- exact digests and Git object IDs;
- stable principals and role separation;
- artifact provenance;
- deterministic downstream invalidation;
- restart/recovery;
- human gates;
- publication authorization;
- sequential dependency-ordered implementation;
- adversarial exact-object review;
- final whole-change integration review;
- idempotent external side-effect reconciliation.

Its own stated boundary is also similar: Herdr supplies agent/pane/worktree/wait/notification APIs while the companion supplies workflow semantics, artifacts, reducers, scheduler, human UI, outbox, and publisher.

Overlap with Agent-Workflow:
Very high.

Potential use:
Formal comparator; possible future collaboration/adoption if licensing, implementation maturity, and semantics align.

Required spike:
Implement the same minimal journey in both designs:

~~~
frozen source
 -> implement
 -> typed completion
 -> exact-object review
 -> rejection/retry
 -> approval
 -> final human acceptance
 -> restart/replay
~~~

Compare invariant coverage, code size, host coupling, and recovery behavior.

Disposition:
DO NOT duplicate blindly. Gate the new scheduler architecture on this comparison.

### 4.2 vekexasia/pi-extensible-workflows

Repository:
https://github.com/vekexasia/pi-extensible-workflows

Observed capabilities:

- deterministic/resumable multi-agent workflows;
- parallel();
- pipeline();
- withWorktree();
- checkpoint();
- persistent named agent handles;
- send/steer/stop/retry;
- packaged reviewer/developer/scout/oracle/researcher roles;
- reviewLoop starter;
- trajectory/Gantt visualization;
- workflow reports;
- Herdr companion package for workflow-agent sessions in panes.

Strength:
Mature and feature-rich.

Constraint:
Pi-centric runtime/extension model. Trusted host code has filesystem/process access.

Overlap:
High for workflow composition, subagent orchestration, worktree isolation, review loops, progress/trajectory, and resumability.

Potential use:
Reference implementation and possibly an execution engine when Pi is acceptable; less suitable as the sole core dependency if Agent-Workflow must remain equally native across Codex/Claude/Pi/OpenCode.

Disposition:
COMPARE; do not rebuild equivalent generic workflow helpers until the integration cost is measured.

### 4.3 aorumbayev/herdr-workflows

Repository:
https://github.com/aorumbayev/herdr-workflows

Observed capabilities:

- native Herdr plugin;
- short YAML workflows;
- run step;
- agent step;
- Herdr API step;
- nested workflow step;
- starts coding agents, sends prompt, waits;
- workflow history and console;
- Herdr pane integration.

Strength:
Simple, direct, Herdr-native execution layer.

Constraint:
Primarily linear workflow semantics compared with Agent-Workflow's stronger evidence/review lifecycle.

Overlap:
High with simple task dispatch and command/agent composition.

Potential use:
Could replace a large class of simple workflow execution paths if Agent-Workflow retains only governance around them.

Disposition:
INTEGRATION CANDIDATE for simple execution; not currently a substitute for sealed evidence/acceptance.

### 4.4 andthezhang/herdr-dynamic-workflow

Repository:
https://github.com/andthezhang/herdr-dynamic-workflow

Observed capabilities:

- JavaScript workflow dialect;
- agent(), parallel(), pipeline(), phase(), log();
- budget handling;
- verify;
- judgePanel;
- loopUntilDry;
- completenessCheck;
- retry;
- gate;
- checkpoint;
- agent kind/model/effort/isolation;
- Herdr-backed local agents;
- SSH execution;
- schema-checked output;
- journal replay;
- blocked-agent policy;
- local worktree isolation;
- resume by run ID.

Overlap:
Very high with generic workflow execution and retry/gate mechanics.

Constraint:
A script-oriented workflow runtime permits more executable workflow logic than Agent-Workflow's current preference for bounded registered semantics. Worktree isolation over SSH and detached runs were not implemented in the reviewed README.

Potential use:
Strong comparator for whether Agent-Workflow needs its own workflow language/runtime at all.

Disposition:
COMPARE; likely reuse for flexible workflows only if deterministic authority can remain outside the script.

### 4.5 cyperx84/herdr-loop

Repository:
https://github.com/cyperx84/herdr-loop

Observed capabilities:

- declarative event-driven agent loops;
- implementation/review/gate/retry/convergence patterns;
- multiple coding-agent kinds;
- Herdr push-event integration;
- real convergence examples;
- blocked-agent handling;
- result routing.

Status observed:
Early project; searched material indicated no stable tagged release at the time of research.

Overlap:
High with iterative review and remediation loops.

Potential use:
Reference implementation for event-driven convergence.

Disposition:
REFERENCE/COMPARE; do not make core dependency until maturity is stronger.

### 4.6 mikhail-angelov/herdr-review-loop

Repository:
https://github.com/mikhail-angelov/herdr-review-loop

Observed capabilities:

- author/reviewer loop;
- heterogeneous agent kinds;
- repeated review until clean, budget stop, or stuck;
- durable review summaries/history;
- blocked/timeout handling;
- nonzero outcome when convergence does not succeed.

Overlap:
Directly overlaps Agent-Workflow's iterative review/remediation UX.

Constraint:
A review-loop outcome is not equivalent to Agent-Workflow's exact revision-bound review/acceptance authority.

Disposition:
USE AS UX/LOOP PRIOR ART; retain exact-object authority in the evidence kernel.

### 4.7 eliasstravik/herdr-projects

Repository:
https://github.com/eliasstravik/herdr-projects

Observed capabilities:

- one coordinator conversation;
- parallel worker threads;
- one branch/worktree per task;
- shared standing instructions and memory;
- coordinator inbox;
- ready-for-review/waiting/working/landing groups;
- pull-request follow-up;
- scheduled routines;
- background ticker;
- remote threads through saved Herdr SSH machines;
- adoption of already-running agent panes;
- reports copied home from remote workers.

Architectural pattern:

The coordinator is an ordinary agent. Deterministic code performs mechanics. Files are the durable record; prompts are nudges.

That is very close to the simplification goal for Agent-Workflow.

Important limitation:
The project explicitly documents its safety settings as soft. Same-user agents can modify shared state or impersonate a human/coordinator through host channels. It is intentionally a productivity system rather than a cryptographic acceptance authority.

Overlap:
Very high with delegation, thread management, worktrees, coordinator inboxes, status grouping, remote workers, and scheduled progression.

Potential use:
Strong prior art for deleting or greatly reducing Agent-Workflow's orchestrator inbox, project supervision, and thread UX.

Disposition:
COMPARE. Do not rebuild project/thread UX unless the evidence kernel needs a missing invariant.

## 5. Review and human-feedback prior art

### 5.1 persiyanov/herdr-reviewr

Repository:
https://github.com/persiyanov/herdr-reviewr

Observed capabilities:

- persistent review pane bound to a worktree;
- uncommitted, branch, last-turn, and commit diff scopes;
- syntax-highlighted diff;
- line/range comments;
- comments sent back to agent input;
- file browser and search;
- read-only PR view;
- auto-open on Herdr worktree creation/open;
- does not edit the worktree.

Overlap:
Interactive review presentation.

What it does not replace:
Agent-Workflow review records, review independence policy, exact subject revision, evaluation gates, or acceptance.

Disposition:
PREFERRED UI INTEGRATION. Do not build a custom diff-review TUI in the fork without a documented gap.

### 5.2 JonasBaeumer/herdr-file-annotator

Repository:
https://github.com/JonasBaeumer/herdr-file-annotator

Observed use:
Structured line-anchored comments such as fix/verify/question/nit sent to agents.

Overlap:
Human review/steering annotation.

Disposition:
Evaluate alongside reviewr. Prefer one interoperable UI adapter rather than duplicating annotation UI.

### 5.3 Idan-Levin/herdr-implement-review

Repository:
https://github.com/Idan-Levin/herdr-implement-review

Observed pattern:
Mother/coordinator agent, implementation agent, security/review agent, evidence retained in plugin state, and explicit coordinator acceptance/remediation.

Overlap:
Useful conceptual prior art for keeping scan/review completion separate from acceptance.

Disposition:
REFERENCE.

## 6. DAG/status visualization prior art

### 6.1 aemrebarut/herdr-dagr

Repository:
https://github.com/aemrebarut/herdr-dagr

Observed capabilities:

- live DAG visualization;
- attempts and retries remain visible;
- gates and loops;
- dependency-ready/waiting display;
- evidence tiers;
- operator steering;
- producer-owned run file;
- renderer explicitly does not become a workflow engine.

This is unusually well aligned with Agent-Workflow's desired boundary.

Potential integration:
Expose a read-only Agent-Workflow run projection compatible with Dagr rather than building an Agent-Workflow-specific dashboard.

Disposition:
HIGH-PRIORITY UI INTEGRATION CANDIDATE.

## 7. Live event history and progress prior art

### 7.1 waynewu411/herdr-event-log

Repository:
https://github.com/waynewu411/herdr-event-log

Observed purpose:
Persist Herdr agent-status events in an append-only log because the native subscription is live-only and does not provide historical replay.

Overlap:
Host-event history currently approximated by Agent-Workflow health/process journals.

Potential use:
Either use this plugin or adopt its architectural pattern for host observation. Do not confuse its host-event history with Agent-Workflow workflow authority.

Disposition:
HIGH-VALUE REFERENCE/OPTIONAL DEPENDENCY.

### 7.2 eliasstravik/herdr-agent-progress

Repository:
https://github.com/eliasstravik/herdr-agent-progress

Observed capabilities:

- progress estimate and current activity in sidebar;
- stale progress marking;
- local DB;
- verified session resume;
- Codex/Claude integration.

Overlap:
Progress/attention UX.

Disposition:
USE PLUGIN; do not rebuild progress dashboard.

### 7.3 ragamo/herdr-flock

Repository:
https://github.com/ragamo/herdr-flock

Observed capability:
Visualizes Herdr working/blocked/done/idle state and keeps session history.

Architectural value:
Confirms that Herdr's state stream is already sufficient for third-party lifecycle visualization.

Disposition:
UI/reference only.

## 8. Routing prior art

### 8.1 nidhi-singh02/agent-router

Repository:
https://github.com/nidhi-singh02/agent-router

Observed capabilities:

- local-first routing among Cursor, Claude Code, Codex, and OpenCode;
- quota-aware deterministic eligibility;
- reserve policies;
- TypeSafe ranking after fixed filters;
- model and reasoning-effort selection;
- launches chosen agent in Herdr;
- uses subscription logins rather than provider API keys;
- local decision/session history.

Overlap:
Extremely relevant to Agent-Workflow's current runtime aliases, role bindings, model selection, no-go policies, and TypeSafe routing seams.

Difference:
Agent-Workflow's logical role and immutable execution contract still need to bind the resolved routing decision for audit/reproducibility.

Potential architecture:

~~~
AW role/policy
  -> deterministic constraints
  -> optional Agent Router decision
  -> freeze resolved execution choice in Agent Run
  -> Herdr launch
~~~

Disposition:
HIGH-PRIORITY INTEGRATION/COMPARISON. Do not retain a second general-purpose model router without proving a gap.

## 9. Blocked-agent and remediation prior art

### 9.1 0xGosu/herdr-auto-pilot

Repository:
https://github.com/0xGosu/herdr-auto-pilot

Observed capabilities:

- watches agent sessions;
- detects approval/questions/errors/stalls;
- learned rules from human decisions;
- explicit task sources;
- optional LLM helper;
- confidence thresholds;
- never-auto patterns;
- kill switch;
- runaway-loop guard;
- retry ceiling;
- audit trail.

Overlap:
Agent-Workflow supervisor/remediation and attention handling.

Risk:
Automated answers to approval/question interfaces can cross authority boundaries. This must not become acceptance or security authority.

Disposition:
OPTIONAL OPERATOR TOOL only. Useful prior art for bounded remediation, not part of Agent-Workflow correctness.

## 10. Agent-team and subagent prior art

### 10.1 caioniehues/herdmates

Repository:
https://github.com/caioniehues/herdmates

Observed architecture:
Claude Code native agent teams retain ownership of spawn/mailboxes/membership/lifecycle. Herdmates maps those native teammates into real Herdr panes and records documented team events rather than reimplementing the team system.

Architectural lesson:
When an agent platform already supplies a coherent team primitive, the host integration should project it rather than implement a competing hidden team engine.

Disposition:
REFERENCE. The Agent-Workflow fork should remain compatible with native team systems as execution providers.

### 10.2 EDMND-SRC/herdr-subagents

Repository:
https://github.com/EDMND-SRC/herdr-subagents

Observed capabilities:

- OpenCode plugin rather than native Herdr plugin;
- creates panes for subagents;
- delegation tools;
- wait/status/close;
- automatic layout;
- orphan sweep;
- dynamic grid.

Overlap:
Subagent presentation and host lifecycle.

Disposition:
REFERENCE; reinforces that Agent-Workflow should not own terminal layout.

## 11. Session handoff prior art

### 11.1 sanirudh17/herdr-agent-handoff

Repository:
https://github.com/sanirudh17/herdr-agent-handoff

Observed capabilities:

- handoff current task to a fresh session of another agent kind;
- focused summary or full transcript mode;
- transcript SHA-256/path reference when large;
- fails closed if source session cannot be uniquely resolved;
- preserves source pane;
- detects installed agent launchers;
- cross-agent session continuity.

Overlap:
Retry/resume/context-transfer UX.

Difference:
Agent-Workflow retry lineage is durable workflow identity, not merely conversational handoff.

Disposition:
USE/REFERENCE for operator session transfer; avoid duplicating transcript handoff machinery.

## 12. Worktree and workspace prior art

### 12.1 tdi/herdr-worktree-setup

Repository:
https://github.com/tdi/herdr-worktree-setup

Observed capabilities:

- worktree.created event hook;
- per-repository setup steps;
- environment/direnv/mise/dependency initialization;
- logs;
- sidebar setup status.

Disposition:
USE FOR WORKTREE BOOTSTRAP UX. Agent-Workflow should not implement repo-specific setup scripts.

### 12.2 tdi/herdr-worktree-from-linear

Repository:
https://github.com/tdi/herdr-worktree-from-linear

Observed capabilities:

- choose Linear issue;
- create/open worktree;
- issue-derived branch;
- optional issue context pane;
- worktree metadata token.

Disposition:
REFERENCE/OPTIONAL. Ticket-to-worktree UX does not belong in the Agent-Workflow core.

### 12.3 cloudmanic/herdr-plus

Repository:
https://github.com/cloudmanic/herdr-plus

Observed capabilities:

- project templates;
- workspace layouts;
- worktree opening;
- per-tab/pane directories;
- quick actions;
- automatic worktree layouts.

Disposition:
USE/REFERENCE for workspace UX.

### 12.4 other worktree plugins screened

Examples:

- eightHundreds/herdr-worktreeinclude;
- jlimas/herdr-worktree-seed;
- zerodice0/herdr-plugin-worktree-bootstrap;
- razajamil/herdr-plugin-workspace-manager.

These reinforce the same boundary: Agent-Workflow should retain source-provenance verification but not own generic worktree setup/presentation.

## 13. GitHub/PR prior art

### 13.1 wyattjoh/herdr-plugin-gh-pr

Repository:
https://github.com/wyattjoh/herdr-plugin-gh-pr

Observed capabilities:

- PR status in Herdr sidebar;
- CI state;
- refresh/open PR actions;
- worktree-aware refresh.

Disposition:
USE/REFERENCE for PR presentation; Agent-Workflow need not build sidebar PR status.

### 13.2 ogulcancelik/herdr-plugin-github-start

Repository:
https://github.com/ogulcancelik/herdr-plugin-github-start

Observed capabilities:

- find/resume named Pi/Codex/Claude sessions;
- GitHub issue/PR target naming;
- focus live session or resume saved one;
- start new agent in Herdr.

Disposition:
REFERENCE for session discovery/resume and GitHub-target UX.

### 13.3 kkckkc/herdr-plugin-gh-workflow

Repository:
https://github.com/kkckkc/herdr-plugin-gh-workflow

Screened as a GitHub/workflow-specific Herdr plugin.

Disposition:
REFERENCE; inspect further if GitHub Actions or PR workflow enters fork scope.

## 14. Task-board prior art

### 14.1 smarzban/tsk

Repository:
https://github.com/smarzban/tsk

Observed capabilities:
Shared human/agent task board, TUI and CLI. Its roadmap includes assigning tasks to agents and Herdr worktree execution.

Disposition:
DO NOT build a generic task-board UI in Agent-Workflow.

### 14.2 miiraheart/herdr-beads

Repository:
https://github.com/miiraheart/herdr-beads

Observed capabilities:
Herdr UI around Beads task/issue state, including status columns and deterministic CLI writes.

Disposition:
Task tracking integration/reference only.

## 15. Notifications and remote attention prior art

Projects screened include:

- dcolinmorgan/herdr-remote;
- 0cv/herdr-mobile-relay;
- dot/herdr-terminal-notifier;
- donghaolicd/herdr-teams-notify;
- yankewei/herdr-focus-notify;
- permgps/herdr-telegram-agents;
- Unayung/herdr-watch;
- cobanov/herdr-ntfysh (archived).

### dcolinmorgan/herdr-remote

Observed scope:
Remote monitoring/approval from mobile/menu-bar/Telegram using Herdr agent-state events.

### Unayung/herdr-watch

Observed scope:
Apple Watch/mobile bridge, Herdr roster and state, push on blocked/done, screen tail and limited input, with Claude hooks supplying richer prompt-option detail.

Important lesson:
Herdr owns generic agent state; agent-specific hooks can enrich it where needed.

Disposition for category:
DO NOT build an Agent-Workflow notification framework. Emit durable attention state and let Herdr/plugins present or relay it.

## 16. Usage/cost prior art

Projects screened:

- Davidcreador/herdr-token-dashboard;
- levi-qiao/herdr-agent-usage;
- senna-lang/herdr-agent-usage.

These already provide local Herdr-side model/token/cost visibility.

Agent-Workflow may still need sealed provider accounting for benchmark/evaluation receipts, but should not build a duplicate operator dashboard.

Disposition:
KEEP ACCOUNTING EVIDENCE; OUTSOURCE DISPLAY.

## 17. Sandbox/isolation prior art

### madarco/agentbox / agentbox-herdr-plugin

Observed capability:
AgentBox environments/boxes exposed through Herdr plugin actions and panes.

Potential relevance:
A future hardened Agent-Workflow profile could execute workers in stronger isolation than ordinary same-user Herdr panes.

Disposition:
FUTURE SECURITY SPIKE. Do not make core dependency during initial fork.

## 18. Capability ownership matrix

| Capability | Existing supply | Target decision |
| --- | --- | --- |
| terminal layout | Herdr core | Herdr |
| coding-agent start | Herdr core | Herdr |
| live agent state | Herdr core | Herdr |
| prompt/wait/read | Herdr core | Herdr |
| remote machine routing | Herdr core | Herdr |
| host events | Herdr core | Herdr |
| durable host-event history | herdr-event-log pattern | plugin/adapter |
| worktree UI | Herdr core + plugins | Herdr/plugins |
| worktree setup | worktree-setup etc. | plugin |
| source provenance | Agent-Workflow | Agent-Workflow |
| model/account routing | agent-router | compare/integrate |
| simple linear workflow | herdr-workflows | integrate when sufficient |
| dynamic workflow scripting | herdr-dynamic-workflow | compare |
| resumable Pi workflows | pi-extensible-workflows | compare |
| project/thread coordinator | herdr-projects | compare |
| review/convergence loops | herdr-loop/review-loop | compare/integrate |
| workflow event-sourced authority | XiaoConstantine/herdr-workflow | critical comparator |
| DAG visualization | herdr-dagr | plugin |
| diff review UI | reviewr/file-annotator | plugin |
| progress UI | agent-progress | plugin |
| notifications/mobile | multiple plugins | plugin |
| session handoff | herdr-agent-handoff | plugin |
| task board | tsk/beads | plugin |
| PR sidebar | gh-pr | plugin |
| token dashboard | token/usage plugins | plugin |
| immutable Agent Run contract | Agent-Workflow | retain |
| exact source baseline | Agent-Workflow | retain |
| sealed evidence/receipts | Agent-Workflow | retain unless stronger compatible prior art adopted |
| eval/review/accept separation | Agent-Workflow | retain |
| benchmark/evaluation receipts | Agent-Workflow | retain |
| exact acceptance revision | Agent-Workflow | retain |
| deterministic replay/idempotence | Agent-Workflow + close prior art | retain or integrate only after proof |

## 19. Features the fork should presume deleted until justified

The fork should start with a presumption against custom implementation of:

- terminal/pane/workspace management;
- coding-agent subprocess ownership;
- PID/process-group supervision;
- heartbeat-based coding-agent liveness;
- host-side live agent-name leasing;
- control-file steering;
- generic notifications;
- mobile notification relays;
- diff viewer;
- progress dashboard;
- generic project/task board;
- worktree setup scripts;
- generic workflow DSL;
- generic reviewer/author loop;
- model/account router;
- token/cost dashboard;
- session handoff implementation.

A feature may return only when a required Agent-Workflow invariant cannot be achieved through Herdr or a suitable plugin.

## 20. Features that still appear worth preserving

The initial keep set is intentionally small.

### Core identity and provenance

- Agent Run ID;
- task/run lineage;
- immutable launch/delegation contract;
- source baseline;
- worktree revision verification;
- dirty-baseline authorization.

### Durable workflow authority

- deterministic dependency eligibility;
- idempotent child binding;
- replay-safe transitions;
- retry lineage;
- human approval gates where policy requires them.

Whether Agent-Workflow implements the scheduler directly remains open pending the workflow-engine gate.

### Evidence

- typed completion evidence;
- exact changed-revision identity;
- command/check evidence;
- criteria results;
- content hashes;
- final receipt;
- evidence sealing.

### Evaluation and decision policy

- deterministic criteria;
- evaluation result;
- comparative evaluation;
- benchmark receipts;
- TypeSafe/Jev decisions only at registered semantic seams;
- decision audit.

### Review and acceptance

- independent review identity/policy;
- exact subject revision;
- reviewed vs accepted distinction;
- accept/reject history;
- accepted revision derived from sealed evidence.

## 21. Adoption rules

A third-party Herdr component can replace Agent-Workflow functionality only when:

1. the license permits the intended use;
2. the project has enough release/test maturity for its role;
3. failure modes are understood;
4. the integration does not transfer Agent-Workflow authority accidentally;
5. the state can be reconciled after restart;
6. external identifiers are treated as bindings/projections, not durable Agent Run identity;
7. the dependency can be removed/replaced without invalidating sealed Agent-Workflow evidence.

UI plugins may be accepted under a lower bar because they are non-authoritative.

Workflow engines and routing components require a much higher bar.

## 22. Recommended evaluation order

1. Herdr core live capability tests.
2. XiaoConstantine/herdr-workflow architecture/maturity/license comparison.
3. Herdr Projects comparison against current orchestrator inbox/supervisor.
4. Herdr Workflows and Dynamic Workflow comparison for execution DSL.
5. Pi Extensible Workflows comparison if Pi-neutrality can be preserved.
6. Reviewr integration spike.
7. Dagr projection spike.
8. Agent Router routing-policy spike.
9. Herdr event-log/restart observation spike.
10. Optional notification/progress integrations.

## 23. Research conclusion

The ecosystem search changes the overhaul from a simple “replace Agent-Workflow's runner with Herdr” project into a broader reduction exercise.

The appropriate default is:

> Build only the durable governance/evidence functionality for which the ecosystem does not already provide a compatible authority.

Everything else should be an adapter, plugin integration, or deleted feature.

The next architectural deliverable must therefore be an ADR choosing between:

- reduced Agent-Workflow scheduler + Herdr execution;
- existing Herdr workflow engine + Agent-Workflow evidence kernel;
- event-sourced Herdr workflow prior art adopted/contributed to, with Agent-Workflow evaluation extensions;
- or a hybrid where Agent-Workflow is primarily a governance/evidence plugin around Herdr's existing workflow ecosystem.
