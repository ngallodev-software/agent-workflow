#!/usr/bin/env bash
set -euo pipefail

EXPECTED_VERSION="${AGENT_WORKFLOW_OPENSPEC_VERSION:-1.13.2}"
PACKAGE="@fission-ai/openspec@${EXPECTED_VERSION}"

if command -v openspec >/dev/null 2>&1; then
  observed="$(openspec --version 2>/dev/null || true)"
  if [[ "$observed" == "$EXPECTED_VERSION" ]]; then
    echo "OpenSpec available: $observed"
    exit 0
  fi
  echo "OpenSpec version mismatch: observed ${observed:-unknown}; expected $EXPECTED_VERSION" >&2
else
  echo "OpenSpec is not installed." >&2
fi

cat >&2 <<EOF
Agent-Workflow's qualified OpenSpec boundary currently requires exactly:
  $PACKAGE

Install explicitly with:
  npm install -g '$PACKAGE'

Run this helper with --install to perform that explicit pinned installation.
EOF

[[ "${1:-}" == "--install" ]] || exit 1
command -v npm >/dev/null 2>&1 || {
  echo "npm is required for OpenSpec installation" >&2
  exit 127
}

npm install -g "$PACKAGE"
command -v openspec >/dev/null 2>&1 || {
  echo "OpenSpec installation completed but 'openspec' is unavailable" >&2
  exit 1
}
observed="$(openspec --version 2>/dev/null || true)"
[[ "$observed" == "$EXPECTED_VERSION" ]] || {
  echo "OpenSpec installation returned version ${observed:-unknown}; expected $EXPECTED_VERSION" >&2
  exit 1
}
echo "OpenSpec available: $observed"
