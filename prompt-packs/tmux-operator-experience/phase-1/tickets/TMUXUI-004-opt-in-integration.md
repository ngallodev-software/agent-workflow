# TMUXUI-004 — opt-in tmux integration and capability policy

**Backlog:** [`TMUXUI-004`](../../../../docs/BACKLOG.md)  
**Dependencies:** TMUXUI-001

## Goal

Make tmux integration explicit, namespaced, idempotent, reversible, and compatible with existing user configuration.

## Writable paths

- Capability/config/install-uninstall service and thin packaged tmux assets.
- Config schema/example and doctor/diagnostic output where appropriate.
- CLI commands for print-only/install/uninstall limited to tmux UI integration.
- Focused preservation/idempotency/package-data tests.
- Installation/operations docs for implemented behavior.

Do not implement popup internals, dashboard, lifecycle actions, refresh daemon, or embedded sidebar.

## Required behavior

- Detect tmux availability/version, `display-popup`, format/hook support, `fzf`, and optional dependencies without assuming host paths.
- Package installation alone performs no tmux mutation.
- `--print-only` emits auditable snippets.
- Explicit installation uses namespaced options, hooks, keybindings, and cache paths; preserve existing hook arrays/status format/keybindings.
- Repeated install is idempotent; uninstall removes only entries created by `agent-workflow` and tolerates partial prior state.
- Support current-session scope first; user-level config editing only if it can preserve content safely and is explicitly requested.
- Avoid global one-second status intervals and auto-created panes/windows.

## Acceptance and tests

- Existing custom `status-right`, hook arrays, interval, and conflicting keybinding remain intact unless the user explicitly selects a replacement behavior.
- Repeated install/uninstall and interrupted partial install recover safely.
- Unsupported tmux/fzf paths produce actionable capability output.
- Built-wheel package-data and public CLI journeys pass.

## Stop conditions

Stop if implementation must rewrite arbitrary tmux config text unsafely, overwrite global options implicitly, or leave untracked mutations that uninstall cannot identify. Use `templates/TICKET_COMPLETION.md`.
