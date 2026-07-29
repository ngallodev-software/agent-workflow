# PROC-006 source reference — shared-window pane identity

## Observed defect

At the preparation revision, `src/agent_workflow/tmux.py::split_window()` asks
tmux to print:

```text
#{session_name}:#{window_index}.#{pane_index}
```

It already reads `#{pane_id}` while laying out panes, but discards that stable
ID and returns the positional target. `src/agent_workflow/sessions.py::launch`
persists the returned value as `tmux_target` and derives `tmux_session` from it
for shared-window runs. `agent_context.complete_task`, `sessions.observe`,
`interrupt`, `terminate`, `kill`, and reusable-agent candidate discovery then
use that persisted target. Pane indexes are mutable when panes are added,
removed, or renumbered.

The live failure pattern is therefore:

```text
persisted: tmux_session=36, tmux_target=36:0.1
live pane: pane_id=%112, pane_index=1
```

The current target may work until another pane changes the layout, after which
the target can resolve to another pane or no pane. This creates a false
`orphaned` result and blocks `task-complete` even though the executor is live.
This failure has affected MSG-001 and PROC-001 recovery attempts.

## Required identity model

- `session_id` / application run ID is the authoritative workflow identity.
- tmux `%pane_id` is the stable locator for the lifetime of one tmux pane. It
  is unaffected by pane index changes and must be used for shared-window
  controls and liveness checks.
- `session:window` is context for capacity/layout discovery, not a pane
  identity.
- pane index (`session:window.index`) is display/debug data only.
- pane title, `@agent-workflow-name`, agent name, and PID are not sufficient
  identity. Names are mutable/reusable and PIDs can exit or be reused.
- Bind the pane to the application run/assignment with a tmux user option such
  as `@agent-workflow-session-id` and, where needed, an assignment identifier.
  The binding is a locator/recovery check; durable JSONL run state remains the
  authority.

An actual pane destruction or tmux-server restart invalidates the `%pane_id`.
Do not guess a replacement by title, PID, or position. Report a genuine
orphan and use the existing recovery/restart lifecycle while preserving the
run evidence.

## Compatibility requirements

Existing dedicated-session runs use the application session name as their
tmux target and must continue to work. Existing shared-window status records
may contain a positional target; define a narrow read/repair/migration path
that either resolves and upgrades the record using an unambiguous run binding
or reports an unavailable/legacy-target outcome. Never silently attach a run
to a different pane.

Keep the public CLI shape stable unless a new diagnostic field is necessary.
If a new field is introduced, prefer an additive field such as `tmux_pane_id`
and preserve truthful legacy status for old runs. Do not make pane names the
new public key.

## Required call sites to audit

- `src/agent_workflow/tmux.py`: pane creation, metadata binding, pane lookup,
  pane info, capture, interrupt, kill, and stable target formatting.
- `src/agent_workflow/sessions.py`: launch, observe, interrupt, terminate,
  kill, and shared/dedicated mode persistence.
- `src/agent_workflow/agent_context.py`: task completion, reusable candidates,
  and window candidate filtering.
- `tests/conftest.py`: fake tmux output must model pane IDs independently from
  pane indexes.
- status/contract schemas and documentation if persisted fields change.

## Explicit non-targets

- Do not implement two-way messaging features beyond the pane identity needed
  for their reliable operation.
- Do not change provider adapters, model selection, worktree ownership,
  lifecycle authority, or sealed receipt semantics.
- Do not automatically kill or delete a suspected orphan.
- Do not add a daemon, database, HTTP transport, or external MCP dependency.
