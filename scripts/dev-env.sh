#!/usr/bin/env bash
# Source this file to enter/leave an Agent-Workflow development runtime:
#   source scripts/dev-env.sh on
#   source scripts/dev-env.sh off

_aw_dev_env_resolve() {
  local root candidate launcher resolved
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  candidate="${1:-}"
  if [[ -n "$candidate" ]]; then
    :
  elif [[ -n "${AGENT_WORKFLOW_VENV:-}" ]]; then
    candidate="$AGENT_WORKFLOW_VENV"
  elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
    candidate="$VIRTUAL_ENV"
  elif [[ -x "$root/.venv/bin/python" || -x "$root/.venv/bin/python3" ]]; then
    candidate="$root/.venv"
  else
    launcher="$(command -v agent-workflow 2>/dev/null || true)"
    [[ -n "$launcher" ]] || return 1
    resolved="$(python3 - "$launcher" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
)"
    candidate="$(dirname "$(dirname "$resolved")")"
  fi
  python3 - "$candidate" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
}

_aw_dev_env_save_var() {
  local name="$1" set_name="_AW_DEV_PREV_${1}_SET" value_name="_AW_DEV_PREV_${1}"
  if declare -p "$name" >/dev/null 2>&1; then
    printf -v "$set_name" '%s' 1
    printf -v "$value_name" '%s' "${!name}"
  else
    printf -v "$set_name" '%s' 0
    printf -v "$value_name" '%s' ""
  fi
  export "$set_name" "$value_name"
}

_aw_dev_env_restore_var() {
  local name="$1" set_name="_AW_DEV_PREV_${1}_SET" value_name="_AW_DEV_PREV_${1}"
  if [[ "${!set_name:-0}" == "1" ]]; then
    printf -v "$name" '%s' "${!value_name}"
    export "$name"
  else
    unset "$name"
  fi
  unset "$set_name" "$value_name"
}

_aw_dev_env_seed_config() {
  local source_config="$1" target_config="$2" venv="$3" python
  if [[ -x "$venv/bin/python" ]]; then
    python="$venv/bin/python"
  else
    python="$venv/bin/python3"
  fi
  mkdir -p "$(dirname "$target_config")"
  "$python" - "$source_config" "$target_config" "$venv" <<'PY'
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import re
import sys
import tempfile
import tomllib

source = Path(sys.argv[1])
target = Path(sys.argv[2])
venv = Path(sys.argv[3]).resolve()

def read_valid(path: Path) -> tuple[str | None, str | None]:
    if not path.is_file():
        return None, None
    text = path.read_text(encoding="utf-8")
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        return text, str(exc)
    return text, None

target_text, target_error = read_valid(target)
source_text, source_error = read_valid(source)

backup = None
if target_text is not None and target_error is None:
    text = target_text
elif source_text is not None and source_error is None:
    if target_text is not None and target_error is not None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = target.with_name(f"{target.name}.invalid-{stamp}")
        backup.write_text(target_text, encoding="utf-8")
    text = source_text
elif target_text is None and source_text is None:
    text = "schema_version = 1\n"
else:
    details = []
    if target_error is not None:
        details.append(f"target {target}: {target_error}")
    if source_error is not None:
        details.append(f"source {source}: {source_error}")
    raise SystemExit("cannot seed development config from valid TOML; " + "; ".join(details))

worktree = json.dumps(str(venv / ".xdg" / "data" / "agent-workflow" / "worktrees"))
state = json.dumps(str(venv / ".xdg" / "state" / "agent-workflow"))

lines = text.splitlines()
out = []
in_paths = False
saw_paths = False
wrote_worktree = False
wrote_state = False
for line in lines:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        if in_paths:
            if not wrote_worktree:
                out.append(f"worktree_root = {worktree}")
            if not wrote_state:
                out.append(f"state_root = {state}")
        in_paths = stripped == "[paths]"
        saw_paths = saw_paths or in_paths
        if in_paths:
            wrote_worktree = False
            wrote_state = False
        out.append(line)
        continue
    if in_paths and re.match(r"^\s*worktree_root\s*=", line):
        out.append(f"worktree_root = {worktree}")
        wrote_worktree = True
    elif in_paths and re.match(r"^\s*state_root\s*=", line):
        out.append(f"state_root = {state}")
        wrote_state = True
    else:
        out.append(line)
if in_paths:
    if not wrote_worktree:
        out.append(f"worktree_root = {worktree}")
    if not wrote_state:
        out.append(f"state_root = {state}")
if not saw_paths:
    if out and out[-1].strip():
        out.append("")
    out.extend(["[paths]", f"worktree_root = {worktree}", f"state_root = {state}"])

rendered = "\n".join(out).rstrip() + "\n"
try:
    tomllib.loads(rendered)
except tomllib.TOMLDecodeError as exc:
    raise SystemExit(f"refusing to write invalid development config: {exc}") from exc

target.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile(
    "w",
    encoding="utf-8",
    dir=target.parent,
    prefix=target.name + ".",
    suffix=".tmp",
    delete=False,
) as handle:
    handle.write(rendered)
    temp = Path(handle.name)
os.replace(temp, target)

if backup is not None:
    print(f"recovered invalid development config; backup preserved at {backup}", file=sys.stderr)
PY
}

aw_dev_env_on() {
  if [[ "${AGENT_WORKFLOW_DEV_ENV_ACTIVE:-}" == "1" ]]; then
    echo "Agent-Workflow dev environment is already active at $AGENT_WORKFLOW_VENV" >&2
    return 0
  fi

  local venv previous_config_home source_config target_config
  venv="$(_aw_dev_env_resolve "${1:-}")" || {
    echo "could not resolve Agent-Workflow development virtualenv" >&2
    return 1
  }
  [[ -x "$venv/bin/python" || -x "$venv/bin/python3" ]] || {
    echo "resolved path is not a virtualenv: $venv" >&2
    return 1
  }

  previous_config_home="${XDG_CONFIG_HOME:-$HOME/.config}"
  source_config="$previous_config_home/agent-workflow/config.toml"

  for name in VIRTUAL_ENV AGENT_WORKFLOW_VENV AGENT_WORKFLOW_BIN PATH XDG_CONFIG_HOME XDG_STATE_HOME XDG_DATA_HOME; do
    _aw_dev_env_save_var "$name"
  done

  export VIRTUAL_ENV="$venv"
  export AGENT_WORKFLOW_VENV="$venv"
  export AGENT_WORKFLOW_BIN="$venv/bin/agent-workflow"
  export PATH="$venv/bin:$PATH"
  export XDG_CONFIG_HOME="$venv/.xdg/config"
  export XDG_STATE_HOME="$venv/.xdg/state"
  export XDG_DATA_HOME="$venv/.xdg/data"
  export AGENT_WORKFLOW_DEV_ENV_ACTIVE=1

  mkdir -p "$XDG_CONFIG_HOME" "$XDG_STATE_HOME" "$XDG_DATA_HOME"
  target_config="$XDG_CONFIG_HOME/agent-workflow/config.toml"
  _aw_dev_env_seed_config "$source_config" "$target_config" "$venv"
  hash -r 2>/dev/null || true

  echo "Agent-Workflow dev environment enabled:"
  echo "  venv:   $VIRTUAL_ENV"
  echo "  config: $target_config"
  echo "  state:  $XDG_STATE_HOME/agent-workflow"
  echo "  data:   $XDG_DATA_HOME/agent-workflow"
}

aw_dev_env_off() {
  if [[ "${AGENT_WORKFLOW_DEV_ENV_ACTIVE:-}" != "1" ]]; then
    echo "Agent-Workflow dev environment is not active" >&2
    return 0
  fi
  for name in VIRTUAL_ENV AGENT_WORKFLOW_VENV AGENT_WORKFLOW_BIN PATH XDG_CONFIG_HOME XDG_STATE_HOME XDG_DATA_HOME; do
    _aw_dev_env_restore_var "$name"
  done
  unset AGENT_WORKFLOW_DEV_ENV_ACTIVE
  hash -r 2>/dev/null || true
  echo "Agent-Workflow dev environment restored"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "This script must be sourced so it can change the current shell:" >&2
  echo "  source scripts/dev-env.sh on [VENV]" >&2
  echo "  source scripts/dev-env.sh off" >&2
  exit 2
fi

case "${1:-}" in
  on)
    shift
    aw_dev_env_on "${1:-}"
    ;;
  off)
    aw_dev_env_off
    ;;
  "")
    ;;
  *)
    echo "usage: source scripts/dev-env.sh [on [VENV]|off]" >&2
    return 2
    ;;
esac
