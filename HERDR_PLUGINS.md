# Herdr plugins: repository reference

This document summarizes the Herdr plugin contract relevant to integrating
`agent-workflow`. It is based on the current Herdr documentation, version
0.8.2, read 2026-08-23.

Primary sources:

- [Herdr plugins](https://herdr.dev/docs/plugins/)
- [Herdr CLI reference](https://herdr.dev/docs/cli-reference/)
- [Herdr socket API](https://herdr.dev/docs/socket-api/)
- [Herdr marketplace](https://herdr.dev/docs/marketplace/)

## 1. What a plugin is

A Herdr plugin is a directory containing `herdr-plugin.toml` and one or more
commands that Herdr launches out of process. The command can be implemented in
Bash, JavaScript, Python, Rust, Go, Lua, or another executable environment.

Herdr owns the host surface:

- plugin installation, linking, enabling, disabling, and validation;
- workspace, tab, terminal pane, agent, keybinding, and event integration;
- invocation context and plugin environment variables;
- CLI and local socket access; and
- plugin command logs.

The plugin owns its implementation language, dependencies, files, and durable
state. A plugin is ordinary user-level executable code, not a sandbox or a
restricted capability container.

There is no separate Herdr plugin SDK. The documented Herdr CLI is the normal
plugin API. Use `HERDR_BIN_PATH` for portable CLI calls; use
`HERDR_SOCKET_PATH` and the raw socket API only when direct request/response
control or long-lived event subscriptions are needed.

Plugin v1 supports manifest-declared actions, startup hooks, event hooks,
terminal panes, keybindings, and link handlers. Runtime action registration and
native non-terminal plugin UI are not part of v1.

## 2. Manifest contract

The minimum manifest is:

```toml
id = "example.workflow"
name = "Example Workflow"
version = "0.1.0"
min_herdr_version = "0.8.2"
description = "A workflow integration"
platforms = ["linux", "macos", "windows"]
```

Required top-level fields are `id`, `name`, `version`, and
`min_herdr_version`. Set `min_herdr_version` to the oldest Herdr version that
supports every API, event name, and manifest field used by the plugin. Herdr
refuses to link or install a plugin requiring a newer version.

Supported manifest entrypoints include:

```toml
[[build]]
command = ["npm", "ci"]

[[startup]]
command = ["python", "startup.py"]

[[actions]]
id = "status"
title = "Show workflow status"
contexts = ["workspace"]
command = ["python", "action.py", "status"]

[[events]]
on = "worktree.created"
command = ["python", "events.py", "worktree-created"]

[[panes]]
id = "dashboard"
title = "Workflow dashboard"
placement = "overlay"
command = ["python", "dashboard.py"]

[[link_handlers]]
id = "workflow-run"
title = "Open workflow run"
pattern = "^https://example\\.test/runs/[A-Za-z0-9-]+$"
action = "status"
```

Commands are argv arrays. Herdr does not invoke them through a shell or perform
shell expansion. Use an explicit shell executable if shell behavior is truly
required, and treat all interpolated values as untrusted.

Top-level `platforms` declares supported platforms. Individual builds,
startup hooks, actions, events, panes, and link handlers may override it.
Action, pane, and link-handler IDs are local to the plugin and may not contain
dots; Herdr qualifies action IDs globally as `plugin.id.action`.

## 3. Installation and lifecycle

For a published plugin:

```text
herdr plugin install OWNER/REPO[/SUBDIR] [--ref REF] [--yes]
herdr plugin list [--plugin ID] [--json]
herdr plugin enable ID
herdr plugin disable ID
herdr plugin uninstall ID
```

For local development:

```text
herdr plugin link /path/to/plugin
herdr plugin unlink ID
herdr plugin config-dir ID
herdr plugin action list --plugin ID
herdr plugin action invoke plugin.id.action
herdr plugin pane open --plugin ID --entrypoint dashboard
herdr plugin log list --plugin ID
```

GitHub installation uses a trust preview, optionally runs manifest build
commands, then registers the plugin. `--yes` is appropriate only for a
trusted, pinned source. `--ref` pins the requested Git revision. Reinstalling a
GitHub-managed plugin replaces its managed checkout. Installing over a locally
linked plugin is refused; unlink it first.

Plugin installation, linking, and enabled state are global to the current user
and available across Herdr sessions. Linking does not run build commands.
Unlinking unregisters a local plugin but leaves its files; uninstalling a
GitHub-managed plugin also removes Herdr-managed checkout files. There is no
separate `plugin update` command; reinstall to refresh a GitHub plugin.

Startup hooks run asynchronously once for each enabled plugin after session
restore and socket readiness. They run again after a live server handoff, but
not merely because a client attaches, config reloads, or a plugin is linked or
enabled. They are one-shot initialization commands, not supervised daemons.
A startup failure is logged but does not stop Herdr.

Build commands run during GitHub installation, after confirmation and before
registration. A build failure aborts installation and leaves the plugin
unregistered. Build commands do not receive runtime plugin context or socket
environment variables.

## 4. Runtime environment and state

Herdr runs runtime commands with the plugin directory as the working directory
and supplies, as applicable:

| Variable | Meaning |
|---|---|
| `HERDR_BIN_PATH` | Portable path to the Herdr executable |
| `HERDR_SOCKET_PATH` | Local Unix socket or Windows named-pipe path |
| `HERDR_ENV` | Herdr plugin environment marker (`1`) |
| `HERDR_PLUGIN_ID` | Installed plugin ID |
| `HERDR_PLUGIN_ROOT` | Linked or installed plugin checkout |
| `HERDR_PLUGIN_CONFIG_DIR` | User-editable plugin configuration directory |
| `HERDR_PLUGIN_STATE_DIR` | Plugin-owned runtime/durable state directory |
| `HERDR_PLUGIN_CONTEXT_JSON` | Invocation context JSON |
| `HERDR_WORKSPACE_ID` | Current workspace, when available |
| `HERDR_TAB_ID` | Current tab, when available |
| `HERDR_PANE_ID` | Current pane, when available |
| `HERDR_PLUGIN_ACTION_ID` | Action being invoked |
| `HERDR_PLUGIN_EVENT` | `startup` or the event-hook context |
| `HERDR_PLUGIN_EVENT_JSON` | Event payload JSON |
| `HERDR_PLUGIN_ENTRYPOINT_ID` | Pane entrypoint being launched |

Herdr-managed environment values take precedence over conflicting caller
values. `HERDR_PLUGIN_CONTEXT_JSON` may contain workspace, tab, focused pane,
worktree, agent, selected text, clicked URL, and link-handler fields.

Never put credentials or durable mutable state in `HERDR_PLUGIN_ROOT` because
GitHub-installed roots are managed source checkouts. Put user-editable files
such as `.env` under `HERDR_PLUGIN_CONFIG_DIR`; put runtime state, indexes,
caches, and durable plugin data under `HERDR_PLUGIN_STATE_DIR`. Herdr creates
these directories and may seed the config directory from legacy plugin config,
but the plugin owns the state format and lifecycle. Herdr provides no managed
plugin database/storage API in v1.

## 5. Actions, events, and links

Actions are explicit manifest commands. They can be invoked from the CLI,
keybindings, or link handlers. An action should perform bounded work, return a
useful exit status, and write detailed diagnostics to stderr while keeping
stdout suitable for Herdr's command log or a caller expecting JSON.

Event hooks are also manifest commands. They receive `HERDR_PLUGIN_EVENT` and
`HERDR_PLUGIN_EVENT_JSON`. They are appropriate for refresh/reconcile hints,
not for replacing an authoritative database or lifecycle journal. A plugin
must tolerate duplicate, delayed, and missing event delivery by rebuilding or
re-reading its own state.

Keybindings use a manifest command entry:

```toml
[[keys.command]]
key = "prefix+w"
type = "plugin_action"
command = "example.workflow.status"
description = "show workflow status"
```

Link handlers match clicked URLs with a Rust regular expression. Modified
click is Control on every platform. A link action receives
`invocation_source = "link_click"`, `clicked_url`, and `link_handler_id` in
the context JSON; shell plugins also receive the corresponding dedicated
environment variables.

## 6. Terminal panes

Manifest panes are terminal panes managed by Herdr. The default placement is
`overlay`, a temporary zoomed overlay that restores focus and zoom when it
closes. `plugin.pane.open` can override placement with `overlay`, `popup`,
`split`, `tab`, or `zoomed`.

`popup` is a session-modal terminal resource. It can specify numeric cell
dimensions or percentages such as `80%`; omitted dimensions use Herdr's default
half-size popup. A popup receives terminal input, closes when its command exits
or when `popup.close` is requested, has no pane ID, emits no pane lifecycle
events, and does not participate in pane/layout/persistence/agent APIs. A
popup may be unavailable while another Herdr modal is active (`ui_busy`).

Overlay, split, tab, and zoomed plugin panes are ordinary Herdr panes after
opening. Plugins can use public pane operations such as move, swap, resize,
zoom, read, and close. Herdr keeps ownership attached to the underlying pane
when it moves across tabs or workspaces. Use public pane IDs and workspace/tab
IDs; never infer identity from pane position or display order.

The CLI/socket API also supports `session.snapshot` for bootstrap, followed by
event subscriptions for cache updates. `pane.moved` reports moves without
fabricating close/create events. This is the correct model for a dashboard that
must survive layout changes.

## 7. CLI versus socket API

Use the layers in this order:

1. Herdr CLI wrappers for shell plugins, simple orchestration, and debugging.
2. Raw socket API for custom clients, typed request/response control, and
   long-lived event subscriptions.
3. The agent skill when teaching an agent to operate Herdr from inside a pane.

The installed binary can expose the exact protocol schema for its version:

```text
herdr api schema
herdr api schema --json
herdr api schema --output herdr-api.schema.json
```

The socket API covers workspaces, tabs, panes, worktrees, agents, events,
notifications, integrations, and plugins. Important plugin-facing methods
include:

```text
plugin.link / plugin.list / plugin.unlink
plugin.enable / plugin.disable
plugin.action.list / plugin.action.invoke
plugin.log.list
plugin.pane.open / plugin.pane.focus / plugin.pane.close
events.subscribe / events.wait
session.snapshot
```

Important terminal/agent methods for a workflow presentation include
`pane.list`, `pane.get`, `pane.read`, `pane.layout`, `pane.move`,
`pane.process_info`, `pane.wait_for_output`, `agent.list`, `agent.get`,
`agent.wait`, `agent.view.set`, and `agent.view.clear`.

Socket transport is platform-specific: Unix uses a Unix socket and Windows
uses a named pipe. `HERDR_BIN_PATH` is preferred when a plugin only needs CLI
operations because it avoids implementing that transport difference.

## 8. Security and reliability rules for agent-workflow integration

- Treat every plugin as trusted executable code with the user's privileges.
- Review manifests, build commands, and runtime commands before installation.
- Pin GitHub sources when reproducibility matters.
- Use argv arrays and avoid shell interpolation.
- Keep credentials in user configuration, never in the plugin checkout or
  invocation context.
- Treat terminal output, event payloads, clicked URLs, and selected text as
  untrusted input; bound, escape, and redact them before durable storage or
  display.
- Herdr pane/process state is an observation and presentation surface. It must
  not become the authority for workflow completion, acceptance, or review.
- Use durable agent-workflow journals, receipts, and schemas for authority;
  Herdr events are refresh hints and Herdr IDs are external bindings.
- Make actions idempotent or revalidate current state before mutation because
  event delivery, pane focus, and process state can change between observation
  and action.
- Keep plugin state outside the checkout and make disable/unlink reversible.

## 9. Implications for `herdr-agent-workflow`

The planned integration should be an out-of-process Herdr plugin with:

- a workspace action to open/resume workflow status;
- a Herdr-managed dashboard pane for durable run/task/review projections;
- event hooks that refresh the projection without granting authority;
- explicit actions that invoke the public `agent-workflow` CLI/services for
  launch, status, review, acceptance, interrupt, and termination; and
- plugin config/state directories used only for presentation preferences,
  cursors, caches, and other plugin-owned data.

It must not call `tmux`, write agent-workflow journals directly, infer
completion from pane liveness, or create a second scheduler, message bus,
receipt format, or plugin registry.
