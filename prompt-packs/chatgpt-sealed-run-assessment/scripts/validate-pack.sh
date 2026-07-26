#!/usr/bin/env bash
set -euo pipefail

PACK_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
REPO_ROOT=$(CDPATH= cd -- "$PACK_DIR/../.." && pwd)

cd "$REPO_ROOT"
exec python3 -m agent_workflow pack validate "$PACK_DIR"
