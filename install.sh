#!/bin/sh
set -eu

# This file has two deliberately small entry points.  From a checkout or a
# release bundle it delegates to the full installer.  When streamed to `sh`
# it is the immutable-tag bootstrap and has no mutable-branch fallback.
case "$0" in
  */*)
    install_script=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
    if [ -f "$install_script/scripts/install-source.sh" ] &&
       { [ -f "$install_script/pyproject.toml" ] || [ -f "$install_script/.release-bundle" ]; }; then
      AGENT_WORKFLOW_SOURCE_ROOT=$install_script
      export AGENT_WORKFLOW_SOURCE_ROOT
      exec /bin/bash "$install_script/scripts/install-source.sh" "$@"
    fi
    ;;
esac

usage() {
  cat <<'EOF'
Usage: curl -fsSL https://github.com/ngallodev-software/agent-workflow/raw/<tag>/install.sh \
  | sh -s -- --version <tag>

The release reference is required and must be an immutable semantic-version
tag.  Native Windows is not supported; Windows users should use WSL2.
EOF
}

VERSION=${AGENT_WORKFLOW_RELEASE_VERSION:-}
PYTHON_BIN=${AGENT_WORKFLOW_INSTALL_PYTHON:-}
while [ "$#" -gt 0 ]; do
  case "$1" in
    --version)
      [ "$#" -ge 2 ] || { echo "--version requires a value" >&2; exit 2; }
      VERSION=$2
      shift 2
      ;;
    --python)
      [ "$#" -ge 2 ] || { echo "--python requires a value" >&2; exit 2; }
      PYTHON_BIN=$2
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown bootstrap option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

case "$VERSION" in
  v[0-9]*.[0-9]*.[0-9]*|[0-9]*.[0-9]*.[0-9]*) ;;
  *) echo "an immutable semantic-version tag is required (for example v0.7.6)" >&2; exit 2 ;;
esac
case "$VERSION" in v*) TAG=$VERSION ;; *) TAG=v$VERSION ;; esac
RELEASE_VERSION=${TAG#v}

OS=$(uname -s 2>/dev/null || echo unknown)
ARCH=$(uname -m 2>/dev/null || echo unknown)
case "$OS" in
  Linux)
    if [ -r /proc/version ] && grep -Eiq 'microsoft|wsl' /proc/version; then
      PLATFORM=wsl2
    else
      PLATFORM=linux
    fi
    ;;
  Darwin) PLATFORM=macos ;;
  *) echo "unsupported operating system: $OS (native Windows is not supported; use WSL2)" >&2; exit 1 ;;
esac
case "$ARCH" in
  x86_64|amd64) ARCH_LABEL=x86_64 ;;
  aarch64|arm64) ARCH_LABEL=arm64 ;;
  *) echo "unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

if [ -z "$PYTHON_BIN" ]; then
  PYTHON_BIN=$(command -v python3 2>/dev/null || true)
fi
[ -n "$PYTHON_BIN" ] || { echo "Python 3.11+ is required (python3 was not found)" >&2; exit 1; }
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "Python interpreter not found: $PYTHON_BIN" >&2; exit 1; }
"$PYTHON_BIN" -c 'import sys; sys.exit("Python 3.11+ is required") if sys.version_info < (3, 11) else None' || exit 1
command -v curl >/dev/null 2>&1 || { echo "curl is required for release bootstrap" >&2; exit 1; }

# The default is release/download/<tag>; it is intentionally never a branch.
# The file:// override is limited to offline tests; HTTPS remains pinned to the
# same repository and tag-shaped release path.
if [ -n "${AGENT_WORKFLOW_RELEASE_BASE_URL:-}" ]; then
  BASE_URL=$AGENT_WORKFLOW_RELEASE_BASE_URL
  case "$BASE_URL" in
    file://*|https://github.com/ngallodev-software/agent-workflow/releases/download/$TAG) ;;
    *) echo "release base must be the tagged GitHub release or a file:// test mirror" >&2; exit 2 ;;
  esac
else
  BASE_URL=https://github.com/ngallodev-software/agent-workflow/releases/download/$TAG
fi
BUNDLE=agent-workflow-${RELEASE_VERSION}-${PLATFORM}.tar.gz
MANIFEST=SHA256SUMS
TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/agent-workflow.XXXXXX") || exit 1
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT HUP INT TERM

curl -fsSL "$BASE_URL/$MANIFEST" -o "$TMP_DIR/$MANIFEST"
curl -fsSL "$BASE_URL/$BUNDLE" -o "$TMP_DIR/$BUNDLE"

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    echo "sha256sum or shasum is required to verify release artifacts" >&2
    return 1
  fi
}
manifest_digest() {
  awk -v target="$1" '$2 == target || $2 == "*" target { print $1; exit }' "$TMP_DIR/$MANIFEST"
}
verify_artifact() {
  artifact=$1
  expected=$(manifest_digest "$(basename "$artifact")")
  case "$expected" in
    ''|*[!0123456789abcdefABCDEF]*) echo "checksum manifest has no valid entry for $(basename "$artifact")" >&2; return 1 ;;
  esac
  [ "${#expected}" -eq 64 ] || { echo "invalid checksum length for $(basename "$artifact")" >&2; return 1; }
  actual=$(sha256 "$artifact")
  [ "$actual" = "$expected" ] || {
    echo "checksum verification failed: $(basename "$artifact")" >&2
    return 1
  }
}
verify_artifact "$TMP_DIR/$BUNDLE"

tar -tzf "$TMP_DIR/$BUNDLE" | awk '
  {
    if (substr($0, 1, 1) == "/") bad=1
    count=split($0, parts, "/")
    for (i=1; i<=count; i++) if (parts[i] == "..") bad=1
  }
  END { exit bad }
' || { echo "release bundle contains an unsafe archive path" >&2; exit 1; }
tar -xzf "$TMP_DIR/$BUNDLE" -C "$TMP_DIR"
BUNDLE_ROOT=$TMP_DIR/agent-workflow-${RELEASE_VERSION}-${PLATFORM}
[ -f "$BUNDLE_ROOT/install.sh" ] || { echo "release bundle is missing install.sh" >&2; exit 1; }
WHEEL=$(find "$BUNDLE_ROOT" -type f -name 'agent_workflow-*.whl' -print | head -n 1)
[ -n "$WHEEL" ] || { echo "release bundle is missing its wheel" >&2; exit 1; }
verify_artifact "$WHEEL"

exec /bin/sh "$BUNDLE_ROOT/install.sh" --python "$PYTHON_BIN" --wheel "$WHEEL"
