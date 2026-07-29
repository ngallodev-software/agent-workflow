# source-preflight-snapshot-reliability

Fix divergent clean-source detection without weakening the dirty-source safety
gate. Validate with `agent-workflow pack validate`, create worktrees through
`agent-workflow worktree create`, and launch through `agent-workflow launch`.
Interactive execution uses a visible tmux pane when available; native host
subagents are not durable runs unless bridged through the CLI.
