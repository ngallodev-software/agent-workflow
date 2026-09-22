#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARENT="$(dirname "$ROOT")"

CONTRACTS_SOURCE=""
COMPARATIVE_EVAL_SOURCE=""
SPECGEN_SOURCE=""
BENCHMARK_SOURCE=""
ALLOW_DIRTY=0

usage() {
  cat <<'USAGE'
Usage: scripts/git-pull-all.sh [options]

Fast-forward all repositories used by the local Agent-Workflow stack.

Options:
  --contracts-source PATH
  --comparative-eval-source PATH
  --specgen-source PATH
  --benchmark-source PATH
  --allow-dirty
  -h, --help

The script never switches branches, resets files, stashes changes, or creates
merge commits. Every repository must be on a local branch with an upstream.
Dirty repositories fail closed unless --allow-dirty is explicitly supplied;
even with that override, git pull --ff-only remains authoritative and may
refuse an update that conflicts with local changes.

Default sibling checkout layout:
  ../agent-workflow-spec-contracts
  ../agent-workflow-comparative-eval
  ../specgen-aw
  ../agent-workflow-benchmark

Agent-Workflow itself is updated last so a caller can safely re-exec a freshly
pulled build/install script after this command returns.
USAGE
}

resolve_path() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --contracts-source)
      shift; [[ $# -gt 0 ]] || { echo "--contracts-source requires a value" >&2; exit 2; }
      CONTRACTS_SOURCE="$1"
      ;;
    --comparative-eval-source)
      shift; [[ $# -gt 0 ]] || { echo "--comparative-eval-source requires a value" >&2; exit 2; }
      COMPARATIVE_EVAL_SOURCE="$1"
      ;;
    --specgen-source)
      shift; [[ $# -gt 0 ]] || { echo "--specgen-source requires a value" >&2; exit 2; }
      SPECGEN_SOURCE="$1"
      ;;
    --benchmark-source)
      shift; [[ $# -gt 0 ]] || { echo "--benchmark-source requires a value" >&2; exit 2; }
      BENCHMARK_SOURCE="$1"
      ;;
    --allow-dirty) ALLOW_DIRTY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

CONTRACTS_SOURCE="$(resolve_path "${CONTRACTS_SOURCE:-$PARENT/agent-workflow-spec-contracts}")"
COMPARATIVE_EVAL_SOURCE="$(resolve_path "${COMPARATIVE_EVAL_SOURCE:-$PARENT/agent-workflow-comparative-eval}")"
SPECGEN_SOURCE="$(resolve_path "${SPECGEN_SOURCE:-$PARENT/specgen-aw}")"
BENCHMARK_SOURCE="$(resolve_path "${BENCHMARK_SOURCE:-$PARENT/agent-workflow-benchmark}")"

pull_repo() {
  local label="$1" source="$2"
  [[ -d "$source" ]] || { echo "$label checkout missing: $source" >&2; exit 1; }
  git -C "$source" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
    echo "$label is not a Git worktree: $source" >&2
    exit 1
  }

  local dirty branch upstream before after
  dirty="$(git -C "$source" status --porcelain=v1 --untracked-files=normal)"
  if [[ -n "$dirty" && "$ALLOW_DIRTY" -ne 1 ]]; then
    echo "$label checkout is dirty; refusing to pull: $source" >&2
    git -C "$source" status --short >&2
    echo "commit/stash the changes or rerun git-pull-all.sh with --allow-dirty" >&2
    exit 1
  fi

  branch="$(git -C "$source" symbolic-ref --quiet --short HEAD || true)"
  [[ -n "$branch" ]] || {
    echo "$label checkout is detached; refusing to switch branches: $source" >&2
    exit 1
  }
  upstream="$(git -C "$source" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
  [[ -n "$upstream" ]] || {
    echo "$label branch $branch has no upstream; refusing to guess: $source" >&2
    exit 1
  }
  before="$(git -C "$source" rev-parse HEAD)"

  printf 'pulling %-28s branch=%s upstream=%s before=%s\n' "$label" "$branch" "$upstream" "$before"
  git -C "$source" pull --ff-only
  after="$(git -C "$source" rev-parse HEAD)"
  printf 'updated %-28s branch=%s before=%s after=%s\n' "$label" "$branch" "$before" "$after"
}

# Update dependencies first. Agent-Workflow itself is last because this helper
# may be invoked by build-install-all.sh, which re-execs the freshly pulled
# installer after all repositories have been updated.
pull_repo "contracts" "$CONTRACTS_SOURCE"
pull_repo "comparative-eval" "$COMPARATIVE_EVAL_SOURCE"
pull_repo "specgen" "$SPECGEN_SOURCE"
pull_repo "benchmark" "$BENCHMARK_SOURCE"
pull_repo "agent-workflow" "$ROOT"

echo
echo "Agent-Workflow stack repositories are fast-forward current."
