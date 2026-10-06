#!/usr/bin/env bash
set -euo pipefail

ORIGINAL_ARGS=("$@")
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PARENT="$(dirname "$ROOT")"

# Third-party runtime dependencies remain intentionally frozen. Versions for
# locally developed stack components are resolved from their checked-out source.
EXPECTED_TYPESAFE_VERSION="0.6.0"
EXPECTED_INSPECT_AI_VERSION="0.3.268"
EXPECTED_INSPECT_SWE_VERSION="0.2.71"

VENV_ARG=""
CONTRACTS_SOURCE_ARG=""
COMPARATIVE_EVAL_SOURCE_ARG=""
SPECGEN_SOURCE_ARG=""
BENCHMARK_SOURCE_ARG=""
VERIFY_ONLY=0
BOOTSTRAP_BUILD=1
NO_PULL=0
PULL_ONLY=0
ALLOW_DIRTY_PULL=0

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
  --no-pull
  --pull-only
  --allow-dirty-pull
  --no-bootstrap-build
  -h, --help

Local stack versions are resolved dynamically from each source checkout after
pulling. VERSION is authoritative when present and must agree with pyproject.toml.
The installer reports repo/venv mismatches before installation, verifies wheel
metadata against source, and requires exact repo == wheel == installed versions
after installation. Third-party runtime versions remain explicit frozen pins.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --venv) shift; [[ $# -gt 0 ]] || { echo "--venv requires a value" >&2; exit 2; }; VENV_ARG="$1" ;;
    --contracts-source) shift; [[ $# -gt 0 ]] || { echo "--contracts-source requires a value" >&2; exit 2; }; CONTRACTS_SOURCE_ARG="$1" ;;
    --comparative-eval-source) shift; [[ $# -gt 0 ]] || { echo "--comparative-eval-source requires a value" >&2; exit 2; }; COMPARATIVE_EVAL_SOURCE_ARG="$1" ;;
    --specgen-source) shift; [[ $# -gt 0 ]] || { echo "--specgen-source requires a value" >&2; exit 2; }; SPECGEN_SOURCE_ARG="$1" ;;
    --benchmark-source) shift; [[ $# -gt 0 ]] || { echo "--benchmark-source requires a value" >&2; exit 2; }; BENCHMARK_SOURCE_ARG="$1" ;;
    --verify-only) VERIFY_ONLY=1; NO_PULL=1 ;;
    --no-pull) NO_PULL=1 ;;
    --pull-only) PULL_ONLY=1 ;;
    --allow-dirty-pull) ALLOW_DIRTY_PULL=1 ;;
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

CONTRACTS_SOURCE="$(resolve_path "${CONTRACTS_SOURCE_ARG:-$PARENT/agent-workflow-spec-contracts}")"
COMPARATIVE_EVAL_SOURCE="$(resolve_path "${COMPARATIVE_EVAL_SOURCE_ARG:-$PARENT/agent-workflow-comparative-eval}")"
SPECGEN_SOURCE="$(resolve_path "${SPECGEN_SOURCE_ARG:-$PARENT/specgen-aw}")"
BENCHMARK_SOURCE="$(resolve_path "${BENCHMARK_SOURCE_ARG:-$PARENT/agent-workflow-benchmark}")"

if [[ "$PULL_ONLY" -eq 1 || "$NO_PULL" -eq 0 ]]; then
  pull_args=(--contracts-source "$CONTRACTS_SOURCE" --comparative-eval-source "$COMPARATIVE_EVAL_SOURCE" --specgen-source "$SPECGEN_SOURCE" --benchmark-source "$BENCHMARK_SOURCE")
  [[ "$ALLOW_DIRTY_PULL" -eq 0 ]] || pull_args+=(--allow-dirty)
  bash "$ROOT/scripts/git-pull-all.sh" "${pull_args[@]}"
  [[ "$PULL_ONLY" -eq 0 ]] || exit 0
  exec bash "$ROOT/scripts/build-install-all.sh" --no-pull "${ORIGINAL_ARGS[@]}"
fi

resolve_source_version() {
  python3 - "$1" "$2" <<'PY'
from pathlib import Path
import sys, tomllib
source = Path(sys.argv[1])
expected_name = sys.argv[2]
path = source / "pyproject.toml"
if not path.is_file():
    raise SystemExit(f"missing required source pyproject.toml: {source}")
project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
if project.get("name") != expected_name:
    raise SystemExit(f"{source}: observed project {project.get('name')!r}; expected {expected_name!r}")
pyproject_version = str(project.get("version", "")).strip()
if not pyproject_version:
    raise SystemExit(f"{source}: pyproject.toml has no project.version")
version_file = source / "VERSION"
if version_file.is_file():
    canonical = version_file.read_text(encoding="utf-8").strip()
    if canonical != pyproject_version:
        raise SystemExit(f"{source}: VERSION={canonical}; pyproject.toml={pyproject_version}")
    print(canonical)
else:
    print(pyproject_version)
PY
}

EXPECTED_CONTRACTS_VERSION="$(resolve_source_version "$CONTRACTS_SOURCE" "specgen-agent-workflow-contracts")"
EXPECTED_AGENT_WORKFLOW_VERSION="$(resolve_source_version "$ROOT" "agent-workflow")"
EXPECTED_COMPARATIVE_EVAL_VERSION="$(resolve_source_version "$COMPARATIVE_EVAL_SOURCE" "agent-workflow-comparative-eval")"
EXPECTED_SPECGEN_VERSION="$(resolve_source_version "$SPECGEN_SOURCE" "specgen")"
EXPECTED_BENCHMARK_VERSION="$(resolve_source_version "$BENCHMARK_SOURCE" "agent-workflow-benchmark")"

if [[ -n "$VENV_ARG" ]]; then VENV="$(resolve_path "$VENV_ARG")"
elif [[ -n "${AGENT_WORKFLOW_VENV:-}" ]]; then VENV="$(resolve_path "$AGENT_WORKFLOW_VENV")"
elif [[ -n "${VIRTUAL_ENV:-}" ]]; then VENV="$(resolve_path "$VIRTUAL_ENV")"
elif [[ -x "$ROOT/.venv/bin/python" || -x "$ROOT/.venv/bin/python3" ]]; then VENV="$(resolve_path "$ROOT/.venv")"
else echo "could not resolve an existing shared virtualenv" >&2; exit 1
fi

if [[ -x "$VENV/bin/python" ]]; then PYTHON="$VENV/bin/python"
elif [[ -x "$VENV/bin/python3" ]]; then PYTHON="$VENV/bin/python3"
else echo "selected path is not a usable virtualenv: $VENV" >&2; exit 1
fi

"$PYTHON" - "$VENV" <<'PY'
from pathlib import Path
import sys
venv = Path(sys.argv[1]).resolve()
if sys.prefix == sys.base_prefix: raise SystemExit("selected interpreter is not running in a virtualenv")
if Path(sys.prefix).resolve() != venv: raise SystemExit(f"interpreter prefix {Path(sys.prefix).resolve()} != requested venv {venv}")
if sys.version_info < (3, 11): raise SystemExit("Agent-Workflow stack requires Python >= 3.11")
PY

[[ -n "${TYPESAFE_API_KEY:-}" ]] || { echo "comparative stack requires TYPESAFE_API_KEY in the environment" >&2; exit 1; }
export VIRTUAL_ENV="$VENV" AGENT_WORKFLOW_VENV="$VENV" AGENT_WORKFLOW_BIN="$VENV/bin/agent-workflow"
export PATH="$VENV/bin:$PATH" XDG_CONFIG_HOME="$VENV/.xdg/config" XDG_STATE_HOME="$VENV/.xdg/state" XDG_DATA_HOME="$VENV/.xdg/data"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_STATE_HOME" "$XDG_DATA_HOME"

LOCAL_COMPONENT_ARGS=(
  "specgen-agent-workflow-contracts" "$EXPECTED_CONTRACTS_VERSION" "$CONTRACTS_SOURCE"
  "agent-workflow" "$EXPECTED_AGENT_WORKFLOW_VERSION" "$ROOT"
  "agent-workflow-comparative-eval" "$EXPECTED_COMPARATIVE_EVAL_VERSION" "$COMPARATIVE_EVAL_SOURCE"
  "specgen" "$EXPECTED_SPECGEN_VERSION" "$SPECGEN_SOURCE"
  "agent-workflow-benchmark" "$EXPECTED_BENCHMARK_VERSION" "$BENCHMARK_SOURCE"
)

report_repo_venv_versions() {
  "$PYTHON" - "${LOCAL_COMPONENT_ARGS[@]}" <<'PY'
from importlib import metadata
import sys
raw=sys.argv[1:]
print("Repository / venv version alignment:")
for i in range(0,len(raw),3):
    name, repo_version, source=raw[i:i+3]
    try: installed=metadata.version(name)
    except metadata.PackageNotFoundError: installed="<not installed>"
    state="match" if installed==repo_version else "mismatch; will reinstall"
    print(f"  {name:<34} repo={repo_version:<12} venv={installed:<15} {state}")
PY
}
report_repo_venv_versions

write_source_provenance() {
  local target="$VENV/share/agent-workflow/source-provenance.json"; mkdir -p "$(dirname "$target")"
  "$PYTHON" - "$target" "${LOCAL_COMPONENT_ARGS[@]}" <<'PY'
from datetime import datetime, timezone
from pathlib import Path
import json, subprocess, sys, tempfile
target=Path(sys.argv[1]); raw=sys.argv[2:]; components={}
for i in range(0,len(raw),3):
    name, version, source_raw=raw[i:i+3]; source=Path(source_raw).resolve()
    revision=subprocess.run(["git","-C",str(source),"rev-parse","--verify","HEAD"],text=True,capture_output=True,check=True).stdout.strip()
    status=subprocess.run(["git","-C",str(source),"status","--porcelain=v1","--untracked-files=all"],text=True,capture_output=True,check=True).stdout.strip()
    components[name]={"version":version,"revision":revision,"dirty":bool(status)}
value={"schema":"agent-workflow/source-provenance/v1","recorded_at":datetime.now(timezone.utc).isoformat(),"components":components}
with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=target.parent,prefix=target.name+".",delete=False) as h:
    json.dump(value,h,indent=2,sort_keys=True); h.write("\n"); temp=Path(h.name)
temp.replace(target); print(f"source provenance: {target}")
PY
}

write_stack_config() {
  local target="$XDG_CONFIG_HOME/agent-workflow/config.toml"; mkdir -p "$(dirname "$target")"
  cat >"$target" <<EOF
schema_version = 1
[paths]
worktree_root = "$VENV/.xdg/data/agent-workflow/worktrees"
state_root = "$VENV/.xdg/state/agent-workflow"
[plugins]
enabled = ["agent-workflow-spec", "agent-workflow-benchmark"]
[semantic]
provider = "typesafe"
[semantic.typesafe]
api_call_log = "$VENV/.xdg/state/agent-workflow/typesafe-api-calls.jsonl"
[decision_policy]
mode = "comparative"
profile = "default"
EOF
  echo "stack config: $target"
}

verify_stack() {
  "$PYTHON" - "${LOCAL_COMPONENT_ARGS[@]}" "$EXPECTED_TYPESAFE_VERSION" "$EXPECTED_INSPECT_AI_VERSION" "$EXPECTED_INSPECT_SWE_VERSION" <<'PY'
from importlib import metadata
from pathlib import Path
import json, os, shutil, sys
raw=sys.argv[1:-3]; third={"typesafe-sdk":sys.argv[-3],"inspect-ai":sys.argv[-2],"inspect-swe":sys.argv[-1]}
expected={}
for i in range(0,len(raw),3): expected[raw[i]]=raw[i+1]
expected.update(third)
provenance_path=Path(sys.prefix)/"share"/"agent-workflow/source-provenance.json"
if not provenance_path.is_file(): raise SystemExit(f"missing source provenance manifest: {provenance_path}")
provenance=json.loads(provenance_path.read_text(encoding="utf-8"))
for name,version in expected.items():
    try: observed=metadata.version(name)
    except metadata.PackageNotFoundError as exc: raise SystemExit(f"missing distribution: {name}=={version}") from exc
    if observed != version: raise SystemExit(f"{name} installed {observed}; repo/runtime expects {version}")
for i in range(0,len(raw),3):
    name,version,_=raw[i:i+3]; item=provenance.get("components",{}).get(name)
    if not isinstance(item,dict) or item.get("version") != version: raise SystemExit(f"{name} provenance does not match repo version {version}")
    if item.get("dirty") is not False: raise SystemExit(f"source provenance reports dirty checkout for {name}")
from agent_workflow.config import load_settings
from agent_workflow.decisions import require_decision_runtime_ready
from agent_workflow.plugins import load_plugin_registry
from agent_workflow.comparative_eval import shared_library_status
from specgen.agent_workflow import AW_VERSION
from agent_workflow_benchmark.compat.inspect_swe_output_schema import assert_runtime_capability
structured_output=assert_runtime_capability(); settings=load_settings()
if settings.decision_mode != "comparative": raise SystemExit(f"decision mode {settings.decision_mode!r}; expected 'comparative'")
if settings.plugins_enabled != ("agent-workflow-spec","agent-workflow-benchmark"): raise SystemExit(f"unexpected plugins: {settings.plugins_enabled!r}")
if settings.executors.get("codex",[None])[0] != "codex": raise SystemExit(f"Codex executor is not direct: {settings.executors.get('codex')!r}")
semantic=require_decision_runtime_ready(settings)
if semantic.get("ready") is not True: raise SystemExit(f"semantic runtime not ready: {semantic}")
shared=shared_library_status()
if not shared.get("installed") or not shared.get("compatible"): raise SystemExit(f"comparative-eval incompatible: {shared}")
loaded=tuple(x.descriptor.name for x in load_plugin_registry(settings.plugins_enabled).loaded)
if AW_VERSION != expected["agent-workflow"]: raise SystemExit(f"SpecGen target {AW_VERSION}; expected {expected['agent-workflow']}")
if not shutil.which("codex"): raise SystemExit("direct Codex executable is not available")
if not os.environ.get("TYPESAFE_API_KEY"): raise SystemExit("TYPESAFE_API_KEY is not configured")
print("\nAgent-Workflow stack verification:")
for name,version in expected.items(): print(f"  {name:<34} {version}")
print(f"  {'structured-output':<34} {structured_output['capability']}")
PY
  "$PYTHON" -m pip check
  "$VENV/bin/agent-workflow" --version >/dev/null
  "$VENV/bin/agent-workflow" --no-plugins --help >/dev/null
  "$VENV/bin/specgen" --help >/dev/null
  "$VENV/bin/contract-bundle" --help >/dev/null
  codex --version >/dev/null
}

if [[ "$VERIFY_ONLY" -eq 1 ]]; then
  # verify-only is deliberately strict: repo/venv mismatch is a hard failure.
  verify_stack
  exit 0
fi

if [[ "$BOOTSTRAP_BUILD" -eq 1 ]]; then
  "$PYTHON" -m pip install --upgrade pip build wheel "setuptools>=77" "jsonschema>=4.23,<5" "PyYAML>=6.0.3,<7" "typesafe-sdk==$EXPECTED_TYPESAFE_VERSION"
else
  "$PYTHON" -c 'import build, setuptools, wheel, jsonschema, yaml, typesafe_sdk'
fi

BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/agent-workflow-stack-build.XXXXXX")"; trap 'rm -rf "$BUILD_ROOT"' EXIT
build_wheel() {
  local key="$1"
  local source="$2"
  local expected_name="$3"
  local expected_version="$4"
  local out="$BUILD_ROOT/$key"
  mkdir -p "$out"
  echo "building $expected_name $expected_version from $source" >&2
  "$PYTHON" -m build --wheel --no-isolation --outdir "$out" "$source" >&2
  set -- "$out"/*.whl; [[ $# -eq 1 && -f "$1" ]] || { echo "expected exactly one wheel for $expected_name" >&2; exit 1; }
  "$PYTHON" - "$1" "$expected_name" "$expected_version" <<'PY'
from email.parser import Parser
import sys, zipfile
wheel,name,version=sys.argv[1:]
with zipfile.ZipFile(wheel) as z:
    paths=[p for p in z.namelist() if p.endswith(".dist-info/METADATA")]
    if len(paths)!=1: raise SystemExit(f"{wheel}: expected one METADATA")
    meta=Parser().parsestr(z.read(paths[0]).decode())
observed=(meta["Name"].lower().replace("_","-"),meta["Version"]); expected=(name.lower().replace("_","-"),version)
if observed != expected: raise SystemExit(f"{wheel}: {observed}; expected {expected}")
PY
  printf '%s\n' "$1"
}
CONTRACTS_WHEEL="$(build_wheel contracts "$CONTRACTS_SOURCE" specgen-agent-workflow-contracts "$EXPECTED_CONTRACTS_VERSION")"
AGENT_WORKFLOW_WHEEL="$(build_wheel core "$ROOT" agent-workflow "$EXPECTED_AGENT_WORKFLOW_VERSION")"
COMPARATIVE_EVAL_WHEEL="$(build_wheel comparative "$COMPARATIVE_EVAL_SOURCE" agent-workflow-comparative-eval "$EXPECTED_COMPARATIVE_EVAL_VERSION")"
SPECGEN_WHEEL="$(build_wheel specgen "$SPECGEN_SOURCE" specgen "$EXPECTED_SPECGEN_VERSION")"
BENCHMARK_WHEEL="$(build_wheel benchmark "$BENCHMARK_SOURCE" agent-workflow-benchmark "$EXPECTED_BENCHMARK_VERSION")"
install_wheel() { local name="$1" wheel="$2"; echo "installing $name from $(basename "$wheel")"; "$PYTHON" -m pip uninstall -y "$name" >/dev/null 2>&1 || true; "$PYTHON" -m pip install --no-deps --force-reinstall "$wheel"; }
install_wheel specgen-agent-workflow-contracts "$CONTRACTS_WHEEL"
install_wheel agent-workflow "$AGENT_WORKFLOW_WHEEL"
install_wheel agent-workflow-comparative-eval "$COMPARATIVE_EVAL_WHEEL"
install_wheel specgen "$SPECGEN_WHEEL"
install_wheel agent-workflow-benchmark "$BENCHMARK_WHEEL"

echo "installing frozen Inspect adjudication runtime"
"$PYTHON" -m pip install --upgrade "inspect-ai==$EXPECTED_INSPECT_AI_VERSION" "inspect-swe==$EXPECTED_INSPECT_SWE_VERSION" "openai>=1.0"
"$PYTHON" "$BENCHMARK_SOURCE/scripts/compat/apply-inspect-swe-output-schema-patch.py"
write_source_provenance
write_stack_config
verify_stack

echo
echo "complete Agent-Workflow stack installed successfully"
echo "  venv:   $VENV"
echo "  config: $XDG_CONFIG_HOME/agent-workflow/config.toml"
echo "  state:  $XDG_STATE_HOME/agent-workflow"
echo "  data:   $XDG_DATA_HOME/agent-workflow"
