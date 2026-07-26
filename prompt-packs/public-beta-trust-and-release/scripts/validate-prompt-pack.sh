#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 1 ]] || { echo "usage: $0 PACK_DIR" >&2; exit 2; }
exec agent-workflow pack validate "$1"
