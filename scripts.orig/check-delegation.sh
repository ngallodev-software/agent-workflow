#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 1 ]] || { echo "usage: $0 SESSION" >&2; exit 2; }
SESSION="$1"
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session: running"
  tmux list-panes -t "$SESSION" -F 'pane_pid=#{pane_pid} dead=#{pane_dead} current_command=#{pane_current_command}'
  tmux capture-pane -pt "$SESSION" -S -40
else
  echo "tmux session: not running"
fi
find . \( -path "*/.delegations/$SESSION/status.json" -o -path "*/.delegations/$SESSION/output.log" \) 2>/dev/null | sort
