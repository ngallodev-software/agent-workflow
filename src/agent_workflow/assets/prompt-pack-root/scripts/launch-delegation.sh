#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 5 ]] || { echo "usage: $0 AGENT_RUN WORKDIR PROMPT_FILE -- COMMAND [ARGS...]" >&2; exit 2; }
agent_run_id=$1; workdir=$2; prompt=$3; shift 3
agent-workflow agent-run prepare "$agent_run_id" "$workdir" "$prompt" "$@"
exec agent-workflow agent-run start "$agent_run_id"
