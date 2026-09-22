#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARENT="$(dirname "$ROOT")"

EXPECTED_CONTRACTS_VERSION="0.2.1"
EXPECTED_AGENT_WORKFLOW_VERSION="0.11.5"
EXPECTED_COMPARATIVE_EVAL_VERSION="0.1.0"
EXPECTED_SPECGEN_VERSION="0.2.4"
EXPECTED_BENCHMARK_VERSION="0.2.8"
EXPECTED_TYPESAFE_VERSION="0.6.0"

VENV_ARG=""
CONTRACTS_SOURCE_ARG=""
COMPARATIVE_EVAL_SOURCE_ARG=""
SPECGEN_SOURCE_ARG=""
BENCHMARK_SOURCE_ARG=""
VERIFY_ONLY=0
BOOTSTRAP_BUILD=1

usage() {
  cat <<'USAGE'
Usage: scripts/build-install-all.sh [options]

Build/install the complete local Agent-Workflow development stack into one
EXISTING virtualenv.

Options:
  --venv PATH
  --contracts-source PATH
  --comparative-eval-source PATH
  --specgen-source PATH
  --benchmark-source PATH
  --verify-only
  --no-bootstrap-build
  -h, --help

Default sibling checkout layout:
  ../agent-workflow-spec-contracts
  ../agent-workflow-comparative-eval
  ../specgen-aw
  ../agent-workflow-benchmark

Required versions:
  specgen-agent-workflow-contracts  0.2.1
  agent-workflow                    0.11.5
  agent-workflow-comparative-eval   0.1.0
  specgen                           0.2.4
  agent-workflow-benchmark          0.2.8
  typesafe-sdk                      0.6.0

The script never creates a venv, never uses pip --user, and never installs
editable packages. TYPESAFE_API_KEY is required because the resulting runtime is
configured for comparative TypeSafe decisions.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv)
      shift; [[ $# -gt 0 ]] || { echo "--venv requires a value" >&2; exit 2; }
      VENV_ARG="$1"
      ;;
    --contracts-source)
      shift; [[ $# -gt 0 ]] || { echo "--contracts-source requires a value" >&2; exit 2; }
      CONTRACTS_SOURCE_ARG="$1"
      ;;
    --comparative-eval-source)
      shift; [[ $# -gt 0 ]] || { echo "--comparative-eval-source requires a value" >&2; exit 2; }
      COMPARATIVE_EVAL_SOURCE_ARG="$1"
      ;;
    --specgen-source)
      shift; [[ $# -gt 0 ]] || { echo "--specgen-source requires a value" >&2; exit 2; }
      SPECGEN_SOURCE_ARG="$1"
      ;;
    --benchmark-source)
      shift; [[ $# -gt 0 ]] || { echo "--benchmark-source requires a value" >&2; exit 2; }
      BENCHMARK_SOURCE_ARG="$1"
      ;;
    --verify-only) VERIFY_ONLY=1 ;;
    --no-bootstrap-build) BOOTSTRAP_BUILD=0 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

resolve_path() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve())
PY
}

if [[ -n "$VENV_ARG" ]]; then
  VENV="$(resolve_path "$VENV_ARG")"
elif [[ -n "${AGENT_WORKFLOW_VENV:-}" ]]; then
  VENV="$(resolve_path "$AGENT_WORKFLOW_VENV")"
elif [[ -n "${VIRTUAL_ENV:-}" ]]; then
  VENV="$(resolve_path "$VIRTUAL_ENV")"
elif [[ -x "$ROOT/.venv/bin/python" || -x "$ROOT/.venv/bin/python3" ]]; then
  VENV="$(resolve_path "$ROOT/.venv")"
else
  echo "could not resolve an existing shared virtualenv" >&2
  exit 1
fi

if [[ -x "$VENV/bin/python" ]]; then
  PYTHON="$VENV/bin/python"
elif [[ -x "$VENV/bin/python3" ]]; then
  PYTHON="$VENV/bin/python3"
else
  echo "selected path is not a usable virtualenv: $VENV" >&2
  exit 1
fi

"$PYTHON" - "$VENV" <<'PY'
from pathlib import Path
import sys
venv = Path(sys.argv[1]).resolve()
if sys.prefix == sys.base_prefix:
    raise SystemExit("selected interpreter is not running in a virtualenv")
if Path(sys.prefix).resolve() != venv:
    raise SystemExit(f"interpreter prefix {Path(sys.prefix).resolve()} != requested venv {venv}")
if sys.version_info < (3, 11):
    raise SystemExit("Agent-Workflow stack requires Python >= 3.11")
PY

[[ -n "${TYPESAFE_API_KEY:-}" ]] || {
  echo "comparative stack requires TYPESAFE_API_KEY in the environment" >&2
  exit 1
}

CONTRACTS_SOURCE="$(resolve_path "${CONTRACTS_SOURCE_ARG:-$PARENT/agent-workflow-spec-contracts}")"
COMPARATIVE_EVAL_SOURCE="$(resolve_path "${COMPARATIVE_EVAL_SOURCE_ARG:-$PARENT/agent-workflow-comparative-eval}")"
SPECGEN_SOURCE="$(resolve_path "${SPECGEN_SOURCE_ARG:-$PARENT/specgen-aw}")"
BENCHMARK_SOURCE="$(resolve_path "${BENCHMARK_SOURCE_ARG:-$PARENT/agent-workflow-benchmark}")"

export VIRTUAL_ENV="$VENV"
export AGENT_WORKFLOW_VENV="$VENV"
export AGENT_WORKFLOW_BIN="$VENV/bin/agent-workflow"
export PATH="$VENV/bin:$PATH"
export XDG_CONFIG_HOME="$VENV/.xdg/config"
export XDG_STATE_HOME="$VENV/.xdg/state"
export XDG_DATA_HOME="$VENV/.xdg/data"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_STATE_HOME" "$XDG_DATA_HOME"

check_source() {
  local source="$1" expected_name="$2" expected_version="$3"
  [[ -f "$source/pyproject.toml" ]] || {
    echo "missing required source pyproject.toml: $source" >&2
    exit 1
  }
  "$PYTHON" - "$source/pyproject.toml" "$expected_name" "$expected_version" <<'PY'
from pathlib import Path
import sys, tomllib
path = Path(sys.argv[1])
expected_name, expected_version = sys.argv[2], sys.argv[3]
project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
if project.get("name") != expected_name or project.get("version") != expected_version:
    raise SystemExit(
        f"{path.parent}: observed {project.get('name')} {project.get('version')}; "
        f"expected {expected_name} {expected_version}"
    )
PY
  if [[ -f "$source/VERSION" ]]; then
    local observed
    observed="$(tr -d '\r\n' < "$source/VERSION")"
    [[ "$observed" == "$expected_version" ]] || {
      echo "$source/VERSION=$observed; expected $expected_version" >&2
      exit 1
    }
  fi
}

check_source "$CONTRACTS_SOURCE" "specgen-agent-workflow-contracts" "$EXPECTED_CONTRACTS_VERSION"
check_source "$ROOT" "agent-workflow" "$EXPECTED_AGENT_WORKFLOW_VERSION"
check_source "$COMPARATIVE_EVAL_SOURCE" "agent-workflow-comparative-eval" "$EXPECTED_COMPARATIVE_EVAL_VERSION"
check_source "$SPECGEN_SOURCE" "specgen" "$EXPECTED_SPECGEN_VERSION"
check_source "$BENCHMARK_SOURCE" "agent-workflow-benchmark" "$EXPECTED_BENCHMARK_VERSION"

write_stack_config() {
  local target="$XDG_CONFIG_HOME/agent-workflow/config.toml"
  mkdir -p "$(dirname "$target")"
  "$PYTHON" - "$target" "$VENV" <<'PY'
from pathlib import Path
import json, os, sys, tempfile, tomllib
target = Path(sys.argv[1])
venv = Path(sys.argv[2]).resolve()
q = json.dumps
rendered = "\n".join([
    "schema_version = 1",
    "",
    "[paths]",
    f"worktree_root = {q(str(venv / '.xdg/data/agent-workflow/worktrees'))}",
    f"state_root = {q(str(venv / '.xdg/state/agent-workflow'))}",
    "",
    "[plugins]",
    'enabled = ["agent-workflow-spec", "agent-workflow-benchmark"]',
    "",
    "[semantic]",
    'provider = "typesafe"',
    "",
    "[semantic.typesafe]",
    f"api_call_log = {q(str(venv / '.xdg' / 'state' / 'agent-workflow' / 'typesafe-api-calls.jsonl'))}",
    "",
    "[decision_policy]",
    'mode = "comparative"',
    'profile = "default"',
    "",
])
parsed = tomllib.loads(rendered)
assert parsed["decision_policy"]["mode"] == "comparative"
assert parsed["plugins"]["enabled"] == ["agent-workflow-spec", "agent-workflow-benchmark"]
with tempfile.NamedTemporaryFile(
    "w", encoding="utf-8", dir=target.parent, prefix=target.name + ".", delete=False
) as handle:
    handle.write(rendered)
    temp = Path(handle.name)
os.replace(temp, target)
print(f"stack config: {target}")
PY
}

verify_stack() {
  "$PYTHON" - <<'PY'
from importlib import metadata
from pathlib import Path
import json, os, shutil

expected = {
    "specgen-agent-workflow-contracts": "0.2.1",
    "agent-workflow": "0.11.5",
    "agent-workflow-comparative-eval": "0.1.0",
    "specgen": "0.2.4",
    "agent-workflow-benchmark": "0.2.8",
    "typesafe-sdk": "0.6.0",
}
for name, version in expected.items():
    try:
        observed = metadata.version(name)
    except metadata.PackageNotFoundError as exc:
        raise SystemExit(f"missing distribution: {name}=={version}") from exc
    if observed != version:
        raise SystemExit(f"{name} version {observed}; expected {version}")

for name in tuple(expected)[:-1]:
    dist = metadata.distribution(name)
    direct = Path(dist._path) / "direct_url.json"
    if direct.is_file():
        value = json.loads(direct.read_text(encoding="utf-8"))
        if value.get("dir_info", {}).get("editable"):
            raise SystemExit(f"{name} is installed editable")

from agent_workflow.config import load_settings
from agent_workflow.decisions import require_decision_runtime_ready
from agent_workflow.plugins import load_plugin_registry
from agent_workflow.comparative_eval import shared_library_status
from specgen.agent_workflow import AW_VERSION

settings = load_settings()
if settings.decision_mode != "comparative":
    raise SystemExit(f"decision mode {settings.decision_mode!r}; expected 'comparative'")
if settings.plugins_enabled != ("agent-workflow-spec", "agent-workflow-benchmark"):
    raise SystemExit(f"unexpected plugins: {settings.plugins_enabled!r}")
if settings.executors.get("codex", [None])[0] != "codex":
    raise SystemExit(f"Codex executor is not direct: {settings.executors.get('codex')!r}")

semantic = require_decision_runtime_ready(settings)
if semantic.get("ready") is not True:
    raise SystemExit(f"semantic runtime not ready: {semantic}")

shared = shared_library_status()
if not shared.get("installed") or not shared.get("compatible"):
    raise SystemExit(f"comparative-eval incompatible: {shared}")

registry = load_plugin_registry(settings.plugins_enabled)
loaded = tuple(item.descriptor.name for item in registry.loaded)
if loaded != ("agent-workflow-spec", "agent-workflow-benchmark"):
    raise SystemExit(f"unexpected loaded plugins: {loaded!r}")

if AW_VERSION != "0.11.5":
    raise SystemExit(f"SpecGen target {AW_VERSION}; expected 0.11.5")

codex = shutil.which("codex")
if not codex:
    raise SystemExit("direct Codex executable is not available")
if Path(codex).name == "agent-workflow-codex":
    raise SystemExit("agent-workflow-codex wrapper may not be used")

if not os.environ.get("TYPESAFE_API_KEY"):
    raise SystemExit("TYPESAFE_API_KEY is not configured")

print("")
print("Agent-Workflow stack verification:")
for name, version in expected.items():
    print(f"  {name:<34} {version}")
print(f"  {'decision-mode':<34} comparative")
print(f"  {'semantic-provider':<34} typesafe")
print(f"  {'plugins':<34} {', '.join(loaded)}")
print(f"  {'codex':<34} {codex}")
print(f"  {'TYPESAFE_API_KEY':<34} configured")
PY

  "$PYTHON" -m pip check
  "$VENV/bin/agent-workflow" --version >/dev/null
  "$VENV/bin/agent-workflow" --no-plugins --help >/dev/null
  "$VENV/bin/specgen" --help >/dev/null
  "$VENV/bin/contract-bundle" --help >/dev/null
  codex --version >/dev/null
}

if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  verify_stack
  exit 0
fi

if [[ "$BOOTSTRAP_BUILD" -eq 1 ]]; then
  "$PYTHON" -m pip install --upgrade     pip build wheel "setuptools>=77"     "jsonschema>=4.23,<5" "PyYAML>=6.0.3,<7"     "typesafe-sdk==$EXPECTED_TYPESAFE_VERSION"
else
  "$PYTHON" -c 'import build, setuptools, wheel, jsonschema, yaml, typesafe_sdk'
fi

BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/agent-workflow-stack-build.XXXXXX")"
trap 'rm -rf "$BUILD_ROOT"' EXIT

build_wheel() {
  local key="$1" source="$2" expected_name="$3" expected_version="$4"
  local out="$BUILD_ROOT/$key"
  mkdir -p "$out"
  echo "building $expected_name $expected_version from $source" >&2
  "$PYTHON" -m build --wheel --no-isolation --outdir "$out" "$source" >&2
  set -- "$out"/*.whl
  [[ $# -eq 1 && -f "$1" ]] || {
    echo "expected exactly one wheel for $expected_name" >&2
    exit 1
  }
  "$PYTHON" - "$1" "$expected_name" "$expected_version" <<'PY'
from email.parser import Parser
from pathlib import Path
import sys, zipfile
wheel = Path(sys.argv[1])
expected_name = sys.argv[2].lower().replace("_", "-")
expected_version = sys.argv[3]
with zipfile.ZipFile(wheel) as archive:
    names = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
    if len(names) != 1:
        raise SystemExit(f"{wheel}: expected one METADATA")
    meta = Parser().parsestr(archive.read(names[0]).decode())
name = meta["Name"].lower().replace("_", "-")
version = meta["Version"]
if (name, version) != (expected_name, expected_version):
    raise SystemExit(f"{wheel}: {name} {version}; expected {expected_name} {expected_version}")
PY
  printf '%s\n' "$1"
}

CONTRACTS_WHEEL="$(build_wheel contracts "$CONTRACTS_SOURCE" "specgen-agent-workflow-contracts" "$EXPECTED_CONTRACTS_VERSION")"
AGENT_WORKFLOW_WHEEL="$(build_wheel core "$ROOT" "agent-workflow" "$EXPECTED_AGENT_WORKFLOW_VERSION")"
COMPARATIVE_EVAL_WHEEL="$(build_wheel comparative "$COMPARATIVE_EVAL_SOURCE" "agent-workflow-comparative-eval" "$EXPECTED_COMPARATIVE_EVAL_VERSION")"
SPECGEN_WHEEL="$(build_wheel specgen "$SPECGEN_SOURCE" "specgen" "$EXPECTED_SPECGEN_VERSION")"
BENCHMARK_WHEEL="$(build_wheel benchmark "$BENCHMARK_SOURCE" "agent-workflow-benchmark" "$EXPECTED_BENCHMARK_VERSION")"

install_wheel() {
  local name="$1" wheel="$2"
  echo "installing $name from $(basename "$wheel")"
  "$PYTHON" -m pip uninstall -y "$name" >/dev/null 2>&1 || true
  "$PYTHON" -m pip install --no-deps --force-reinstall "$wheel"
}

install_wheel "specgen-agent-workflow-contracts" "$CONTRACTS_WHEEL"
install_wheel "agent-workflow" "$AGENT_WORKFLOW_WHEEL"
install_wheel "agent-workflow-comparative-eval" "$COMPARATIVE_EVAL_WHEEL"
install_wheel "specgen" "$SPECGEN_WHEEL"
install_wheel "agent-workflow-benchmark" "$BENCHMARK_WHEEL"

write_stack_config
verify_stack

echo
echo "complete Agent-Workflow stack installed successfully"
echo "  venv:   $VENV"
echo "  config: $XDG_CONFIG_HOME/agent-workflow/config.toml"
echo "  state:  $XDG_STATE_HOME/agent-workflow"
echo "  data:   $XDG_DATA_HOME/agent-workflow"
echo
echo "Interactive isolated shell:"
echo "  source $ROOT/scripts/dev-env.sh on $VENV"
echo "Restore previous shell:"
echo "  source $ROOT/scripts/dev-env.sh off"
