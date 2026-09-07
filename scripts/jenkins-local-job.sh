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
  config_home="${XDG_CONFIG_HOME:-}"
  home_dir="${HOME:-}"
  if [[ -z "$home_dir" ]] && command -v getent >/dev/null 2>&1; then
    home_dir="$(getent passwd "$(id -u)" | cut -d: -f6)"
  fi
  config_paths=()
  if [[ -n "${JENKINS_CONFIG_FILE:-}" ]]; then
    config_paths+=("$JENKINS_CONFIG_FILE")
  else
    [[ -n "$config_home" ]] && config_paths+=("$config_home/agent-workflow/jenkins.env")
    [[ -n "$home_dir" ]] && config_paths+=("$home_dir/.config/agent-workflow/jenkins.env")
  fi
  for config_path in "${config_paths[@]}"; do
    if [[ -r "$config_path" ]]; then
    # shellcheck disable=SC1090
      source "$config_path"
      break
    fi
  done
  if [[ -z "${JENKINS_CONFIG_FILE:-}" && -n "$home_dir" && -r "$home_dir/.config/osint-suite/jenkins.env" ]]; then
    # shellcheck disable=SC1090
    source "$home_dir/.config/osint-suite/jenkins.env"
    if [[ -z "${JENKINS_USER:-}" || -z "${JENKINS_TOKEN:-}" ]]; then
      JENKINS_USER="${OSINT_JENKINS_USER:-}"
      JENKINS_TOKEN="${OSINT_JENKINS_TOKEN:-}"
      JENKINS_URL="${OSINT_JENKINS_URL:-$jenkins_url}"
    fi
  fi
  [[ -n "${JENKINS_USER:-}" && -n "${JENKINS_TOKEN:-}" ]] || {
    echo "JENKINS_USER and JENKINS_TOKEN are required to trigger $job_name" >&2
    exit 2
  }
  jenkins_url="${JENKINS_URL:-$jenkins_url}"
  mkdir -p "$(dirname "$cli")"
  if ! jar tf "$cli" >/dev/null 2>&1; then
    tmp_cli="$(mktemp "${cli}.XXXXXX")"
    trap 'rm -f "$tmp_cli"' RETURN
    curl -fsS "$jenkins_url/jnlpJars/jenkins-cli.jar" -o "$tmp_cli"
    jar tf "$tmp_cli" >/dev/null
    mv "$tmp_cli" "$cli"
    trap - RETURN
  fi
  java -jar "$cli" -s "$jenkins_url" -auth "$JENKINS_USER:$JENKINS_TOKEN" -http build "$job_name"
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
