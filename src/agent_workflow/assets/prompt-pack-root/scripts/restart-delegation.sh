#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 1 && $# -le 2 ]] || { echo "usage: $0 AGENT_RUN [NEW_AGENT_RUN]" >&2; exit 2; }
args=(agent-run restart "$1")
[[ $# -eq 2 ]] && args+=(--new-agent-run-id "$2")
exec agent-workflow "${args[@]}"
