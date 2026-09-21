#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ORIGINAL_AGENT_WORKFLOW="$(command -v agent-workflow 2>/dev/null || true)"
VENV_ARG=""
VERIFY_ONLY=0
BOOTSTRAP_BUILD=1

usage() {
  cat <<'USAGE'
Usage: bash scripts/build-install.sh [--venv PATH] [--verify-only] [--no-bootstrap-build]

Build Agent-Workflow from this checkout and install its wheel into the active
development virtualenv. This script never installs to the user Python
environment and never creates a virtualenv.

Virtualenv selection:
  1. --venv PATH
  2. AGENT_WORKFLOW_VENV
  3. VIRTUAL_ENV
  4. active python3 virtualenv
  5. repository .venv
  6. virtualenv inferred from the agent-workflow launcher
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv)
      shift
      [[ $# -gt 0 ]] || { echo "--venv requires a value" >&2; exit 2; }
      VENV_ARG="$1"
      ;;
    --verify-only) VERIFY_ONLY=1 ;;
    --no-bootstrap-build) BOOTSTRAP_BUILD=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 127; }

resolve_path() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
}

is_venv() {
  [[ -x "$1/bin/python" || -x "$1/bin/python3" ]]
}

active_python_venv() {
  python3 - <<'PY'
import sys
print(sys.prefix if sys.prefix != sys.base_prefix else "")
PY
}

infer_venv_from_launcher() {
  local launcher="$1" resolved parent candidate
  [[ -n "$launcher" ]] || return 1
  resolved="$(resolve_path "$launcher")"
  parent="$(dirname "$resolved")"
  candidate="$(dirname "$parent")"
  if is_venv "$candidate"; then
    printf '%s\n' "$candidate"
    return 0
  fi
  return 1
}

if [[ -n "$VENV_ARG" ]]; then
  VENV="$(resolve_path "$VENV_ARG")"
elif [[ -n "${AGENT_WORKFLOW_VENV:-}" ]]; then
  VENV="$(resolve_path "$AGENT_WORKFLOW_VENV")"
elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
  VENV="$(resolve_path "$VIRTUAL_ENV")"
else
  ACTIVE_PREFIX="$(active_python_venv)"
  if [[ -n "$ACTIVE_PREFIX" ]]; then
    VENV="$(resolve_path "$ACTIVE_PREFIX")"
  elif is_venv "$ROOT/.venv"; then
    VENV="$(resolve_path "$ROOT/.venv")"
  else
    AW_ON_PATH="$(command -v agent-workflow 2>/dev/null || true)"
    VENV="$(infer_venv_from_launcher "$AW_ON_PATH" || true)"
  fi
fi

[[ -n "${VENV:-}" ]] || {
  echo "no development virtualenv could be resolved; activate it or pass --venv PATH" >&2
  exit 1
}
is_venv "$VENV" || { echo "selected path is not a virtualenv: $VENV" >&2; exit 1; }

if [[ -x "$VENV/bin/python" ]]; then PYTHON="$VENV/bin/python"; else PYTHON="$VENV/bin/python3"; fi
AW_LAUNCHER="$VENV/bin/agent-workflow"
# Use the same venv-local config/state/data layout that benchmark/dev runs use.
# This affects only this build/install process; source scripts/dev-env.sh manually
# when the calling shell should remain in the isolated environment.
source "$ROOT/scripts/dev-env.sh"
aw_dev_env_on "$VENV" >/dev/null

echo "Agent-Workflow source: $ROOT"
echo "target virtualenv: $VENV"
echo "target Python: $PYTHON"

"$PYTHON" - "$VENV" <<'PY'
from pathlib import Path
import sys
expected = Path(sys.argv[1]).resolve()
if sys.prefix == sys.base_prefix:
    raise SystemExit(f"selected interpreter is not a virtualenv: {sys.executable}")
if Path(sys.prefix).resolve() != expected:
    raise SystemExit(f"selected interpreter prefix mismatch: expected {expected}, observed {sys.prefix}")
if sys.version_info < (3, 11):
    raise SystemExit("Agent-Workflow requires Python 3.11+")
PY

EXPECTED_VERSION="$("$PYTHON" - "$ROOT/pyproject.toml" <<'PY'
from pathlib import Path
import sys, tomllib
print(tomllib.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["project"]["version"])
PY
)"

verify_installed_state() {
  "$PYTHON" - "$ROOT" "$EXPECTED_VERSION" "$VENV" <<'PY'
from importlib import metadata
from pathlib import Path
import hashlib, json, sys, sysconfig

root = Path(sys.argv[1]).resolve()
expected_version = sys.argv[2]
venv = Path(sys.argv[3]).resolve()
purelib = Path(sysconfig.get_paths()["purelib"]).resolve()

try:
    dist = metadata.distribution("agent-workflow")
except metadata.PackageNotFoundError as exc:
    raise SystemExit("agent-workflow is not installed in the selected virtualenv") from exc

if dist.version != expected_version:
    raise SystemExit(f"version mismatch: expected {expected_version}, installed {dist.version}")

location = Path(dist.locate_file("")).resolve()
try:
    location.relative_to(purelib)
except ValueError as exc:
    raise SystemExit(f"distribution resolves outside selected virtualenv: {location}") from exc

raw = dist.read_text("direct_url.json")
if raw and json.loads(raw).get("dir_info", {}).get("editable") is True:
    raise SystemExit("Agent-Workflow is still installed editable")

module = Path(__import__("agent_workflow").__file__).resolve()
try:
    module.relative_to(purelib)
except ValueError as exc:
    raise SystemExit(f"Agent-Workflow import resolves outside selected virtualenv: {module}") from exc

source_root = root / "schemas"
source = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(source_root.glob("*.json"))
}
installed_root = venv / "share" / "agent-workflow" / "schemas"
installed = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted(installed_root.glob("*.json"))
}
if source != installed:
    raise SystemExit(
        "installed schema manifest differs from source; "
        f"missing={sorted(set(source)-set(installed))}, "
        f"extra={sorted(set(installed)-set(source))}, "
        f"changed={sorted(k for k in set(source)&set(installed) if source[k] != installed[k])}"
    )
bad = sorted(name for name in installed if name.startswith("benchmark-"))
if bad:
    raise SystemExit("core install unexpectedly owns benchmark schemas: " + ", ".join(bad))

scripts = {
    ep.name: ep.value
    for ep in metadata.entry_points(group="console_scripts")
    if getattr(ep, "dist", None) is not None
    and ep.dist.metadata.get("Name", "").lower().replace("_", "-") == "agent-workflow"
}
expected = {
    "agent-workflow": "agent_workflow.cli:main",
    "agent-workflow-mcp": "agent_workflow.mcp.server:main",
}
if scripts != expected:
    raise SystemExit(f"unexpected Agent-Workflow console scripts: {scripts}")

dist_infos = sorted(purelib.glob("agent_workflow-*.dist-info"))
egg_infos = sorted(purelib.glob("agent_workflow*.egg-info"))
editable = sorted(purelib.glob("__editable__.agent_workflow-*.pth"))
editable += sorted(purelib.glob("__editable___agent_workflow_*_finder.py"))
if len(dist_infos) != 1:
    raise SystemExit("expected exactly one Agent-Workflow dist-info directory")
if egg_infos:
    raise SystemExit("stale Agent-Workflow egg-info: " + ", ".join(map(str, egg_infos)))
if editable:
    raise SystemExit("stale editable Agent-Workflow metadata: " + ", ".join(map(str, editable)))

launcher = venv / "bin" / "agent-workflow"
if not launcher.is_file():
    raise SystemExit(f"launcher missing from selected virtualenv: {launcher}")
first = launcher.read_text(encoding="utf-8", errors="replace").splitlines()[0]
if str(venv / "bin") not in first:
    raise SystemExit(f"launcher shebang does not target selected virtualenv: {first}")

try:
    benchmark = metadata.distribution("agent-workflow-benchmark")
except metadata.PackageNotFoundError:
    benchmark = None
if benchmark is not None:
    bench_root = Path(benchmark.locate_file("")).resolve()
    try:
        bench_root.relative_to(purelib)
    except ValueError as exc:
        raise SystemExit(f"benchmark plugin resolves outside selected virtualenv: {bench_root}") from exc
    print(f"shared benchmark plugin remains installed: {benchmark.version}")

print(f"verified Agent-Workflow wheel install: {dist.version}; schemas={len(installed)}")
PY

  "$AW_LAUNCHER" --version >/dev/null
  "$AW_LAUNCHER" --no-plugins --help >/dev/null

  "$PYTHON" - <<'PY'
from agent_workflow.config import load_settings
from agent_workflow.decisions import decision_mode
from agent_workflow.semantic.typesafe import capability

settings = load_settings()
mode = decision_mode(settings.decision_mode)
if mode.provider == "typesafe":
    cap = capability(settings)
    if not cap.get("typesafe_sdk_installed"):
        raise SystemExit(
            f"decision mode {mode.name!r} requires the TypeSafe SDK in the shared virtualenv"
        )
    if not cap.get("api_key_configured"):
        raise SystemExit(
            f"decision mode {mode.name!r} requires TYPESAFE_API_KEY in the runtime environment"
        )
    if mode.capture_comparison:
        from agent_workflow.comparative_eval import shared_library_status
        shared = shared_library_status()
        if not shared.get("installed") or not shared.get("compatible"):
            raise SystemExit(
                "comparative decision mode requires compatible "
                "agent-workflow-comparative-eval in the shared virtualenv"
            )
    print(
        f"semantic runtime verified: mode={mode.name}; "
        "typesafe_api_key=configured"
    )
else:
    print("semantic runtime verified: mode=deterministic; TypeSafe key not required")
PY

  local active
  active="$(command -v agent-workflow 2>/dev/null || true)"
  [[ -n "$active" ]] || { echo "agent-workflow is not on PATH" >&2; return 1; }
  if [[ "$(resolve_path "$active")" != "$(resolve_path "$AW_LAUNCHER")" ]]; then
    echo "stale/shadowing agent-workflow launcher detected:" >&2
    echo "  PATH resolves: $active" >&2
    echo "  expected:      $AW_LAUNCHER" >&2
    echo "activate $VENV and run: hash -r" >&2
    return 1
  fi
}

if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  verify_installed_state
  exit 0
fi

"$PYTHON" -m pip --version >/dev/null 2>&1 || {
  echo "pip is unavailable in selected virtualenv: $VENV" >&2
  exit 1
}

if ! "$PYTHON" -c 'import build, setuptools' >/dev/null 2>&1; then
  [[ "$BOOTSTRAP_BUILD" -eq 1 ]] || {
    echo "build/setuptools tooling is missing from $VENV" >&2
    exit 1
  }
  echo "installing build tooling into selected virtualenv"
  "$PYTHON" -m pip install --upgrade 'build>=1,<2' 'setuptools>=61'
fi

echo "cleaning repository build artifacts"
rm -rf "$ROOT/build" "$ROOT/dist" "$ROOT/src/agent_workflow.egg-info"

echo "building Agent-Workflow wheel"
(
  cd "$ROOT"
  "$PYTHON" scripts/verify-wheel-source.py
  "$PYTHON" -m build --wheel
)

WHEELS=()
while IFS= read -r path; do
  [[ -n "$path" ]] && WHEELS+=("$path")
done < <(find "$ROOT/dist" -maxdepth 1 -type f -name 'agent_workflow-*.whl' -print | sort)
[[ "${#WHEELS[@]}" -eq 1 ]] || {
  echo "expected exactly one Agent-Workflow wheel, found ${#WHEELS[@]}" >&2
  exit 1
}
WHEEL="${WHEELS[0]}"
echo "built wheel: $WHEEL"

"$PYTHON" - "$ROOT" "$WHEEL" "$EXPECTED_VERSION" <<'PY'
from pathlib import Path
from zipfile import ZipFile
from email.parser import Parser
import configparser, hashlib, io, sys

root = Path(sys.argv[1]).resolve()
wheel = Path(sys.argv[2]).resolve()
expected_version = sys.argv[3]
source = {
    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
    for p in sorted((root / "schemas").glob("*.json"))
}

with ZipFile(wheel) as archive:
    names = archive.namelist()
    meta_name = next(n for n in names if n.endswith(".dist-info/METADATA"))
    meta = Parser().parsestr(archive.read(meta_name).decode())
    if meta["Name"] != "agent-workflow" or meta["Version"] != expected_version:
        raise SystemExit(f"unexpected wheel metadata: {meta['Name']} {meta['Version']}")

    marker = "/share/agent-workflow/schemas/"
    schemas = {
        Path(n).name: hashlib.sha256(archive.read(n)).hexdigest()
        for n in names if marker in n and n.endswith(".json")
    }
    if source != schemas:
        raise SystemExit(
            "wheel schema manifest differs from source; "
            f"missing={sorted(set(source)-set(schemas))}, extra={sorted(set(schemas)-set(source))}"
        )
    if any(name.startswith("benchmark-") for name in schemas):
        raise SystemExit("core wheel unexpectedly carries benchmark schemas")

    ep_name = next(n for n in names if n.endswith(".dist-info/entry_points.txt"))
    parser = configparser.ConfigParser()
    parser.read_file(io.StringIO(archive.read(ep_name).decode()))
    console = dict(parser["console_scripts"])
    expected = {
        "agent-workflow": "agent_workflow.cli:main",
        "agent-workflow-mcp": "agent_workflow.mcp.server:main",
    }
    if console != expected:
        raise SystemExit(f"unexpected wheel console scripts: {console}")

print(f"verified wheel before install: version={expected_version}, schemas={len(source)}")
PY

echo "removing previous Agent-Workflow distribution from selected virtualenv"
"$PYTHON" -m pip uninstall -y agent-workflow >/dev/null 2>&1 || true

"$PYTHON" - <<'PY'
from pathlib import Path
import shutil, sys, sysconfig

purelib = Path(sysconfig.get_paths()["purelib"]).resolve()
bin_dir = Path(sys.executable).resolve().parent
paths = [purelib / "agent_workflow"]
paths += sorted(purelib.glob("agent_workflow-*.dist-info"))
paths += sorted(purelib.glob("agent_workflow*.egg-info"))
paths += sorted(purelib.glob("__editable__.agent_workflow-*.pth"))
paths += sorted(purelib.glob("__editable___agent_workflow_*_finder.py"))

for path in paths:
    if not path.exists() and not path.is_symlink():
        continue
    print(f"removing stale Agent-Workflow install artifact: {path}")
    shutil.rmtree(path) if path.is_dir() and not path.is_symlink() else path.unlink()

for name in ("agent-workflow", "agent-workflow-mcp"):
    path = bin_dir / name
    if path.exists() or path.is_symlink():
        print(f"removing stale venv launcher: {path}")
        path.unlink()
PY

echo "installing Agent-Workflow wheel into selected virtualenv"
"$PYTHON" -m pip install --no-deps --force-reinstall "$WHEEL"

verify_installed_state

echo
echo "Agent-Workflow install verified"
echo "  virtualenv: $VENV"
echo "  version: $EXPECTED_VERSION"
echo "  launcher: $AW_LAUNCHER"
echo "  wheel: $WHEEL"
echo "  config: $XDG_CONFIG_HOME/agent-workflow/config.toml"
echo "  state: $XDG_STATE_HOME/agent-workflow"
echo "  data: $XDG_DATA_HOME/agent-workflow"
echo
echo "For an interactive isolated dev/benchmark shell:"
echo "  source scripts/dev-env.sh on"
echo "Restore the previous shell environment afterward with:"
echo "  source scripts/dev-env.sh off"
if [[ -n "$ORIGINAL_AGENT_WORKFLOW" ]] && [[ "$(resolve_path "$ORIGINAL_AGENT_WORKFLOW")" != "$(resolve_path "$AW_LAUNCHER")" ]]; then
  echo
  echo "note: before this script, PATH resolved agent-workflow to:"
  echo "  $ORIGINAL_AGENT_WORKFLOW"
  echo "activate $VENV (or fix PATH) before invoking Agent-Workflow from this shell."
fi
echo
echo "If this shell cached an older ~/.local/bin launcher, run: hash -r"
