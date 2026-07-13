#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 1 ]] || { echo "usage: $0 SESSION" >&2; exit 2; }
SESSION="$1"
if tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux send-keys -t "$SESSION" C-c
  sleep 2
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  echo "stopped: $SESSION"
else
  echo "session not running: $SESSION"
fi
