#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 1 ]] || { echo "usage: $0 AGENT_RUN" >&2; exit 2; }
exec agent-workflow agent-run terminate "$1"
