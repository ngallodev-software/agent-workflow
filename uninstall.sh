#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${AGENT_WORKFLOW_INSTALL_PYTHON:-python3}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      shift
      [[ $# -gt 0 ]] || { echo "--python requires a value" >&2; exit 2; }
      PYTHON_BIN="$1"
      ;;
    -h|--help)
      echo "Usage: ./uninstall.sh [--python PATH]"
      exit 0
      ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done
remove_owned_link() {
  local expected="$1" path="$2"
  if [[ -L "$path" && "$(readlink "$path")" == "$expected" ]]; then
    unlink "$path"
  elif [[ -e "$path" || -L "$path" ]]; then
    echo "preserved unrelated path: $path" >&2
  fi
}
remove_owned_link "$ROOT/bin/agent-workflow" "$HOME/.local/bin/agent-workflow"
for root in "$HOME/.agents/skills" "$HOME/.codex/skills" "$HOME/.claude/skills"; do
  while IFS= read -r -d '' skill_dir; do
    skill="$(basename "$skill_dir")"
    path="$root/$skill"
    remove_owned_link "$skill_dir" "$path"
  done < <(find "$ROOT/skills" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
done
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DATA_DIR="$DATA_HOME/agent-workflow"
if [[ -f "$APP_DATA_DIR/source-root" && "$(<"$APP_DATA_DIR/source-root")" == "$ROOT" ]]; then
  for tree in schemas evals prompt-packs; do
    if [[ -d "$APP_DATA_DIR/$tree" ]]; then
      find "$APP_DATA_DIR/$tree" -type f -delete
      find "$APP_DATA_DIR/$tree" -depth -type d -empty -delete
    fi
  done
  unlink "$APP_DATA_DIR/source-root"
  find "$APP_DATA_DIR" -depth -type d -empty -delete
fi
MAN_DIR="$DATA_HOME/man/man1"
for page in "$ROOT"/docs/man/*.1; do
  [[ -f "$page" ]] || continue
  installed="$MAN_DIR/$(basename "$page")"
  if [[ -f "$installed" ]] && cmp -s "$page" "$installed"; then
    unlink "$installed"
  fi
done
if [[ -f "$ROOT/.release-bundle" ]]; then
  command -v "$PYTHON_BIN" >/dev/null 2>&1 || {
    echo "Python interpreter not found: $PYTHON_BIN" >&2
    exit 127
  }
  "$PYTHON_BIN" -m pip uninstall --yes agent-workflow
fi
cat <<'EOF2'
Removed owned launcher, workflow skill symlinks, synchronized assets, and
unchanged man pages; release bundles also remove the agent-workflow wheel.
Unrelated paths and locally modified man pages were preserved.
Configuration, run evidence, and the source repository were intentionally preserved.
EOF2
