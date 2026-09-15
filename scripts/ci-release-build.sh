#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

rm -rf build dist
python -m build --sdist --wheel --outdir dist
wheel="$(find "$root/dist" -maxdepth 1 -type f -name 'agent_workflow-*.whl' -print -quit)"
sdist="$(find "$root/dist" -maxdepth 1 -type f -name 'agent_workflow-*.tar.gz' -print -quit)"
test -n "$wheel" || { echo 'built agent-workflow wheel is missing' >&2; exit 2; }
test -n "$sdist" || { echo 'built agent-workflow sdist is missing' >&2; exit 2; }
python scripts/build-release-bundles.py --version "v$(tr -d '\n' < VERSION)" --wheel "$wheel" --sdist "$sdist" --output-dir "$root/dist"
find dist -maxdepth 1 -type f \( -name '*.whl' -o -name '*.tar.gz' -o -name '*.zip' \) -print0 | sort -z | xargs -0 sha256sum > dist/SHA256SUMS
python scripts/audit-release-assets.py
