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
python scripts/build-release-bundles.py --version "v$(tr -d '\r\n' < VERSION)" --wheel "$wheel" --sdist "$sdist" --output-dir "$root/dist"
(
  cd dist
  for path in *.whl *.tar.gz *.zip; do
    [[ -f "$path" ]] || continue
    sha256sum "$path"
  done | sort -k2
) > dist/SHA256SUMS
if grep -Eq '(^|[[:space:]])(\./|dist/)' dist/SHA256SUMS; then
  echo "release checksum manifest must use release-root basenames" >&2
  exit 2
fi
if [ "$(python -c 'import os; print(os.name)')" != nt ]; then
  python scripts/audit-release-assets.py
fi
