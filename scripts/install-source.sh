#!/usr/bin/env bash
set -euo pipefail
usage() {
  cat <<'USAGE'
Usage: ./install.sh [--no-skills] [--no-hooks] [--no-deps] [--python PATH]
                    [--wheel PATH] [--extras NAME[,NAME...]] [--harnesses NAME[,NAME...]]

Installs this checkout, or a supplied wheel, into the current user's Python
environment, including its declared core dependencies, then creates launcher, shared
skill symlinks, and client hook reminders. Codex skill installation is the default;
Claude and generic harness roots are opt-in. MCP is deliberately excluded from this
default installer; use scripts/install-mcp.sh to opt into the local stdio adapter.
Missing dependencies may require network access.

Options:
  --no-skills            Skip installation of agent skill symlinks.
  --no-hooks             Skip Codex and Claude Code hook reminders.
  --no-deps              Skip Python package/dependency installation.
  --python PATH          Python interpreter used for the host installation.
  --wheel PATH           Install this built wheel instead of an editable checkout.
  --extras NAME[,NAME...] Install optional non-MCP feature groups (for example
                          eval,stats,completion or all). Core dependencies are
                          always included unless --no-deps is set. MCP must be
                          installed with scripts/install-mcp.sh.
  --harnesses NAME[,NAME...] Install skill links for codex (default), claude,
                            and/or generic. Generic uses the .agents skill root.
USAGE
}
INSTALL_SKILLS=1
INSTALL_HOOKS=1
INSTALL_DEPS=1
EXTRAS=""
INSTALL_HARNESSES="codex"
WHEEL_PATH="${AGENT_WORKFLOW_INSTALL_WHEEL:-}"
PYTHON_BIN="${AGENT_WORKFLOW_INSTALL_PYTHON:-python3}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-skills) INSTALL_SKILLS=0 ;;
    --no-hooks) INSTALL_HOOKS=0 ;;
    --no-deps) INSTALL_DEPS=0 ;;
    --python)
      shift
      [[ $# -gt 0 ]] || { echo "--python requires a value" >&2; exit 2; }
      PYTHON_BIN="$1"
      ;;
    --wheel)
      shift
      [[ $# -gt 0 ]] || { echo "--wheel requires a value" >&2; exit 2; }
      WHEEL_PATH="$1"
      ;;
    --extras)
      shift
      [[ $# -gt 0 ]] || { echo "--extras requires a value" >&2; exit 2; }
      EXTRAS="$1"
      ;;
    --harnesses)
      shift
      [[ $# -gt 0 ]] || { echo "--harnesses requires a value" >&2; exit 2; }
      INSTALL_HARNESSES="$1"
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done
ROOT="${AGENT_WORKFLOW_SOURCE_ROOT:-$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BIN_DIR="$HOME/.local/bin"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/agent-workflow"
CONFIG_FILE="$CONFIG_DIR/config.toml"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DATA_DIR="$DATA_HOME/agent-workflow"
HOOKS_DATA_DIR="$APP_DATA_DIR/hooks"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
SHARED_SKILLS_DIR="$CODEX_HOME_DIR/skills"
CODEX_CONFIG_FILE="$CODEX_HOME_DIR/config.toml"
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CLAUDE_SETTINGS_FILE="$CLAUDE_CONFIG_DIR/settings.json"
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 127; }
command -v "$PYTHON_BIN" >/dev/null || {
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 127
}
PYTHON_PATH="$(command -v "$PYTHON_BIN")"
"$PYTHON_BIN" -c 'import sys; sys.exit("agent-workflow requires Python 3.11+") if sys.version_info < (3,11) else None'
PYTHON_IN_VENV="$("$PYTHON_BIN" -c 'import sys; print("1" if sys.prefix != sys.base_prefix else "0")')"
if [[ "$EXTRAS" == "all" ]]; then
  EXTRAS="eval,stats,completion"
fi
if [[ ",$EXTRAS," == *,mcp,* ]]; then
  echo "MCP is opt-in; use scripts/install-mcp.sh" >&2
  exit 2
fi
declare -A harness_roots=(
  [codex]="$SHARED_SKILLS_DIR"
  [claude]="$HOME/.claude/skills"
  [generic]="$HOME/.agents/skills"
)
declare -A selected_harnesses=()
IFS=',' read -r -a harness_list <<< "$INSTALL_HARNESSES"
for harness in "${harness_list[@]}"; do
  [[ -n "${harness_roots[$harness]+x}" ]] || {
    echo "unknown harness: $harness (expected codex, claude, or generic)" >&2
    exit 2
  }
  selected_harnesses["$harness"]=1
done
if [[ $INSTALL_DEPS -eq 1 ]]; then
  if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    echo "pip is missing for $PYTHON_PATH; trying ensurepip" >&2
    ensurepip_args=(--upgrade)
    [[ "$PYTHON_IN_VENV" == "1" ]] || ensurepip_args+=(--user)
    if "$PYTHON_BIN" -m ensurepip "${ensurepip_args[@]}" >/dev/null 2>&1; then
      echo "bootstrapped pip for $PYTHON_PATH" >&2
    fi
  fi
  if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    cat >&2 <<EOF3
pip is unavailable for the selected interpreter: $PYTHON_PATH
Install pip for that interpreter, then rerun this command:
  $PYTHON_PATH -m ensurepip --upgrade --user
If ensurepip is unavailable, install the OS package that provides pip
(often python3-pip), or pass --python PATH for a Python installation with pip.
EOF3
    exit 1
  fi
  install_target="$ROOT"
  if [[ -n "$WHEEL_PATH" ]]; then
    [[ -f "$WHEEL_PATH" ]] || { echo "wheel not found: $WHEEL_PATH" >&2; exit 2; }
    install_target="$WHEEL_PATH"
  elif [[ -n "$EXTRAS" ]]; then
    install_target="$ROOT[$EXTRAS]"
  fi
  echo "installing Python package and dependencies: $install_target"
  if [[ -n "$WHEEL_PATH" ]]; then
    pip_args=(--upgrade --force-reinstall "$install_target")
    "$PYTHON_BIN" -m pip install "${pip_args[@]}"
  else
    "$PYTHON_BIN" -m pip install --upgrade --editable "$install_target"
  fi
fi
if [[ $INSTALL_DEPS -eq 0 ]] && ! "$PYTHON_BIN" -c 'import jsonschema, yaml' >/dev/null 2>&1; then
  echo "jsonschema>=4.18,<5 and PyYAML>=6.0.3,<7 are required; rerun without --no-deps or install them with $PYTHON_BIN -m pip" >&2
  exit 1
fi
mkdir -p "$BIN_DIR" "$CONFIG_DIR"
is_owned_pip_launcher() {
  local path="$1"
  [[ -f "$path" ]] || return 1
  "$PYTHON_BIN" - "$path" <<'PY'
from pathlib import Path
import sys

lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
raise SystemExit(
    0
    if len(lines) == 6
    and lines[0].startswith("#!")
    and lines[1:] == [
        "import sys",
        "from agent_workflow.cli import main",
        "if __name__ == '__main__':",
        "    sys.argv[0] = sys.argv[0].removesuffix('.exe')",
        "    sys.exit(main())",
    ]
    else 1
)
PY
}

safe_link() {
  local source="$1" destination="$2"
  if [[ -L "$destination" ]]; then
    local current_target
    current_target="$(readlink -f "$destination")"
    if [[ "$current_target" != "$(readlink -f "$source")" \
      && ( -z "${installed_launcher:-}" || "$current_target" != "$(readlink -f "$installed_launcher")" ) ]]; then
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

launcher_source="$ROOT/bin/agent-workflow"
installed_launcher="$(dirname "$PYTHON_PATH")/agent-workflow"
if [[ $INSTALL_DEPS -eq 1 && -x "$installed_launcher" && "$installed_launcher" != "$BIN_DIR/agent-workflow" ]]; then
  launcher_source="$installed_launcher"
fi
if [[ -f "$BIN_DIR/agent-workflow" && ! -L "$BIN_DIR/agent-workflow" ]] && is_owned_pip_launcher "$BIN_DIR/agent-workflow"; then
  unlink "$BIN_DIR/agent-workflow"
fi
safe_link "$launcher_source" "$BIN_DIR/agent-workflow"
if [[ ! -e "$CONFIG_FILE" ]]; then
  cp "$ROOT/config/agent-workflow.example.toml" "$CONFIG_FILE"
  echo "created config: $CONFIG_FILE"
else
  echo "kept existing config: $CONFIG_FILE"
fi
if [[ $INSTALL_SKILLS -eq 1 ]]; then
  skills=()
  while IFS= read -r -d '' skill_dir; do
    skills+=("$(basename "$skill_dir")")
  done < <(find "$ROOT/skills" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
  for harness in "${harness_list[@]}"; do
    root="${harness_roots[$harness]}"
    mkdir -p "$root"
    for skill in "${skills[@]}"; do
      safe_link "$ROOT/skills/$skill" "$root/$skill"
    done
  done

  # Remove only links owned by older all-harness installations.
  for legacy_harness in generic claude; do
    [[ -n "${selected_harnesses[$legacy_harness]+x}" ]] && continue
    legacy_root="${harness_roots[$legacy_harness]}"
    for skill in "${skills[@]}"; do
      legacy_link="$legacy_root/$skill"
      if [[ -L "$legacy_link" && "$(readlink "$legacy_link")" == "$ROOT/skills/$skill" ]]; then
        unlink "$legacy_link"
      fi
    done
  done

fi

# Keep host-discoverable, non-Python release assets in dedicated XDG
# locations. The Python package also carries schemas, but syncing them here
# makes an editable install and a wheel install resolve the same current set.
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
sync_owned_hook_tree() {
  local source="$1" destination="$2" path relative
  mkdir -p "$destination"

  # Remove only files previously owned by Agent-Workflow's hook bundle.
  # Preserve unrelated user files that happen to live in the same directory.
  while IFS= read -r -d '' path; do
    relative="${path#"$destination"/}"
    case "$relative" in
      agent-workflow-run-reminder|rtk-session-reminder|codebase-memory-session-reminder|codex-code-discovery-gate|README.md)
        if [[ ! -f "$source/$relative" ]]; then
          rm -f "$path"
        fi
        ;;
    esac
  done < <(find "$destination" -maxdepth 1 -type f -print0)

  sync_tree "$source" "$destination"
}
if [[ $INSTALL_HOOKS -eq 1 ]]; then
  sync_owned_hook_tree "$ROOT/scripts/hooks" "$HOOKS_DATA_DIR"
  CBM_GATE=""
  if [[ -x "$HOME/.codex/hooks/cbm-code-discovery-gate" ]]; then
    CBM_GATE="$HOME/.codex/hooks/cbm-code-discovery-gate"
  fi
  CLAUDE_CBM_GATE=""
  if [[ -x "$HOME/.claude/hooks/cbm-code-discovery-gate" ]]; then
    CLAUDE_CBM_GATE="$HOME/.claude/hooks/cbm-code-discovery-gate"
  fi
  "$PYTHON_PATH" "$ROOT/scripts/configure-hooks.py" \
    --codex-config "$CODEX_CONFIG_FILE" \
    --claude-settings "$CLAUDE_SETTINGS_FILE" \
    --hooks-dir "$HOOKS_DATA_DIR" \
    --cbm-gate "$CBM_GATE" \
    --claude-cbm-gate "$CLAUDE_CBM_GATE"
fi
mkdir -p "$APP_DATA_DIR"
printf '%s\n' "$ROOT" > "$APP_DATA_DIR/source-root"
HOOK_CLIENTS=""
if [[ $INSTALL_HOOKS -eq 1 ]]; then
  HOOK_CLIENTS="hooks: Codex ($CODEX_CONFIG_FILE), Claude Code ($CLAUDE_SETTINGS_FILE)"
fi
cat <<EOF2
installed launcher: $BIN_DIR/agent-workflow
source repository: $ROOT
config: $CONFIG_FILE
host data: $APP_DATA_DIR
man pages: $MAN_DIR
$HOOK_CLIENTS

Ensure this is on PATH:
  export PATH="\$HOME/.local/bin:\$PATH"

Then run:
  agent-workflow doctor
EOF2
