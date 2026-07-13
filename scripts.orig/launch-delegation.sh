#!/usr/bin/env bash
set -euo pipefail
usage() {
  cat <<'EOF'
Usage: launch-delegation.sh SESSION WORKDIR PROMPT_FILE -- COMMAND [ARGS...]
Example: launch-delegation.sh osint-p0-01 /worktrees/p0-01 prompt.md -- codex exec --full-auto -
Requires tmux. The prompt is passed to COMMAND on stdin.
EOF
}
[[ $# -ge 5 ]] || { usage >&2; exit 2; }
SESSION="$1"; WORKDIR="$2"; PROMPT_FILE="$3"; shift 3
[[ "${1:-}" == "--" ]] || { usage >&2; exit 2; }
shift
[[ $# -gt 0 ]] || { usage >&2; exit 2; }
command -v tmux >/dev/null 2>&1 || { echo "tmux is required" >&2; exit 127; }
[[ -d "$WORKDIR" ]] || { echo "workdir not found: $WORKDIR" >&2; exit 2; }
[[ -f "$PROMPT_FILE" ]] || { echo "prompt not found: $PROMPT_FILE" >&2; exit 2; }
tmux has-session -t "$SESSION" 2>/dev/null && { echo "session exists: $SESSION" >&2; exit 2; }
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$WORKDIR/.delegations/$SESSION"; mkdir -p "$STATE_DIR"
PROMPT_COPY="$STATE_DIR/prompt.md"; LOG_FILE="$STATE_DIR/output.log"
STATUS_FILE="$STATE_DIR/status.json"; RUNNER="$STATE_DIR/run.sh"
cp "$PROMPT_FILE" "$PROMPT_COPY"
printf '%q ' "$@" > "$STATE_DIR/command.txt"; printf '\n' >> "$STATE_DIR/command.txt"
python3 "$SCRIPT_DIR/session_status.py" "$STATUS_FILE" --session "$SESSION" --workdir "$WORKDIR" --prompt "$PROMPT_COPY" --log "$LOG_FILE" --status launched
{
  echo '#!/usr/bin/env bash'
  echo 'set -o pipefail'
  printf 'cd %q\n' "$WORKDIR"
  printf 'cat %q | ' "$PROMPT_COPY"
  printf '%q ' "$@"
  printf '2>&1 | tee -a %q\n' "$LOG_FILE"
  echo 'rc=${PIPESTATUS[1]}'
  echo 'if [[ $rc -eq 0 ]]; then final_status=completed; else final_status=failed; fi'
  printf 'python3 %q %q --status "$final_status" --exit-code "$rc"\n' "$SCRIPT_DIR/session_status.py" "$STATUS_FILE"
  echo 'exit "$rc"'
} > "$RUNNER"
chmod +x "$RUNNER"
tmux new-session -d -s "$SESSION" -c "$WORKDIR" "$RUNNER"
echo "launched: $SESSION"
echo "foreground: tmux attach -t $SESSION"
echo "log: $LOG_FILE"
