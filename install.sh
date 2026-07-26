#!/usr/bin/env bash
set -euo pipefail
usage() {
  cat <<'USAGE'
Usage: ./install.sh [--no-skills] [--no-deps] [--python PATH]
                    [--extras NAME[,NAME...]]

Installs this checkout into the current user's Python environment in editable
mode, including its declared core dependencies, then creates launcher and skill
symlinks. Missing dependencies may require network access.

Options:
  --no-skills            Skip installation of agent skill symlinks.
  --no-deps              Skip Python package/dependency installation.
  --python PATH          Python interpreter used for the host installation.
  --extras NAME[,NAME...] Install optional dependency groups (for example
                          eval,stats or all). Core dependencies are always
                          included unless --no-deps is set.
USAGE
}
INSTALL_SKILLS=1
INSTALL_DEPS=1
EXTRAS=""
PYTHON_BIN="${AGENT_WORKFLOW_INSTALL_PYTHON:-python3}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-skills) INSTALL_SKILLS=0 ;;
    --no-deps) INSTALL_DEPS=0 ;;
    --python)
      shift
      [[ $# -gt 0 ]] || { echo "--python requires a value" >&2; exit 2; }
      PYTHON_BIN="$1"
      ;;
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
command -v "$PYTHON_BIN" >/dev/null || {
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 127
}
"$PYTHON_BIN" -c 'import sys; sys.exit("agent-workflow requires Python 3.11+") if sys.version_info < (3,11) else None'
if [[ $INSTALL_DEPS -eq 1 ]]; then
  "$PYTHON_BIN" -m pip --version >/dev/null 2>&1 || {
    echo "pip is required; install it for $PYTHON_BIN before running this installer" >&2
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
  "$PYTHON_BIN" -m pip install --user --upgrade --editable "$install_target"
elif ! "$PYTHON_BIN" -c 'import jsonschema' >/dev/null 2>&1; then
  echo "jsonschema>=4.18,<5 is required; rerun without --no-deps or install it with $PYTHON_BIN -m pip" >&2
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
  skill_roots=("$HOME/.agents/skills" "$HOME/.codex/skills" "$HOME/.claude/skills")
  skills=()
  while IFS= read -r -d '' skill_dir; do
    skills+=("$(basename "$skill_dir")")
  done < <(find "$ROOT/skills" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
  mkdir -p "${skill_roots[@]}"
  for root in "${skill_roots[@]}"; do
    for skill in "${skills[@]}"; do
      safe_link "$ROOT/skills/$skill" "$root/$skill"
    done
  done
fi

# Keep host-discoverable, non-Python release assets in dedicated XDG
# locations. The Python package also carries schemas, but syncing them here
# makes an editable install and a wheel install resolve the same current set.
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DATA_DIR="$DATA_HOME/agent-workflow"
MAN_DIR="$DATA_HOME/man/man1"
sync_tree() {
  local source="$1" destination="$2" path relative target
  [[ -d "$source" ]] || return 0
  while IFS= read -r -d '' path; do
    relative="${path#"$source"/}"
    target="$destination/$relative"
    mkdir -p "$(dirname "$target")"
    cp -p "$path" "$target"
  done < <(find "$source" -type f -print0)
}
sync_tree "$ROOT/schemas" "$APP_DATA_DIR/schemas"
sync_tree "$ROOT/evals" "$APP_DATA_DIR/evals"
sync_tree "$ROOT/prompt-packs" "$APP_DATA_DIR/prompt-packs"
sync_tree "$ROOT/docs/man" "$MAN_DIR"
mkdir -p "$APP_DATA_DIR"
printf '%s\n' "$ROOT" > "$APP_DATA_DIR/source-root"
cat <<EOF2
installed launcher: $BIN_DIR/agent-workflow
source repository: $ROOT
config: $CONFIG_FILE
host data: $APP_DATA_DIR
man pages: $MAN_DIR

Ensure this is on PATH:
  export PATH="\$HOME/.local/bin:\$PATH"

Then run:
  agent-workflow doctor
EOF2
