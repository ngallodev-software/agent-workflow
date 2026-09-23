# DEC-010 — Fork Agent-Workflow into a Herdr-Centered Replacement

- **Status:** decided
- **Date:** 2026-09-22
- **Decision owner:** project maintainer
- **Source baseline:** Agent-Workflow 0.11.6 at 63627e6ec73fa62c18da64ffc38c5189cced6458
- **Target repository working name:** ngallodev-software/agent-workflow-herdr

## Context

Agent-Workflow was deliberately designed as a host-independent workflow authority. During its development it also accumulated substantial machinery for launching coding-agent processes, constructing executor commands, tracking process groups, inferring liveness, delivering live steering, maintaining host bindings, and supervising workers.

Herdr has since matured into an execution fabric with:

- supported coding-agent start/control;
- live agent identity and lifecycle states;
- prompt/wait/read operations;
- workspace/tab/pane management;
- remote-machine routing;
- worktree support;
- plugin actions, panes, and events.

The Herdr plugin ecosystem additionally contains implementations for workflow execution, project/thread coordination, review loops, diff review, DAG visualization, progress display, model routing, notifications, worktree setup, and agent handoff.

Continuing to expand Agent-Workflow's host/runtime layer would create duplicate authority and duplicate infrastructure.

A separate repository is preferable to an in-place rewrite because the current 0.11.x implementation remains a valuable stable/reference line while the replacement deletes compatibility surfaces aggressively.

## Decision

Create a new repository from the Agent-Workflow 0.11.6 history and redesign the normal execution path around Herdr.

The replacement architecture adopts these boundaries:

### Herdr owns live execution

Herdr is the normal authority for:

- coding-agent process/session launch;
- live agent naming;
- pane/workspace placement;
- prompt transport;
- agent wait/read/status;
- blocked-state observation;
- focus/navigation;
- remote-machine transport;
- live terminal/process control.

Agent-Workflow does not maintain a parallel PID/process-group/terminal model for normal Herdr workers.

### Agent-Workflow owns durable governance

Agent-Workflow remains the authority for:

- Agent Run identity;
- immutable contracts;
- source provenance;
- durable workflow policy;
- exact artifact/revision identity;
- completion contracts;
- evaluation evidence;
- review records;
- acceptance/rejection;
- sealed receipts;
- replay/idempotence;
- benchmark/evaluation receipts;
- registered semantic decision policy.

### Existing Herdr plugins are preferred for non-authoritative UX

Before implementing a user-interface or generic workflow feature, the project must evaluate relevant existing Herdr plugins.

In particular the project should presume reuse/integration for:

- diff/review UI;
- DAG visualization;
- progress display;
- notifications/mobile relay;
- worktree setup/layout;
- task/project boards;
- session handoff;
- token/cost dashboards.

### Workflow scheduling remains an open subdecision

This decision does **not** commit the fork to porting the current Agent-Workflow scheduler.

Before implementing a workflow engine, the project must compare its remaining requirements against existing Herdr workflow systems, especially:

- XiaoConstantine/herdr-workflow;
- vekexasia/pi-extensible-workflows;
- aorumbayev/herdr-workflows;
- andthezhang/herdr-dynamic-workflow;
- cyperx84/herdr-loop;
- eliasstravik/herdr-projects.

The fork may retain a reduced scheduler, adapt an existing engine, or become primarily a governance/evidence layer around an existing engine.

## Consequences

### Positive

- Removes duplicate live-execution authority.
- Eliminates most need for PID/PGID/process supervision.
- Eliminates normal control-file steering.
- Reduces executor/provider launch code.
- Makes remote execution a Herdr concern.
- Makes the product boundary easier to explain.
- Allows existing Herdr plugins to provide richer UX without expanding the core.
- Preserves the strongest Agent-Workflow differentiators.
- Enables independent benchmarking against the existing 0.11.x implementation.

### Negative

- Herdr becomes a required platform for the normal replacement path.
- The replacement cannot claim the original core's “runs with no interactive runtime host installed” property unless an optional headless backend is retained.
- Herdr API/version compatibility becomes a platform dependency.
- Some current tests and schemas become obsolete rather than migratable.
- Existing prompt packs/tooling will need a compatibility review.
- A smaller core increases the importance of clear authority boundaries with third-party plugins.

## Rejected alternatives

### Continue evolving the current repository in place

Rejected because removal and compatibility work would remain interleaved. It would be difficult to tell whether complexity is genuinely gone or only hidden behind compatibility paths.

### Embed Herdr directly throughout the existing core

Rejected because host identifiers and plugin behavior must remain replaceable bindings rather than durable workflow identity.

### Keep the full headless runtime and merely add a Herdr adapter

Rejected as the default architecture because it preserves two execution stacks and much of the complexity this overhaul is intended to remove.

An optional headless compatibility backend may be retained only if CI, benchmark, or deployment requirements justify it.

### Replace all Agent-Workflow workflow/evidence semantics with generic Herdr workflows immediately

Rejected pending comparison. Existing workflow projects overlap heavily, but not all have demonstrated the exact provenance, sealed evidence, replay, independent review, and acceptance semantics required by Agent-Workflow.

## Required follow-up decisions

1. Herdr minimum supported version.
2. Workflow engine: retain, integrate, or contribute/adopt.
3. Model/account routing ownership.
4. Host-event persistence strategy.
5. Whether an optional headless backend survives.
6. Whether the SQLite projection and MCP read adapter remain useful.
7. Which review/DAG/progress plugins receive first-class integration adapters.

## Evidence required before implementation cutover

- live Herdr capability receipt;
- workflow-engine comparison;
- license/maturity review of dependencies;
- one end-to-end Herdr Agent Run;
- restart/rebind journey;
- exact-revision review/accept journey;
- comparative benchmark against 0.11.6.

## References

- docs/HERDR_OVERHAUL_MASTER_PLAN.md
- docs/HERDR_PRIOR_ART.md
- docs/HERDR_CAPABILITY_MATRIX.md
- docs/NEW_REPOSITORY_BOOTSTRAP.md
