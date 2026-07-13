#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 1 ]] || { echo "usage: $0 SESSION" >&2; exit 2; }
exec agent-workflow terminate "$1"
