#!/usr/bin/env bash
set -euo pipefail
rm -f "$HOME/.local/bin/agent-workflow"
for root in "$HOME/.agents/skills" "$HOME/.claude/skills"; do
  for skill in delegated-implementation prompt-pack-builder phase-gate-review; do
    path="$root/$skill"
    [[ -L "$path" ]] && rm -f "$path"
  done
done
cat <<'EOF2'
Removed the launcher and workflow skill symlinks.
Configuration, run evidence, and the source repository were intentionally preserved.
EOF2
