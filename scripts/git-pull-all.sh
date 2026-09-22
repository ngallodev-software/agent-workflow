#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARENT="$(dirname "$ROOT")"

CONTRACTS_SOURCE=""
COMPARATIVE_EVAL_SOURCE=""
SPECGEN_SOURCE=""
BENCHMARK_SOURCE=""
ALLOW_DIRTY=0
ALLOW_CREDENTIAL_HELPER=0

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
  --allow-credential-helper
  -h, --help

The script never switches branches, resets files, stashes changes, or creates
merge commits. Every repository must be on a local branch with an upstream.
Dirty repositories fail closed unless --allow-dirty is explicitly supplied;
even with that override, git pull --ff-only remains authoritative and may
refuse an update that conflicts with local changes.

Authentication is non-interactive and credential-store-safe by default. GitHub
HTTPS remotes use a one-shot token from GH_TOKEN/GITHUB_TOKEN or read-only
`gh auth token` with Git credential helpers disabled. The script never writes
Git credential configuration or remote URLs. Pass --allow-credential-helper
only to opt back into the repository's configured credential helper.

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
    --allow-credential-helper) ALLOW_CREDENTIAL_HELPER=1 ;;
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

  local remote remote_url
  remote="${upstream%%/*}"
  remote_url="$(git -C "$source" remote get-url "$remote" 2>/dev/null || true)"
  [[ -n "$remote_url" ]] || {
    echo "$label upstream remote URL could not be resolved: $upstream" >&2
    exit 1
  }

  printf 'pulling %-28s branch=%s upstream=%s before=%s\n' "$label" "$branch" "$upstream" "$before"

  if [[ "$remote_url" == https://github.com/* || "$remote_url" == http://github.com/* ]]; then
    if [[ "$ALLOW_CREDENTIAL_HELPER" -eq 1 ]]; then
      # Explicit compatibility escape hatch. Keep the operation non-interactive,
      # but allow the caller's configured helper to satisfy GitHub auth.
      GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=Never \
        git -C "$source" pull --ff-only
    else
      # Do not invoke or mutate Git Credential Manager from an installer/update
      # script. Supply a one-shot token through GIT_ASKPASS while disabling the
      # configured credential helper for this command only.
      local token auth_dir
      token="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
      if [[ -z "$token" ]] && command -v gh >/dev/null 2>&1; then
        token="$(gh auth token --hostname github.com 2>/dev/null || true)"
      fi
      [[ -n "$token" ]] || {
        echo "$label uses a GitHub HTTPS remote but no non-persistent token is available." >&2
        echo "Set GH_TOKEN/GITHUB_TOKEN, authenticate with 'gh auth login', use an SSH remote," >&2
        echo "or explicitly pass --allow-credential-helper." >&2
        exit 1
      }
      auth_dir="$(mktemp -d "${TMPDIR:-/tmp}/agent-workflow-git-auth.XXXXXX")"
      chmod 700 "$auth_dir"
      printf '%s' "$token" >"$auth_dir/token"
      chmod 600 "$auth_dir/token"
      cat >"$auth_dir/askpass" <<'ASKPASS'
#!/usr/bin/env bash
case "$1" in
  *Username*|*username*) printf '%s\n' "x-access-token" ;;
  *Password*|*password*) cat "$GIT_PULL_ALL_TOKEN_FILE" ;;
  *) exit 1 ;;
esac
ASKPASS
      chmod 700 "$auth_dir/askpass"
      if ! GIT_PULL_ALL_TOKEN_FILE="$auth_dir/token" \
           GIT_ASKPASS="$auth_dir/askpass" \
           GIT_TERMINAL_PROMPT=0 \
           GIT_CONFIG_COUNT=1 \
           GIT_CONFIG_KEY_0=credential.helper \
           GIT_CONFIG_VALUE_0= \
           git -C "$source" pull --ff-only; then
        rm -rf "$auth_dir"
        exit 1
      fi
      rm -rf "$auth_dir"
      unset token
    fi
  else
    # SSH and local/file transports do not use Git's HTTP credential helper.
    # Keep terminal credential prompting disabled at the Git layer.
    GIT_TERMINAL_PROMPT=0 git -C "$source" pull --ff-only
  fi

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
