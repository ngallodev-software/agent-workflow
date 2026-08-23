# HERDR-003 — terminal-neutral workflow adapter

Define and implement the smallest public adapter needed for a terminal host to
bind workflow runs to external workspace/tab/pane identifiers. Keep the
authority in existing agent-workflow services and support headless operation.
Add acceptance evidence for replay, restart, plugin suppression, and missing
host behavior. Do not import Herdr or add tmux compatibility code.
