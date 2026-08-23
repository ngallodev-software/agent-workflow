# Phase 2 master prompt

Execute the dependency DAG exactly. HERDR-003 must be accepted before
HERDR-004 starts. The plugin uses Herdr's documented manifest/CLI/socket
surface and agent-workflow's public authority services; it must not call tmux
or write private durable state.
