#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 3 && $# -le 4 ]] || { echo "usage: $0 REPO_PATH TICKET_ID BASE_REF [DEST]" >&2; exit 2; }
args=(worktree create "$1" "$2" "$3")
[[ $# -ge 4 ]] && args+=(--dest "$4")
exec agent-workflow "${args[@]}"
