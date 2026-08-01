#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 1 && $# -le 2 ]] || { echo "usage: $0 SESSION [NEW_SESSION]" >&2; exit 2; }
args=(restart "$1")
[[ $# -eq 2 ]] && args+=(--new-session "$2")
exec agent-workflow "${args[@]}"
