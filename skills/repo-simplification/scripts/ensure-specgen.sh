#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_URL="${SPECGEN_REPOSITORY_URL:-https://github.com/ngallodev-software/specgen-aw.git}"

if command -v specgen >/dev/null 2>&1 && specgen version >/dev/null 2>&1; then
  echo "SpecGen available: $(specgen version)"
  exit 0
fi

cat >&2 <<EOF
SpecGen-AW is not installed or its 'specgen version' check failed.
Install it from GitHub with the maintained installer:
  git clone --depth 1 $REPOSITORY_URL specgen-aw
  (cd specgen-aw && ./scripts/install.sh)

Run this helper with --install to perform that explicit bootstrap.
EOF

[[ "${1:-}" == "--install" ]] || exit 1
command -v git >/dev/null 2>&1 || { echo "git is required for SpecGen installation" >&2; exit 127; }

temporary_root="$(mktemp -d)"
trap 'rm -rf "$temporary_root"' EXIT
git clone --depth 1 "$REPOSITORY_URL" "$temporary_root/specgen-aw"
"$temporary_root/specgen-aw/scripts/install.sh"

command -v specgen >/dev/null 2>&1 && specgen version >/dev/null 2>&1 || {
  echo "SpecGen installation completed but 'specgen version' is still unavailable" >&2
  exit 1
}
echo "SpecGen available: $(specgen version)"
