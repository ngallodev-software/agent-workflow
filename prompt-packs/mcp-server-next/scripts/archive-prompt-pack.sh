#!/usr/bin/env bash
set -euo pipefail
[[ $# -eq 2 ]] || { echo "usage: $0 PACK_DIR OUTPUT.tar.zst" >&2; exit 2; }
exec agent-workflow pack archive "$1" "$2"
