#!/usr/bin/env bash
set -euo pipefail
usage() {
  cat <<'USAGE'
Usage: ./install.sh [--no-skills] [--no-deps] [--extras NAME[,NAME...]]

Installs this checkout into the current user's Python environment in editable
mode, including its declared core dependencies, then creates launcher and skill
symlinks. Missing dependencies may require network access.

Options:
  --no-deps              Skip Python package/dependency installation.
  --extras NAME[,NAME...] Install optional dependency groups (for example
                          eval,stats or all). Core dependencies are always
                          included unless --no-deps is set.
USAGE
}
INSTALL_SKILLS=1
INSTALL_DEPS=1
EXTRAS=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-skills) INSTALL_SKILLS=0 ;;
    --no-deps) INSTALL_DEPS=0 ;;
    --extras)
      shift
      [[ $# -gt 0 ]] || { echo "--extras requires a value" >&2; exit 2; }
      EXTRAS="$1"
      ;;
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
if [[ $INSTALL_DEPS -eq 1 ]]; then
  command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 127; }
  python3 -m pip --version >/dev/null 2>&1 || {
    echo "pip is required; install it for python3 before running this installer" >&2
    exit 1
  }
  install_target="$ROOT"
  if [[ -n "$EXTRAS" ]]; then
    if [[ "$EXTRAS" == "all" ]]; then
      EXTRAS="eval,stats,otel,mlflow,completion"
    fi
    install_target="$ROOT[$EXTRAS]"
  fi
  echo "installing Python package and dependencies: $install_target"
  python3 -m pip install --user --upgrade --editable "$install_target"
elif ! python3 -c 'import jsonschema' >/dev/null 2>&1; then
  echo "jsonschema>=4.18,<5 is required; rerun without --no-deps or install it with python3 -m pip" >&2
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
if [[ $INSTALL_DEPS -eq 1 && -x "$BIN_DIR/agent-workflow" && ! -L "$BIN_DIR/agent-workflow" ]]; then
  echo "kept pip-managed launcher: $BIN_DIR/agent-workflow"
else
  safe_link "$ROOT/bin/agent-workflow" "$BIN_DIR/agent-workflow"
fi
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
