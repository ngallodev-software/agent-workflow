#!/usr/bin/env bash
set -euo pipefail
usage() {
  cat <<'USAGE'
Usage: ./install.sh [--no-skills] [--no-hooks] [--no-deps] [--python PATH]
                    [--wheel PATH] [--extras NAME[,NAME...]]

Installs this checkout, or a supplied wheel, into the current user's Python
environment, including its declared core dependencies, then creates launcher, skill
symlinks, and client hook reminders. The local stdio MCP adapter is an optional
feature installed and registered only when the `mcp` extra is requested. Missing
dependencies may require network access.

Options:
  --no-skills            Skip installation of agent skill symlinks.
  --no-hooks             Skip Codex and Claude Code hook reminders.
  --no-deps              Skip Python package/dependency installation.
  --python PATH          Python interpreter used for the host installation.
  --wheel PATH           Install this built wheel instead of an editable checkout.
  --extras NAME[,NAME...] Install optional feature groups (for example
                          mcp,eval,stats or all). Core dependencies are always
                          included unless --no-deps is set.
USAGE
}
INSTALL_SKILLS=1
INSTALL_HOOKS=1
INSTALL_DEPS=1
EXTRAS=""
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
CODEX_CONFIG_FILE="$CODEX_HOME_DIR/config.toml"
CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CLAUDE_SETTINGS_FILE="$CLAUDE_CONFIG_DIR/settings.json"
# MCP is a first-party optional feature. Installation and client registration
# are requested explicitly through --extras mcp (or --extras all).
MCP_CONFIG_REQUESTED=0
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 127; }
command -v "$PYTHON_BIN" >/dev/null || {
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 127
}
PYTHON_PATH="$(command -v "$PYTHON_BIN")"
"$PYTHON_BIN" -c 'import sys; sys.exit("agent-workflow requires Python 3.11+") if sys.version_info < (3,11) else None'
PYTHON_IN_VENV="$("$PYTHON_BIN" -c 'import sys; print("1" if sys.prefix != sys.base_prefix else "0")')"
if [[ "$EXTRAS" == "all" ]]; then
  EXTRAS="eval,stats,otel,mlflow,completion,mcp"
fi
if [[ ",$EXTRAS," == *,mcp,* ]]; then
  MCP_CONFIG_REQUESTED=1
fi
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
    if [[ "$EXTRAS" == "all" || ",$EXTRAS," == *,mcp,* ]]; then
      pip_args+=("mcp==1.28.1")
    fi
    "$PYTHON_BIN" -m pip install "${pip_args[@]}"
  else
    "$PYTHON_BIN" -m pip install --upgrade --editable "$install_target"
  fi
fi
if [[ $MCP_CONFIG_REQUESTED -eq 1 ]] && ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
from importlib.metadata import PackageNotFoundError, version

try:
    installed = version("mcp")
except PackageNotFoundError:
    raise SystemExit(1)
raise SystemExit(0 if installed == "1.28.1" else 1)
PY
then
  echo "MCP support requires mcp==1.28.1 for $PYTHON_PATH; rerun without --no-deps or install it with $PYTHON_BIN -m pip install mcp==1.28.1" >&2
  exit 1
fi
if [[ $INSTALL_DEPS -eq 0 ]] && ! "$PYTHON_BIN" -c 'import jsonschema, yaml' >/dev/null 2>&1; then
  echo "jsonschema>=4.18,<5 and PyYAML>=6.0.3,<7 are required; rerun without --no-deps or install them with $PYTHON_BIN -m pip" >&2
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

configure_codex_mcp() {
  mkdir -p "$CODEX_HOME_DIR"
  if [[ -e "$CODEX_CONFIG_FILE" && ! -f "$CODEX_CONFIG_FILE" ]]; then
    echo "refusing to configure Codex: not a regular file: $CODEX_CONFIG_FILE" >&2
    return 1
  fi
  if [[ -f "$CODEX_CONFIG_FILE" ]] && grep -Eq '^[[:space:]]*\[mcp_servers\.("agent-workflow"|agent-workflow)\][[:space:]]*$' "$CODEX_CONFIG_FILE"; then
    echo "kept existing Codex MCP server: $CODEX_CONFIG_FILE"
    return 0
  fi
  if [[ -s "$CODEX_CONFIG_FILE" ]]; then
    printf '\n' >> "$CODEX_CONFIG_FILE"
  fi
  "$PYTHON_PATH" - "$PYTHON_PATH" "$CONFIG_FILE" "$ROOT" >> "$CODEX_CONFIG_FILE" <<'PY'
import json
import sys

python_path, config_path, repo_root = sys.argv[1:]
quote = json.dumps
print("[mcp_servers.agent-workflow]")
print(f"command = {quote(python_path)}")
print(
    "args = "
    + "[\"-m\", \"agent_workflow.mcp.server\", \"--config\", "
    + quote(config_path)
    + ", \"--repo-root\", "
    + quote(repo_root)
    + "]"
)
PY
  echo "configured Codex MCP server: $CODEX_CONFIG_FILE"
}

configure_claude_mcp() {
  local claude_config="$HOME/.claude.json"
  "$PYTHON_PATH" - "$claude_config" "$PYTHON_PATH" "$CONFIG_FILE" "$ROOT" <<'PY'
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

config_path = Path(sys.argv[1])
python_path, app_config, repo_root = sys.argv[2:]
if config_path.is_symlink():
    raise SystemExit(f"refusing to configure Claude: symlink path: {config_path}")
if config_path.exists():
    if not config_path.is_file():
        raise SystemExit(f"refusing to configure Claude: not a regular file: {config_path}")
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"refusing to configure Claude: invalid JSON: {config_path}: {exc}") from exc
else:
    data = {}
if not isinstance(data, dict):
    raise SystemExit(f"refusing to configure Claude: top-level JSON value is not an object: {config_path}")
servers = data.setdefault("mcpServers", {})
if not isinstance(servers, dict):
    raise SystemExit(f"refusing to configure Claude: mcpServers is not an object: {config_path}")
if "agent-workflow" in servers:
    print(f"kept existing Claude MCP server: {config_path}")
    raise SystemExit(0)
servers["agent-workflow"] = {
    "type": "stdio",
    "command": python_path,
    "args": [
        "-m",
        "agent_workflow.mcp.server",
        "--config",
        app_config,
        "--repo-root",
        repo_root,
    ],
    "env": {},
}
config_path.parent.mkdir(parents=True, exist_ok=True)
mode = stat.S_IMODE(config_path.stat().st_mode) if config_path.exists() else 0o600
fd, temporary = tempfile.mkstemp(prefix=f".{config_path.name}.", dir=config_path.parent)
try:
    os.fchmod(fd, mode or 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")
    os.replace(temporary, config_path)
except BaseException:
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.unlink(temporary)
    except FileNotFoundError:
        pass
    raise
print(f"configured Claude MCP server: {config_path}")
PY
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
if [[ $MCP_CONFIG_REQUESTED -eq 1 ]]; then
  configure_codex_mcp
  configure_claude_mcp
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
if [[ $INSTALL_HOOKS -eq 1 ]]; then
  sync_tree "$ROOT/scripts/hooks" "$HOOKS_DATA_DIR"
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
MCP_CLIENTS=""
if [[ $MCP_CONFIG_REQUESTED -eq 1 ]]; then
  MCP_CLIENTS="MCP clients: Codex ($CODEX_CONFIG_FILE), Claude Code ($HOME/.claude.json)"
fi
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
$MCP_CLIENTS
$HOOK_CLIENTS

Ensure this is on PATH:
  export PATH="\$HOME/.local/bin:\$PATH"

Then run:
  agent-workflow doctor
EOF2
