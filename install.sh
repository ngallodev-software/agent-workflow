#!/usr/bin/env bash
set -euo pipefail
usage() {
  cat <<'USAGE'
Usage: ./install.sh [--no-skills]

Creates symlinks from the permanent source repository into ~/.local/bin and
supported agent skill directories. No network access, virtual environment, or
package download is required.
USAGE
}
INSTALL_SKILLS=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-skills) INSTALL_SKILLS=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done
ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/agent-workflow"
CONFIG_FILE="$CONFIG_DIR/config.toml"
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 127; }
python3 -c 'import sys; sys.exit("agent-workflow requires Python 3.11+") if sys.version_info < (3,11) else None'
if ! python3 -c 'import jsonschema' >/dev/null 2>&1; then
  echo "jsonschema>=4.18,<5 is required; install the wheel or run: python3 -m pip install 'jsonschema>=4.18,<5'" >&2
  exit 1
fi
mkdir -p "$BIN_DIR" "$CONFIG_DIR"
safe_link() {
  local source="$1" destination="$2"
  if [[ -L "$destination" ]]; then
    if [[ "$(readlink "$destination")" != "$source" ]]; then
      echo "refusing to replace unrelated symlink: $destination" >&2
      exit 2
    fi
    unlink "$destination"
  elif [[ -e "$destination" ]]; then
    echo "refusing to replace non-symlink path: $destination" >&2
    exit 2
  fi
  ln -s "$source" "$destination"
}
safe_link "$ROOT/bin/agent-workflow" "$BIN_DIR/agent-workflow"
if [[ ! -e "$CONFIG_FILE" ]]; then
  cp "$ROOT/config/agent-workflow.example.toml" "$CONFIG_FILE"
  echo "created config: $CONFIG_FILE"
else
  echo "kept existing config: $CONFIG_FILE"
fi
if [[ $INSTALL_SKILLS -eq 1 ]]; then
  mkdir -p "$HOME/.agents/skills" "$HOME/.claude/skills"
  for skill in delegated-implementation prompt-pack-builder phase-gate-review; do
    safe_link "$ROOT/skills/$skill" "$HOME/.agents/skills/$skill"
    safe_link "$ROOT/skills/$skill" "$HOME/.claude/skills/$skill"
  done
fi
cat <<EOF2
installed launcher: $BIN_DIR/agent-workflow
source repository: $ROOT
config: $CONFIG_FILE

Ensure this is on PATH:
  export PATH="\$HOME/.local/bin:\$PATH"

Then run:
  agent-workflow doctor
EOF2
