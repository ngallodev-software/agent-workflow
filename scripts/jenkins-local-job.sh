#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
job_name="${JENKINS_JOB_NAME:-agent-workflow-local}"
branch="${JENKINS_BRANCH:-master}"
repo_url="${JENKINS_REPO_URL:-$(git -C "$root" rev-parse --show-toplevel)}"
if [[ -f "$root/.git" ]]; then
  common_dir="$(git -C "$root" rev-parse --path-format=absolute --git-common-dir)"
  repo_url="$(dirname "$common_dir")"
fi
jenkins_home="${JENKINS_HOME:-/var/lib/jenkins}"
job_dir="$jenkins_home/jobs/$job_name"
config="$job_dir/config.xml"
case "${1:-}" in
  configure)
    mkdir -p "$job_dir"
    tmp="$job_dir/config.xml.tmp"
    sed -e "s#__REPO__#$repo_url#g" -e "s#__JOB__#$job_name#g" -e "s#__BRANCH__#$branch#g" \
      "$root/scripts/jenkins-local-job.xml" > "$tmp"
    mv "$tmp" "$config"
    echo "configured $job_name at $config"
    echo "Reload Jenkins, then inspect: $JENKINS_URL/job/$job_name/"
    ;;
  inspect)
    test -r "$config"
    rg -n 'description|pollSCM|__REPO__|<url>|scriptPath|disabled' "$config" || true
    ;;
  *) echo "usage: $0 configure|inspect" >&2; exit 2 ;;
esac
