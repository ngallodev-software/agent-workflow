# HERDR-004 — build the Herdr plugin

In the separately indexed `/lump/apps/herdr` worktree/repository scope approved
by HERDR-GATE-2, create `herdr-agent-workflow` as a manifest-driven Herdr plugin.
Use argv-only calls through `HERDR_BIN_PATH`; use Herdr panes/actions/events
for presentation and the public agent-workflow CLI/services for authority.
Implement config/state directory separation, bounded output, reversible link/
install behavior, and installed plugin acceptance. Do not call tmux, write
agent-workflow journals directly, infer completion from pane state, or add a
second scheduler/registry.
