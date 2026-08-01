# TMUXUI-006 — dedicated tmux dashboard window

**Backlog:** [`TMUXUI-006`](../../../../docs/BACKLOG.md)  
**Dependencies:** TMUXUI-002, TMUXUI-003, TMUXUI-004

## Goal

Provide a reusable persistent `aw-dashboard` tmux window using the accepted snapshot, preview, and cache interfaces without altering managed work-window geometry or agent capacity.

## Writable paths

- Dashboard renderer/controller and thin launcher asset.
- Minimal tmux window metadata helpers.
- Config for dashboard window name/reuse/refresh behavior.
- Dashboard layout/capacity tests and installed journey.
- User/operations documentation.

Do not insert a sidebar into work windows, change agent split algorithms, or implement new lifecycle authority.

## Required behavior

- Create or reuse exactly one namespaced dashboard window per selected scope.
- Render attention list, active hierarchy, selected metadata, and bounded preview responsively.
- Mark dashboard resources with explicit UI metadata and exclude them from managed agent discovery/capacity.
- Preserve selection where possible and rebuild from snapshot truth.
- Handle narrow terminals and missing preview gracefully.
- Close/remove cleanly without killing managed runs or leaving stale metadata.

## Acceptance and tests

- Before/after inventories prove agent pane count, orchestrator pane, columns, dimensions, and run bindings are unchanged.
- Duplicate invocation reuses rather than multiplies dashboard windows.
- Narrow, detached, renamed, manually closed, and stale-window cases.
- Installed journey opens, refreshes, focuses a run, closes, and verifies cleanup.

## Stop conditions

Stop if the dashboard must occupy a managed agent pane, changes work-window layout, or relies on mutable pane indexes. Embedded-sidebar ideas belong only to TMUXUI-008. Use `templates/TICKET_COMPLETION.md`.
