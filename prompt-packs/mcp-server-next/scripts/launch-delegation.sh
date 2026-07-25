#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 5 ]] || { echo "usage: $0 SESSION WORKDIR PROMPT_FILE -- COMMAND [ARGS...]" >&2; exit 2; }
exec agent-workflow launch "$@"
