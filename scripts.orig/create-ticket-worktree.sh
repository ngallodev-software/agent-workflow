#!/usr/bin/env bash
set -euo pipefail
[[ $# -ge 3 ]] || { echo "usage: $0 REPO_PATH TICKET_ID BASE_REF [DEST]" >&2; exit 2; }
REPO="$(cd "$1" && pwd)"; TICKET="$2"; BASE="$3"; DEST="${4:-$(dirname "$REPO")/worktrees/$TICKET}"
BRANCH="impl/${TICKET,,}"
mkdir -p "$(dirname "$DEST")"
git -C "$REPO" worktree add -b "$BRANCH" "$DEST" "$BASE"
echo "$DEST"
