#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: ./install-mcp.sh [--no-register] [--unregister] [--no-skills]
                        [--no-hooks] [--no-deps] [--python PATH] [--wheel PATH]

Explicitly installs Agent-Workflow's optional local stdio MCP adapter. The
ordinary install-source.sh never installs or registers MCP. By default this
script also registers the adapter in Codex and Claude; --no-register installs
only, and --unregister removes only Agent-Workflow's owned entries.

Options:
  --no-register          Install MCP without changing Codex or Claude config.
  --unregister           Remove Agent-Workflow MCP entries; do not install.
  --no-skills            Skip installation of agent skill symlinks.
  --no-hooks             Skip Codex and Claude Code hook reminders.
  --no-deps              Skip package installation; require mcp==1.28.1 already.
  --python PATH          Python interpreter used for the host installation.
  --wheel PATH           Install this built wheel instead of an editable checkout.
USAGE
}

INSTALL_SKILLS=1
INSTALL_HOOKS=1
INSTALL_DEPS=1
REGISTER_MCP=1
UNREGISTER_MCP=0
WHEEL_PATH="${AGENT_WORKFLOW_INSTALL_WHEEL:-}"
PYTHON_BIN="${AGENT_WORKFLOW_INSTALL_PYTHON:-python3}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-register) REGISTER_MCP=0 ;;
    --unregister) UNREGISTER_MCP=1 ;;
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
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done
if [[ $UNREGISTER_MCP -eq 1 && $REGISTER_MCP -eq 0 ]]; then
  echo "--unregister cannot be combined with --no-register" >&2
  exit 2
fi
ROOT="${AGENT_WORKFLOW_SOURCE_ROOT:-$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
CODEX_CONFIG_FILE="$CODEX_HOME_DIR/config.toml"
CLAUDE_CONFIG_FILE="${CLAUDE_MCP_CONFIG_FILE:-$HOME/.claude.json}"
CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/agent-workflow/config.toml"
command -v "$PYTHON_BIN" >/dev/null || {
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 127
}
PYTHON_PATH="$(command -v "$PYTHON_BIN")"

configure_codex_mcp() {
  local operation="$1"
  "$PYTHON_PATH" - "$CODEX_CONFIG_FILE" "$PYTHON_PATH" "$CONFIG_FILE" "$ROOT" "$operation" <<'PY'
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

config_file = Path(sys.argv[1])
python_path, config_path, repo_root, operation = sys.argv[2:]
if config_file.is_symlink():
    raise SystemExit(f"refusing to configure Codex: symlink path: {config_file}")
if config_file.exists() and not config_file.is_file():
    raise SystemExit(f"refusing to configure Codex: not a regular file: {config_file}")

text = config_file.read_text(encoding="utf-8") if config_file.exists() else ""
original = text
removed = False
begin = "# BEGIN AGENT-WORKFLOW MANAGED MCP"
end = "# END AGENT-WORKFLOW MANAGED MCP"
while begin in text:
    removed = True
    start = text.index(begin)
    finish = text.find(end, start)
    if finish < 0:
        raise SystemExit(f"refusing to replace unterminated managed MCP block: {config_file}")
    finish += len(end)
    text = text[:start].rstrip() + "\n" + text[finish:].lstrip()

table = re.compile(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$")
ours = re.compile(r'^mcp_servers\s*\.\s*(?:agent-workflow|"agent-workflow")(?:\s*\.|\s*$)')
kept = []
dropping = False
for line in text.splitlines(keepends=True):
    header = table.match(line)
    if header:
        dropping = bool(ours.match(header.group(1).strip()))
        removed = removed or dropping
    if not dropping:
        kept.append(line)
clean = "".join(kept).strip()

if operation == "register":
    quote = json.dumps
    block = "\n".join((
        begin,
        "[mcp_servers.agent-workflow]",
        f"command = {quote(python_path)}",
        "args = "
        + "[\"-m\", \"agent_workflow.mcp.server\", \"--config\", "
        + quote(config_path)
        + ", \"--repo-root\", "
        + quote(repo_root)
        + "]",
        end,
    ))
    updated = (clean + "\n\n" if clean else "") + block + "\n"
else:
    updated = (clean + "\n") if clean else ""

if operation != "register" and not removed:
    print(f"Agent-Workflow Codex MCP entry already absent: {config_file}")
    raise SystemExit(0)
if updated == original:
    print(f"Agent-Workflow Codex MCP entry already current: {config_file}")
    raise SystemExit(0)
config_file.parent.mkdir(parents=True, exist_ok=True)
mode = stat.S_IMODE(config_file.stat().st_mode) if config_file.exists() else 0o600
fd, temporary = tempfile.mkstemp(prefix=f".{config_file.name}.", dir=config_file.parent)
try:
    os.fchmod(fd, mode or 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(updated)
    os.replace(temporary, config_file)
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
print(f"{'configured' if operation == 'register' else 'removed'} Agent-Workflow Codex MCP: {config_file}")
PY
}

configure_claude_mcp() {
  local operation="$1"
  "$PYTHON_PATH" - "$CLAUDE_CONFIG_FILE" "$PYTHON_PATH" "$CONFIG_FILE" "$ROOT" "$operation" <<'PY'
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

config_path = Path(sys.argv[1])
python_path, app_config, repo_root, operation = sys.argv[2:]
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
servers = data.get("mcpServers")
if operation == "register":
    if servers is None:
        servers = data["mcpServers"] = {}
    if not isinstance(servers, dict):
        raise SystemExit(f"refusing to configure Claude: mcpServers is not an object: {config_path}")
    servers["agent-workflow"] = {
        "type": "stdio",
        "command": python_path,
        "args": [
            "-m", "agent_workflow.mcp.server", "--config", app_config,
            "--repo-root", repo_root,
        ],
        "env": {},
    }
elif isinstance(servers, dict):
    servers.pop("agent-workflow", None)
elif servers is not None:
    raise SystemExit(f"refusing to configure Claude: mcpServers is not an object: {config_path}")
else:
    print(f"Agent-Workflow Claude MCP entry already absent: {config_path}")
    raise SystemExit(0)

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
print(f"{'configured' if operation == 'register' else 'removed'} Agent-Workflow Claude MCP: {config_path}")
PY
}

if [[ $UNREGISTER_MCP -eq 1 ]]; then
  configure_codex_mcp remove
  configure_claude_mcp remove
  exit 0
fi

source_args=(--python "$PYTHON_BIN")
[[ $INSTALL_SKILLS -eq 1 ]] || source_args+=(--no-skills)
[[ $INSTALL_HOOKS -eq 1 ]] || source_args+=(--no-hooks)
[[ $INSTALL_DEPS -eq 1 ]] || source_args+=(--no-deps)
[[ -n "$WHEEL_PATH" ]] && source_args+=(--wheel "$WHEEL_PATH")
AGENT_WORKFLOW_SOURCE_ROOT="$ROOT" "$ROOT/scripts/install-source.sh" "${source_args[@]}"

if [[ $INSTALL_DEPS -eq 1 ]]; then
  "$PYTHON_BIN" -m pip install --upgrade "mcp==1.28.1"
fi
if ! "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
from importlib.metadata import PackageNotFoundError, version

try:
    installed = version("mcp")
except PackageNotFoundError:
    raise SystemExit(1)
raise SystemExit(0 if installed == "1.28.1" else 1)
PY
then
  echo "MCP support requires mcp==1.28.1 for $PYTHON_PATH; rerun without --no-deps or install it with $PYTHON_PATH -m pip install mcp==1.28.1" >&2
  exit 1
fi

if [[ $REGISTER_MCP -eq 1 ]]; then
  configure_codex_mcp register
  configure_claude_mcp register
else
  echo "installed MCP support without registering Codex or Claude"
fi
cat <<EOF2
MCP installation complete: agent-workflow-mcp
MCP client registration: $([[ $REGISTER_MCP -eq 1 ]] && echo enabled || echo skipped)
EOF2
