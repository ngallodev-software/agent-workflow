#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_URL="${CODEBASE_MEMORY_REPOSITORY_URL:-https://github.com/DeusData/codebase-memory-mcp.git}"
CONFIG_FILE="${CODEX_CONFIG_FILE:-${CODEX_HOME:-$HOME/.codex}/config.toml}"

configured_command() {
  [[ -r "$CONFIG_FILE" && -x "$(command -v python3 2>/dev/null || true)" ]] || return 0
  python3 - "$CONFIG_FILE" <<'PY'
import sys
import tomllib
from pathlib import Path

try:
    data = tomllib.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    command = data.get("mcp_servers", {}).get("codebase-memory-mcp", {}).get("command")
except (OSError, tomllib.TOMLDecodeError):
    command = None
if isinstance(command, str) and command:
    print(command)
PY
}

resolve_command() {
  local candidate="${CODEBASE_MEMORY_MCP_COMMAND:-}"
  if [[ -z "$candidate" ]]; then
    candidate="$(command -v codebase-memory-mcp 2>/dev/null || true)"
  fi
  if [[ -z "$candidate" ]]; then
    candidate="$(configured_command || true)"
  fi
  [[ -n "$candidate" ]] || return 1
  if [[ "$candidate" == */* ]]; then
    [[ -x "$candidate" ]] || return 1
    printf '%s\n' "$candidate"
  else
    command -v "$candidate"
  fi
}

probe() {
  local command_path="$1"
  if command -v timeout >/dev/null 2>&1; then
    timeout 5 "$command_path" --version
  else
    "$command_path" --version
  fi
}

if command_path="$(resolve_command 2>/dev/null)" && version="$(probe "$command_path" 2>/dev/null)"; then
  echo "codebase-memory-mcp available: $version"
  exit 0
fi

cat >&2 <<EOF
codebase-memory-mcp is not installed, not executable, or its --version probe failed.
Install it from GitHub with its maintained checksum-verifying installer:
  git clone --depth 1 $REPOSITORY_URL codebase-memory-mcp
  (cd codebase-memory-mcp && ./install.sh)

Run this helper with --install to perform that explicit bootstrap.
EOF

[[ "${1:-}" == "--install" ]] || exit 1
command -v git >/dev/null 2>&1 || { echo "git is required for codebase-memory-mcp installation" >&2; exit 127; }

temporary_root="$(mktemp -d)"
trap 'rm -rf "$temporary_root"' EXIT
git clone --depth 1 "$REPOSITORY_URL" "$temporary_root/codebase-memory-mcp"
bash "$temporary_root/codebase-memory-mcp/install.sh"

command_path="$(resolve_command 2>/dev/null || true)"
if [[ -z "$command_path" ]] || ! version="$(probe "$command_path" 2>/dev/null)"; then
  echo "codebase-memory-mcp installation completed but its --version probe is unavailable" >&2
  exit 1
fi
echo "codebase-memory-mcp available: $version"
