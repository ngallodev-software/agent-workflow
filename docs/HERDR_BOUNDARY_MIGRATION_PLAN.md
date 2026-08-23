# Herdr boundary migration plan

## Objective

Make Herdr the only owner of terminal, tmux, pane, layout, and pane-identity
behavior. Keep `agent-workflow` focused on durable workflow authority and ship
the retained workflow capabilities as a first-party Herdr plugin.

This is an execution plan, not permission to delete the current implementation.
The inventory phase must establish the exact compatibility surface first.

## Target ownership

| Capability | Owner after migration | Boundary |
|---|---|---|
| tmux server/session/window/pane creation and teardown | Herdr | Herdr CLI/socket/plugin API |
| pane identity, layout, naming, capacity, attach, capture, focus | Herdr | Stable Herdr pane/workspace IDs |
| terminal UI, dashboards, popups, external-terminal attachment | Herdr | Herdr plugin panes/actions |
| durable run/workflow state and append-only evidence | agent-workflow | Existing schemas, journals, receipts |
| worktrees, prompt packs, task manifests, dependency scheduling | agent-workflow | Existing CLI/services |
| messages, approvals, review/acceptance, evaluation, SQLite projection | agent-workflow | Existing authority services |
| process policy and executor adapters | agent-workflow core | No tmux ownership; typed terminal adapter only |
| Herdr integration and operator presentation | `herdr-agent-workflow` plugin | Herdr manifest plus CLI calls |

## Explicit removal set

The implementation phase must remove or replace all first-party tmux/pane
ownership, including `agent_workflow.tmux`, pane-capacity and pane-identity
helpers, tmux-specific session launch/observation/attach/kill paths, benchmark
operator-pane runners, managed hierarchy topology, external-terminal adapters,
and tmux-only acceptance/invariant tests. It must preserve durable session
identity and evidence fields by replacing terminal references with an explicit
Herdr binding/adapter record.

The following are not automatically removed: subprocess execution, process
groups, cancellation policy, durable lifecycle transitions, raw evidence
schemas, or workflow scheduling. Those remain useful without a terminal host.

## Plugin shape

The first-party plugin is a separate Herdr distribution/repository subtree,
`herdr-agent-workflow`, with a `herdr-plugin.toml` manifest. It should provide:

1. a workspace action to open or resume the workflow view for the current
   Herdr workspace;
2. a pane/dashboard entrypoint for durable run, task, review, and attention
   state;
3. event hooks that refresh or reconcile the presentation after workflow
   events, without making terminal state authoritative;
4. explicit actions for launch, status, review, accept, interrupt, and
   terminate that call the typed `agent-workflow` CLI and preserve its evidence
   rules;
5. plugin-owned config/state under Herdr's supplied directories, never inside
   the installed plugin checkout.

The plugin must not shell out to `tmux`, infer completion from pane liveness,
write agent-workflow authority files directly, or introduce a second scheduler,
message bus, receipt format, or plugin registry.

## Agent-workflow execution plan

The work is intentionally staged through isolated worktrees and sealed
completion reports:

```text
HERDR-001 inventory and seam contract
  -> HERDR-GATE-0
  -> HERDR-002 remove tmux/pane ownership
  -> HERDR-GATE-1
  -> HERDR-003 extract terminal-neutral workflow adapter
  -> HERDR-GATE-2
  -> HERDR-004 build herdr-agent-workflow plugin
  -> HERDR-GATE-3
```

Each implementation ticket has one disjoint writable scope. Every phase runs
the release-drift audit, pack validation, focused installed journeys, and an
independent gate. Real tmux/Herdr acceptance is opt-in evidence; it is not
replaced by fake terminal output.

### HERDR-001 — inventory and seam contract

Use codebase-memory on both indexed repositories plus bounded source searches
to produce a symbol/file ownership matrix, call-graph impact report, public
CLI compatibility list, schema migration list, and Herdr API compatibility
matrix. Capture the current dirty-tree baseline and stop on overlapping
uncommitted edits. No source mutation.

### HERDR-002 — remove terminal ownership

In an isolated agent-workflow worktree, delete only the confirmed tmux/pane
implementation and replace callers with a typed terminal-host boundary. Remove
or rewrite terminal-specific commands/tests/docs and update the backlog only
after acceptance. Durable lifecycle operations must fail clearly when no host
adapter is configured, rather than silently recreating tmux behavior.

### HERDR-003 — terminal-neutral workflow adapter

Keep workflow launch, process policy, evidence collection, scheduling, and
receipts independent of Herdr. Define a narrow adapter contract for a host to
request a terminal target and report stable external IDs. Prove headless
workflow journeys and ensure `--no-plugins`/core recovery remain functional.

### HERDR-004 — `herdr-agent-workflow` plugin

Implement the manifest, actions, pane, event hooks, config/state separation,
argv-only invocation, bounded output/error handling, and installed plugin
journey. The plugin calls agent-workflow's public CLI/services and translates
Herdr context into explicit workspace/run bindings. It never owns authority.

## Acceptance gates

- No `agent-workflow` runtime path invokes tmux or owns pane topology.
- Core installed workflow journeys pass without tmux or Herdr.
- Herdr can open, refresh, and close the workflow presentation without changing
  durable workflow state except through an explicit action.
- Pane movement, workspace changes, terminal restart, and Herdr restart do not
  rebind a run to a different pane.
- Every lifecycle action has durable evidence and remains replayable after the
  plugin is disabled.
- Plugin install/link/uninstall is reversible and leaves workflow evidence and
  user config intact.
- Release assets contain neither a duplicate terminal manager nor unreviewed
  plugin state; docs, schemas, help, and tests agree with the new boundary.

## Stop conditions

Stop and report a typed blocker if Herdr lacks a required stable API, the dirty
tree overlaps a target path, a proposed change would alter authority schemas,
or the candidate plugin needs direct access to private agent-workflow internals.
