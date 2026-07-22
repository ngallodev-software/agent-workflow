#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
remove_owned_link() {
  local expected="$1" path="$2"
  if [[ -L "$path" && "$(readlink "$path")" == "$expected" ]]; then
    unlink "$path"
  elif [[ -e "$path" || -L "$path" ]]; then
    echo "preserved unrelated path: $path" >&2
  fi
}
remove_owned_link "$ROOT/bin/agent-workflow" "$HOME/.local/bin/agent-workflow"
for root in "$HOME/.agents/skills" "$HOME/.claude/skills"; do
  for skill in delegated-implementation prompt-pack-builder phase-gate-review; do
    path="$root/$skill"
    remove_owned_link "$ROOT/skills/$skill" "$path"
  done
done
cat <<'EOF2'
Removed owned launcher and workflow skill symlinks; unrelated paths were preserved.
Configuration, run evidence, and the source repository were intentionally preserved.
EOF2
