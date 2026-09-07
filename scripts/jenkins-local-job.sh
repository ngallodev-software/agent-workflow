#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
job_name="${JENKINS_JOB_NAME:-agent-workflow-local}"
branch="${JENKINS_BRANCH:-release-tooling}"
repo_url="${JENKINS_REPO_URL:-$(git -C "$root" rev-parse --show-toplevel)}"
if [[ -f "$root/.git" ]]; then
  common_dir="$(git -C "$root" rev-parse --path-format=absolute --git-common-dir)"
  repo_url="$(dirname "$common_dir")"
fi
jenkins_home="${JENKINS_HOME:-/var/lib/jenkins}"
jenkins_url="${JENKINS_URL:-http://127.0.0.1:8080}"
cli="${JENKINS_CLI:-/tmp/agent-workflow-jenkins-cli.jar}"
job_dir="$jenkins_home/jobs/$job_name"
config="$job_dir/config.xml"
trigger() {
  if [[ -r "${XDG_CONFIG_HOME:-$HOME/.config}/agent-workflow/jenkins.env" ]]; then
    # shellcheck disable=SC1090
    source "${XDG_CONFIG_HOME:-$HOME/.config}/agent-workflow/jenkins.env"
  fi
  [[ -n "${JENKINS_USER:-}" && -n "${JENKINS_TOKEN:-}" ]] || {
    echo "JENKINS_USER and JENKINS_TOKEN are required to trigger $job_name" >&2
    exit 2
  }
  mkdir -p "$(dirname "$cli")"
  [[ -s "$cli" ]] || curl -fsS "$jenkins_url/jnlpJars/jenkins-cli.jar" -o "$cli"
  java -jar "$cli" -s "$jenkins_url" -auth "$JENKINS_USER:$JENKINS_TOKEN" build "$job_name"
}
case "${1:-}" in
  configure)
    mkdir -p "$job_dir"
    tmp="$job_dir/config.xml.tmp"
    sed -e "s#__REPO__#$repo_url#g" -e "s#__JOB__#$job_name#g" -e "s#__BRANCH__#$branch#g" \
      "$root/scripts/jenkins-local-job.xml" > "$tmp"
    mv "$tmp" "$config"
    echo "configured $job_name at $config"
    echo "Reload Jenkins, then inspect: $jenkins_url/job/$job_name/"
    ;;
  inspect)
    test -r "$config"
    rg -n 'description|pollSCM|__REPO__|<url>|scriptPath|disabled' "$config" || true
    ;;
  trigger)
    [[ "$(git -C "$root" symbolic-ref --short HEAD 2>/dev/null || true)" == "release-tooling" ]] || {
      echo "not triggering $job_name: local branch is not release-tooling" >&2
      exit 0
    }
    trigger
    ;;
  install-hook)
    hook="$(git -C "$root" rev-parse --path-format=absolute --git-path hooks/post-commit)"
    mkdir -p "$(dirname "$hook")"
    cat >"$hook" <<EOF
#!/usr/bin/env bash
exec "$root/scripts/jenkins-local-post-commit"
EOF
    chmod 0755 "$hook"
    echo "installed local release-tooling Jenkins post-commit hook: $hook"
    ;;
  *) echo "usage: $0 configure|inspect|trigger|install-hook" >&2; exit 2 ;;
esac
