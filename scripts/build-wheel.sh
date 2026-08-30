#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
python3 scripts/verify-wheel-source.py
rm -rf build dist
python3 -m build --wheel --no-isolation
