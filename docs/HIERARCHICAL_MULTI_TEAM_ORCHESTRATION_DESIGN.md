# Hierarchical multi-team orchestration design

## Executive summary

This design adds one orchestration level above the current orchestrator-to-agent model:

```text
root orchestrator
  ├── team lead: implementation
  │     ├── implementation agent A
  │     ├── implementation agent B
  │     └── test agent
  ├── team lead: architecture
  │     ├── research agent
  │     └── design-review agent
  └── team lead: verification
        ├── integration agent
        ├── security agent
        └── release/drift agent
```

The root orchestrator may create a new tmux session or a new window in an existing managed session. Each new window is owned by one **team lead**, which acts as a scoped orchestrator and creates its own worker panes. Communication is durable and replayable at every boundary. tmux panes, windows, `wait-for`, and terminal notifications are projections and wake hints, never authority.

The design intentionally reuses the repository's existing strengths: append-only JSONL evidence, orchestrator registries and inboxes, launch contracts, workflow snapshots and receipts, isolated worktrees, pane identity, and canonical session launch. It does not introduce a second scheduler or a separate message bus.

## Goals

1. Let one root orchestrator delegate bounded subgraphs to multiple team leads.
2. Give each team lead a separate terminal workspace and a stable tmux window identity.
3. Let a team lead launch and supervise worker agents in panes without granting it unbounded root authority.
4. Support bidirectional root ↔ team-lead and team-lead ↔ worker communication with restart-safe replay.
5. Preserve a complete lineage from root objective through team assignment, worker runs, reviews, approvals, and final receipt.
6. Allow root-level fan-out and fan-in across teams while preserving existing per-workflow parallelism and safety limits.
7. Keep the architecture single-host and tmux-first now, while making the durable protocol transport-neutral for a future remote host adapter.

## Non-goals

- Arbitrary recursive orchestration depth. Version 1 supports exactly three authority tiers: root orchestrator, team lead, worker.
- Allowing team leads to mutate root workflow state directly.
- Treating terminal text, pane existence, or process liveness as completion.
- Replacing prompt packs, workflow snapshots, or canonical session services.
- Introducing Redis, NATS, a daemon, or multi-host scheduling in the first implementation.
- Giving child agents direct authority to create sibling teams.

## Terminology and authority tiers

| Tier | Principal | Owns | May create | May not do |
|---|---|---|---|---|
| 0 | root orchestrator | root plan, team budget, cross-team dependencies, global acceptance | team-lead windows/sessions | edit a team's journal directly; infer success from tmux |
| 1 | team lead | one delegated team assignment and bounded child workflow | worker panes/runs within its allocation | create another team lead; exceed delegated scope/budget; accept global outcome |
| 2 | worker agent | one ticket/assignment and its evidence | no orchestration children | alter team/root registries or workflow authority |

A principal's capabilities come from an immutable launch/delegation contract, not from a role string alone.

## Current-state fit and identified gaps

The current source already provides:

- canonical tmux pane creation and pane metadata in `tmux.py`;
- canonical session launch in `sessions.py`;
- an orchestrator registry and append-only aggregate inbox in `orchestrator_inbox.py`;
- session-scoped durable messages in `messages.py`;
- workflow snapshots, append-only events, reconciliation, and receipts;
- pane identity reliability and explicit source/worktree boundaries.

The existing implementation is principally shaped around one orchestrator window supervising direct child sessions. The missing abstractions are:

1. a durable **orchestration hierarchy** and parent/child orchestrator identity;
2. a canonical **team delegation contract**;
3. tmux **managed session/window** creation rather than pane-only launch;
4. a scoped team-lead runtime that can invoke canonical workflow/session services;
5. hierarchical message routing and acknowledgement across two inbox boundaries;
6. root-level team scheduling, budgets, reconciliation, and fan-in receipts;
7. operator commands that show the tree rather than a flat child registry.

## Architecture

### Control plane and presentation plane

```text
Durable control plane                           Local presentation plane
--------------------------------------------    ---------------------------
root hierarchy.json / hierarchy-events.jsonl    tmux managed session
root inbox.jsonl and action/ack journals          root window
team delegation contracts                         team-lead windows
team registries and inboxes                        worker panes
team workflow snapshots/events/receipts          pane titles/status/wake hints
worker run evidence and final receipts            optional external terminal window
```

The durable side is authoritative. The tmux side may be destroyed and reconstructed from durable state.

### Managed tmux topology

Preferred default:

```text
TMUX SESSION: aw-<root-id>

window 0: root
  pane 0: root orchestrator
  pane 1: tree/status dashboard (optional projection)

window 1: team-implementation
  pane 0: team lead
  pane 1..N: implementation/test workers

window 2: team-architecture
  pane 0: team lead
  pane 1..N: research/review workers

window 3: team-verification
  pane 0: team lead
  pane 1..N: integration/security/release workers
```

An operator may choose `--terminal-mode external-window`. In that mode, agent-workflow first creates the managed tmux session/window, then asks a configured terminal adapter to open a new terminal attached to the exact tmux target. The external terminal process is convenience only. The team continues if that terminal closes.

### New durable artifacts

Under the root orchestration directory:

```text
~/.local/state/agent-workflow/orchestrations/<hash>/
├── hierarchy.json                     # immutable identity/topology contract
├── hierarchy-events.jsonl             # authoritative team lifecycle journal
├── root-inbox.jsonl                    # imported team-lead events
├── root-actions.jsonl                  # root commands to teams
├── root-acknowledgements.jsonl
├── tmux-topology.json                  # mutable/rebuildable projection
├── teams/
│   └── <team-id>/
│       ├── delegation-contract.json    # immutable bounded authority
│       ├── registry.json               # team-lead registry
│       ├── inbox.jsonl                 # worker → team lead
│       ├── actions.jsonl               # team lead → worker
│       ├── acknowledgements.jsonl
│       ├── workflow-snapshot.json
│       ├── workflow-events.jsonl
│       ├── workflow-status.json        # projection
│       └── team-receipt.json           # immutable team fan-in seal
└── root-receipt.json                   # immutable cross-team seal
```

Existing worker run directories remain unchanged. The hierarchy references their canonical final receipts by digest.

## Contracts

### 1. Hierarchy contract

`agent-workflow/orchestration-hierarchy/v1` contains:

- root orchestrator ID and workflow ID;
- allowed depth, fixed to `2` below root;
- managed tmux session identity;
- global budgets: teams, total workers, concurrent workers, interactive panes;
- terminal adapter policy;
- exact team IDs and parent identity;
- source/prompt-pack snapshot digests;
- creation timestamp and identity digest.

It is installed read-only before the first team is launched.

### 2. Team delegation contract

`agent-workflow/team-delegation/v1` is the capability boundary. It contains:

- `root_orchestrator_id`, `team_id`, `team_lead_session_id`;
- objective, deliverables, writable scope, no-go scope, and stop conditions;
- delegated workflow snapshot or allowed prompt-pack phase/tasks;
- dependency inputs and required output/result schemas;
- maximum workers, concurrent workers, panes, retries, and wall-clock budget;
- allowed executor, model, class, interactivity, and permission selections;
- allowed commands expressed through parser-derived command catalog references;
- message routes the team lead may use;
- required reviews, approvals, and team receipt contents;
- parent action cursor and contract digest.

The team lead can narrow this authority for workers but cannot widen it.

### 3. Team receipt

`agent-workflow/team-receipt/v1` seals:

- the exact installed delegation contract identity and file digest;
- every explicitly declared local journal identity, record count, final message, size, and file digest;
- exact worker run IDs and immutable evidence, including every contract-required output kind;
- required independent review evidence;
- unresolved issues, scope deviations, exact bounded budget usage, and terminal disposition.

Evidence references are relative to an explicit evidence root and must resolve to read-only, single-link regular files. Duplicate ownership, cross-team journal identities, missing required outputs/reviews, later journal appends, and evidence mutation fail verification. The root scheduler may eventually accept a team as complete only from a verified team receipt; that runtime behavior is not part of HIER-002.

### 4. Root receipt

`agent-workflow/root-orchestration-receipt/v1` commits to the exact hierarchy and contract-set files, complete declared root journals, the exact declared team contract/receipt set, cross-team bindings, contract-required final approvals, unresolved evidence, and global outcome. It independently re-verifies every nested team receipt and rejects later appends, mutation, partial team sets, or ambiguous evidence ownership.

## Message model

### Envelope

Use one transport-neutral envelope for both hierarchy edges:

```json
{
  "schema": "agent-workflow/hierarchical-message/v1",
  "message_id": "uuid",
  "correlation_id": "uuid-or-null",
  "causation_id": "uuid-or-null",
  "sequence": 42,
  "timestamp": "RFC3339",
  "route": {
    "orchestration_id": "root-123",
    "from_principal": "team:implementation",
    "to_principal": "root",
    "hop": 1,
    "max_hops": 2
  },
  "assignment": {
    "team_id": "implementation",
    "worker_session_id": null,
    "assignment_id": "uuid-or-null"
  },
  "kind": "progress|question|decision_request|steer|cancel|task_complete|team_complete|error|heartbeat",
  "delivery": "requested|received|applied|rejected|unavailable",
  "summary": "bounded text",
  "content_ref": "relative/path/or-null",
  "content_sha256": "sha256:...-or-null",
  "sender_identity_digest": "sha256:..."
}
```

Large content is stored as a bounded, immutable referenced artifact. Journals keep summaries and digests.

### Routing rules

- Workers send only to their team lead unless the delegation contract explicitly permits a read-only escalation copy to root.
- Team leads send to root and to their own workers.
- Root sends to team leads, never directly to workers by default.
- Emergency root cancellation may target a worker, but the action is also recorded in the team action journal and must be acknowledged by the team lead.
- Every actionable message requires a correlated acknowledgement. `received` is not `applied`.
- Importers are idempotent by source journal identity plus source message ID.
- Sequence numbers are local to each authoritative journal. Global ordering is not claimed; causation/correlation establish cross-journal relationships.
- `tmux wait-for` signals a channel derived from recipient identity after fsync. Consumers always replay from their durable cursor.

### Decision and question flow

A blocked worker emits `question` to the team inbox. The team lead may answer within delegated authority. If not, it emits `decision_request` to root with the worker message as causation. Root replies with a correlated action. Team lead records application or rejection, then issues a narrower worker steer. This preserves authority and a complete decision chain.

## Team-lead lifecycle

1. Root validates source, prompt pack, dependency inputs, and global budgets.
2. Root writes hierarchy and team delegation contract.
3. Root creates or resolves managed tmux session.
4. Root creates a dedicated tmux window and starts the team lead in its first pane through canonical `launch_session`.
5. Team lead verifies its contract, creates its scoped registry/inbox, and records `team_ready`.
6. Root scheduler marks the team running only after durable readiness evidence exists.
7. Team lead creates worker worktrees/runs through canonical services and binds panes to exact run IDs.
8. Team lead imports worker messages, handles local questions, and escalates only unresolved decisions.
9. Team lead reconciles worker receipts, runs required fan-in/review nodes, and seals the team receipt.
10. Root verifies the team receipt, resolves cross-team bindings, and either launches dependent teams or requests rework.
11. Root seals the root receipt after global review/acceptance.
12. tmux windows may remain attachable, be archived, or be closed according to retention policy; durable evidence remains.

## Scheduling and budgets

Two schedulers cooperate without sharing mutable state:

- **Root scheduler:** schedules teams, enforces global concurrency, cross-team dependencies, and global budgets.
- **Team scheduler:** schedules only worker nodes within one delegation contract.

Global capacity is leased. A root-issued `capacity-lease` records the number of worker slots and interactive panes granted to a team. Team launch must atomically consume from its lease. Root can reduce future capacity but cannot erase already launched evidence. Version 1 should use a root lock plus append-only lease events; no daemon is required.

Recommended defaults:

- maximum active teams: 4;
- maximum worker runs across all teams: configurable, default 12;
- maximum interactive worker panes per team: 6;
- maximum hierarchy depth: 2 below root;
- one team lead pane per team window;
- noninteractive workers need not consume pane capacity.

## tmux and terminal design

Add a `ManagedTmuxTopology` service rather than embedding window logic in the scheduler.

Required operations:

- `ensure_managed_session(root_id, attach=False)`;
- `create_team_window(root_id, team_id, cwd, command)`;
- `resolve_team_window(root_id, team_id)` using durable tmux IDs/metadata;
- `split_worker_pane(team_window_id, run_id, pane_name, command)`;
- `open_external_terminal(target, adapter)`;
- `reconcile_topology(hierarchy)`;
- `close_team_window(team_id, policy)`.

Bind metadata at every level:

```text
session: @agent-workflow-root-orchestrator-id
window:  @agent-workflow-team-id
window:  @agent-workflow-team-lead-session-id
pane:    @agent-workflow-role = root|team-lead|worker|dashboard
pane:    @agent-workflow-session-id
pane:    @agent-workflow-assignment-id
```

Store tmux stable IDs (`$session`, `@window`, `%pane`) where available; names and indexes are display values only. Never rebind a live run by pane position.

### Forking a new terminal

Terminal emulators are platform-specific. Define a narrow adapter interface:

```text
open(target_tmux_session_window, title) -> launch observation
```

Supported adapters may include `current`, `windows-terminal`, `gnome-terminal`, `kitty`, `wezterm`, and `iterm2`, but the initial implementation should support `current` plus one host-tested adapter. Commands must be argv-only, configuration-selected, and explicitly trusted. Failure to open an external terminal does not roll back a successfully created durable team/window; it returns a diagnostic and attach command.

On Windows/WSL, the likely adapter launches a new Windows Terminal tab/window whose command is `wsl.exe ... tmux attach-session -t <session> \; select-window -t <window-id>`. Exact distribution and executable resolution must be configuration-driven and tested on the target host.

## Recovery and reconciliation

On restart, root:

1. reads hierarchy contract and replays hierarchy events;
2. verifies every team contract and team-lead launch footprint;
3. queries tmux topology as observation;
4. recreates missing windows only for recoverable active team leads;
5. never launches a duplicate team lead when durable evidence shows a live or sealed one;
6. imports unread team messages using durable cursors;
7. reconciles team receipts and worker receipts;
8. marks terminal loss distinctly from task failure;
9. records every repair as an event.

A team lead performs the same process for workers. Missing tmux does not erase execution evidence. A missing process with no final receipt becomes `lost`/`intervention_required`, not `failed` or `complete` by inference.

## Security and trust boundaries

- Team-lead authority is capability-based and contract-bound.
- All IDs and paths are validated; state directories and journals reject symlinks and hard-link ambiguity using existing patterns.
- Root and team actions are append-only and identity-bound.
- Team leads may call only an explicit command subset and only within delegated repositories/worktrees.
- External terminal adapters are trusted local executables and disabled by default until configured.
- Prompt content never supplies shell fragments for terminal launch.
- Secrets remain executor-policy controlled and are not copied into hierarchy artifacts or messages.
- Root acceptance remains separate from team/worker execution success.

## CLI surface

Proposed commands:

```text
agent-workflow orchestration create --root-id ID --workflow SNAPSHOT [--tmux-session NAME]
agent-workflow orchestration status --root-id ID [--tree] [--json]
agent-workflow orchestration reconcile --root-id ID
agent-workflow orchestration attach --root-id ID [--team TEAM]
agent-workflow orchestration seal --root-id ID

agent-workflow team create --root-id ID --contract CONTRACT [--terminal-mode current|external-window]
agent-workflow team status --root-id ID --team TEAM
agent-workflow team message --root-id ID --team TEAM --kind ...
agent-workflow team steer --root-id ID --team TEAM --message TEXT
agent-workflow team cancel --root-id ID --team TEAM --reason TEXT
agent-workflow team seal --root-id ID --team TEAM
```

Avoid a separate hidden team-lead executable path. A team lead is launched through the normal session service with `principal=team-lead` and a contract reference.

## Implementation decomposition

### Phase 0 — contracts and executable future specifications

Define schemas, hierarchy/event replay, delegation capability validation, receipts, and strict expected-failure journeys. No tmux mutation yet.

### Phase 1 — managed tmux sessions/windows

Add stable session/window identity, team window creation, worker pane creation scoped to a window, topology reconciliation, and attach behavior on the critical path. After the managed topology is implemented, the external terminal adapter is a separate optional branch with its own independent gate; it must not delay the team-lead runtime.

### Phase 2 — team-lead runtime and hierarchical messaging

Launch a team lead through canonical session services, create its scoped workflow/inbox, import and route messages, enforce acknowledgements and escalation, and bind worker launches to the delegation contract.

### Phase 3 — root scheduler, fan-in, recovery, and product journey

Schedule multiple teams, enforce capacity leases, resolve cross-team result bindings, verify team receipts, recover after root/team/tmux interruption, seal root receipt, and prove an installed-product end-to-end journey.

## Dependency and parallelism model

`DEC-005` gates the hierarchy contract. The durable authority lane (`HIER-001`, `HIER-002`, `HIER-GATE-0`) can proceed while existing messaging and pane-identity prerequisites are completed. `PROC-006` first gates `HIER-003`; accepted `MSG-001`, `PROC-001`, and `PROC-002` first gate `HIER-005`; accepted `BKL-002` first gates `HIER-006`.

The core implementation path is:

```text
DEC-005 → HIER-001 → HIER-002 → HIER-GATE-0
        → HIER-003 → HIER-GATE-1
        → HIER-005 → HIER-006 → HIER-GATE-2
        → HIER-007 → HIER-008 → HIER-GATE-3
```

The external terminal branch is intentionally outside that path:

```text
HIER-003 → HIER-004 → HIER-GATE-1A
```

Each ticket's external acceptance gates still apply. Missing manifest dependency edges permit concurrency; prose cannot override the manifest DAG.

## Acceptance journeys

The minimum installed-product journey must prove:

1. root creates one managed tmux session and at least two team windows;
2. each team lead launches at least two workers in its own panes/worktrees;
3. a worker question reaches its team lead; one is resolved locally and one escalates to root;
4. root steering is durably acknowledged and applied through the team lead;
5. team A result is bound into dependent team B without reading terminal prose;
6. closing an external terminal does not lose the team;
7. killing/restarting the root process allows replay without duplicate teams/workers;
8. a moved/reindexed pane remains associated by stable metadata;
9. a team cannot exceed its worker/model/command/scope budget;
10. team and root receipts verify exact child evidence and reject tampering;
11. global acceptance remains false until explicit lifecycle approval exists.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Recursive complexity and runaway agents | fixed depth, immutable budgets, capability narrowing, global leases |
| Duplicate launches after restart | durable launch footprints, deterministic IDs, reconciliation before mutation |
| Flat inbox assumptions leak across tiers | separate authoritative journals per edge; explicit route and principal identity |
| tmux window indexes drift | stable tmux IDs and metadata; indexes only for display |
| Team lead becomes an alternate executor | launch through canonical session/workflow services only |
| Cross-team deadlock | root-owned dependency graph, bounded decision timeouts, explicit intervention state |
| Terminal adapter command injection | argv-only configured adapters; no prompt-derived shell |
| Too much state duplication | references/digests to existing worker evidence; projections rebuildable |

## Recommended decision

Approve `DEC-005` and adopt the three-tier model with one root-managed tmux session and one window per team lead. Implement durable hierarchy/contracts/receipts first, then managed tmux topology, then the team-lead runtime, and only then root fan-out/fan-in. Do not add arbitrary recursion or multi-host transport until the local hierarchy is proven by restart and tamper tests.
