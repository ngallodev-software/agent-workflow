#!/usr/bin/env python3
"""Build and install the complete Agent-Workflow development stack into one venv."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
from importlib import metadata


ROOT = Path(__file__).resolve().parents[1]
STACK_ROOT = ROOT.parent

DISTRIBUTIONS = {
    "contracts": "specgen-agent-workflow-contracts",
    "agent_workflow": "agent-workflow",
    "comparative_eval": "agent-workflow-comparative-eval",
    "specgen": "specgen",
    "benchmark": "agent-workflow-benchmark",
}


class InstallError(RuntimeError):
    pass


def run(
    argv: list[str | Path],
    *,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    rendered = [str(item) for item in argv]
    print("+", " ".join(rendered), flush=True)
    result = subprocess.run(
        rendered,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
        text=True,
        capture_output=capture,
        check=False,
    )
    if result.returncode:
        if capture:
            if result.stdout:
                print(result.stdout, file=sys.stderr, end="")
            if result.stderr:
                print(result.stderr, file=sys.stderr, end="")
        raise InstallError(
            f"command failed with exit {result.returncode}: {' '.join(rendered)}"
        )
    return result


def resolve(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def require_source(path: Path, name: str) -> Path:
    if not (path / "pyproject.toml").is_file():
        raise InstallError(f"{name} source checkout is missing pyproject.toml: {path}")
    return path


def project(source: Path) -> dict:
    return tomllib.loads((source / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]


def source_version(source: Path) -> str:
    return str(project(source)["version"])


def source_name(source: Path) -> str:
    return str(project(source)["name"])


def select_venv(value: str | None) -> Path:
    candidates: list[Path] = []
    if value:
        candidates.append(resolve(value))
    if os.environ.get("AGENT_WORKFLOW_VENV"):
        candidates.append(resolve(os.environ["AGENT_WORKFLOW_VENV"]))
    if os.environ.get("VIRTUAL_ENV"):
        candidates.append(resolve(os.environ["VIRTUAL_ENV"]))
    candidates.append(ROOT / ".venv")

    for candidate in candidates:
        if (candidate / "bin" / "python").is_file() or (
            candidate / "bin" / "python3"
        ).is_file():
            return candidate.resolve()
    raise InstallError(
        "no existing shared virtualenv found; pass --venv PATH or create "
        f"{ROOT / '.venv'} before running this script"
    )


def venv_python(venv: Path) -> Path:
    for name in ("python", "python3"):
        candidate = venv / "bin" / name
        if candidate.is_file():
            return candidate
    raise InstallError(f"selected virtualenv has no Python interpreter: {venv}")


def runtime_env(venv: Path) -> dict[str, str]:
    env = dict(os.environ)
    bin_dir = venv / "bin"
    env.update(
        {
            "VIRTUAL_ENV": str(venv),
            "AGENT_WORKFLOW_VENV": str(venv),
            "AGENT_WORKFLOW_BIN": str(bin_dir / "agent-workflow"),
            "XDG_CONFIG_HOME": str(venv / ".xdg" / "config"),
            "XDG_STATE_HOME": str(venv / ".xdg" / "state"),
            "XDG_DATA_HOME": str(venv / ".xdg" / "data"),
            "PATH": str(bin_dir) + os.pathsep + env.get("PATH", ""),
        }
    )
    for key in ("XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME"):
        Path(env[key]).mkdir(parents=True, exist_ok=True)
    return env


def assert_interpreter(py: Path, venv: Path, env: dict[str, str]) -> None:
    code = """
from pathlib import Path
import sys
expected = Path(sys.argv[1]).resolve()
if sys.prefix == sys.base_prefix:
    raise SystemExit(f"interpreter is not a virtualenv: {sys.executable}")
if Path(sys.prefix).resolve() != expected:
    raise SystemExit(f"virtualenv prefix mismatch: {sys.prefix} != {expected}")
if sys.version_info < (3, 11):
    raise SystemExit("Agent-Workflow stack requires Python 3.11+")
"""
    run([py, "-c", code, str(venv)], env=env)


def bootstrap(py: Path, env: dict[str, str]) -> None:
    run(
        [
            py,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "build>=1.2,<2",
            "setuptools>=77",
            "jsonschema>=4.23,<5",
            "PyYAML>=6.0.3,<7",
            "typesafe-sdk==0.6.0",
        ],
        env=env,
    )


def build_and_install_local(
    *,
    py: Path,
    env: dict[str, str],
    source: Path,
    expected_distribution: str,
    stage: Path,
) -> Path:
    actual_name = source_name(source).lower().replace("_", "-")
    expected_name = expected_distribution.lower().replace("_", "-")
    if actual_name != expected_name:
        raise InstallError(
            f"source distribution mismatch at {source}: "
            f"expected {expected_distribution}, observed {source_name(source)}"
        )
    out = stage / expected_name
    out.mkdir(parents=True, exist_ok=True)
    run(
        [
            py,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            out,
            source,
        ],
        env=env,
    )
    wheels = sorted(out.glob("*.whl"))
    if len(wheels) != 1:
        raise InstallError(
            f"expected exactly one wheel for {expected_distribution}, found {len(wheels)}"
        )
    run(
        [py, "-m", "pip", "install", "--no-deps", "--force-reinstall", wheels[0]],
        env=env,
    )
    observed = metadata_version(py, env, expected_distribution)
    expected = source_version(source)
    if observed != expected:
        raise InstallError(
            f"{expected_distribution} install mismatch: source={expected}, installed={observed}"
        )
    print(f"installed {expected_distribution} {observed} from {source}")
    return wheels[0]


def metadata_version(py: Path, env: dict[str, str], distribution: str) -> str:
    code = (
        "from importlib.metadata import version; "
        "import sys; print(version(sys.argv[1]))"
    )
    return run([py, "-c", code, distribution], env=env, capture=True).stdout.strip()


def write_stack_config(venv: Path, py: Path, env: dict[str, str]) -> Path:
    config = Path(env["XDG_CONFIG_HOME"]) / "agent-workflow" / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    worktree = venv / ".xdg" / "data" / "agent-workflow" / "worktrees"
    state = venv / ".xdg" / "state" / "agent-workflow"
    rendered = "\n".join(
        [
            "schema_version = 1",
            "",
            "[paths]",
            f"worktree_root = {json.dumps(str(worktree))}",
            f"state_root = {json.dumps(str(state))}",
            "",
            "[plugins]",
            'enabled = ["agent-workflow-benchmark", "agent-workflow-spec"]',
            "",
            "[semantic]",
            'provider = "typesafe"',
            "",
            "[decision_policy]",
            'mode = "comparative"',
            'profile = "default"',
            "",
        ]
    )
    tomllib.loads(rendered)
    temp = config.with_name(config.name + ".stack.tmp")
    temp.write_text(rendered, encoding="utf-8")
    os.replace(temp, config)
    print(f"wrote authoritative stack config: {config}")
    return config


def verify_stack(
    *,
    py: Path,
    venv: Path,
    env: dict[str, str],
    sources: dict[str, Path],
) -> None:
    if not env.get("TYPESAFE_API_KEY"):
        raise InstallError(
            "TYPESAFE_API_KEY must be loaded for the comparative Agent-Workflow stack"
        )

    expected = {
        DISTRIBUTIONS[key]: source_version(source)
        for key, source in sources.items()
    }
    for distribution, version in expected.items():
        observed = metadata_version(py, env, distribution)
        if observed != version:
            raise InstallError(
                f"installed {distribution}={observed}, expected source version {version}"
            )

    code = r"""
from importlib import metadata
from pathlib import Path
import os
import shutil
import tomllib

from agent_workflow.config import load_settings
from agent_workflow.decisions import require_decision_runtime_ready
from specgen.agent_workflow import AW_VERSION

config_path = Path(os.environ["XDG_CONFIG_HOME"]) / "agent-workflow" / "config.toml"
config = tomllib.loads(config_path.read_text(encoding="utf-8"))
provider = config.get("semantic", {}).get("provider")
if provider != "typesafe":
    raise SystemExit(f"expected TypeSafe provider in config, observed {provider!r}")

settings = load_settings()
if settings.decision_mode != "comparative":
    raise SystemExit(f"expected comparative mode, observed {settings.decision_mode!r}")
status = require_decision_runtime_ready(settings)
if status.get("ready") is not True:
    raise SystemExit(f"semantic runtime is not ready: {status}")

core_version = metadata.version("agent-workflow")
if AW_VERSION != core_version:
    raise SystemExit(
        f"SpecGen target mismatch: AW_VERSION={AW_VERSION}, installed Agent-Workflow={core_version}"
    )
if metadata.version("typesafe-sdk") != "0.6.0":
    raise SystemExit("typesafe-sdk must be exactly 0.6.0")
if metadata.version("agent-workflow-comparative-eval") != "0.1.0":
    raise SystemExit("agent-workflow-comparative-eval must be exactly 0.1.0")

codex_argv = settings.executors.get("codex")
if not codex_argv or Path(str(codex_argv[0])).name != "codex":
    raise SystemExit(f"Agent-Workflow Codex executor is not direct: {codex_argv!r}")
if shutil.which("codex") is None:
    raise SystemExit("direct codex executable is not available on PATH")

print(
    "runtime verified: comparative + TypeSafe + comparative-eval; "
    f"Agent-Workflow={core_version}; SpecGen target={AW_VERSION}; codex=direct"
)
"""
    run([py, "-c", code], env=env)

    aw = venv / "bin" / "agent-workflow"
    run([aw, "--version"], env=env)
    plugin_result = run(
        [aw, "--json", "plugins", "list"], env=env, capture=True
    )
    payload = json.loads(plugin_result.stdout)
    rows = {item.get("name"): item for item in payload.get("plugins", [])}
    for name in ("agent-workflow-benchmark", "agent-workflow-spec"):
        row = rows.get(name)
        if not row:
            raise InstallError(f"enabled plugin is missing from inventory: {name}")
        if row.get("enabled") is not True or row.get("loaded") is not True:
            raise InstallError(
                f"plugin did not load: {name}; "
                f"enabled={row.get('enabled')} loaded={row.get('loaded')}"
            )

    run([aw, "benchmark", "--help"], env=env)
    run([aw, "spec", "--help"], env=env)
    run([aw, "--json", "spec", "compatibility"], env=env)
    run([py, "-m", "pip", "check"], env=env)
    print("complete Agent-Workflow stack verification passed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build and install contracts, comparative-eval, Agent-Workflow, "
            "SpecGen-AW, and benchmark plugin into one existing virtualenv."
        )
    )
    parser.add_argument("--venv", help="existing shared virtualenv")
    parser.add_argument(
        "--contracts-source",
        default=os.environ.get(
            "AGENT_WORKFLOW_CONTRACTS_SOURCE",
            str(STACK_ROOT / "agent-workflow-spec-contracts"),
        ),
    )
    parser.add_argument(
        "--comparative-eval-source",
        default=os.environ.get(
            "AGENT_WORKFLOW_COMPARATIVE_EVAL_SOURCE",
            str(STACK_ROOT / "agent-workflow-comparative-eval"),
        ),
    )
    parser.add_argument(
        "--specgen-source",
        default=os.environ.get("SPECGEN_SOURCE_ROOT", str(STACK_ROOT / "specgen-aw")),
    )
    parser.add_argument(
        "--benchmark-source",
        default=os.environ.get(
            "AGENT_WORKFLOW_BENCHMARK_SOURCE",
            str(STACK_ROOT / "agent-workflow-benchmark"),
        ),
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify the existing shared install without rebuilding or mutating config",
    )
    parser.add_argument(
        "--no-bootstrap-deps",
        action="store_true",
        help="do not install/upgrade shared third-party build/runtime dependencies",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    venv = select_venv(args.venv)
    py = venv_python(venv)
    env = runtime_env(venv)

    if not env.get("TYPESAFE_API_KEY"):
        raise InstallError(
            "TYPESAFE_API_KEY is required before build/install because the "
            "shared stack is configured for comparative decision mode"
        )

    sources = {
        "contracts": require_source(resolve(args.contracts_source), "contracts"),
        "agent_workflow": ROOT,
        "comparative_eval": require_source(
            resolve(args.comparative_eval_source), "comparative-eval"
        ),
        "specgen": require_source(resolve(args.specgen_source), "SpecGen-AW"),
        "benchmark": require_source(resolve(args.benchmark_source), "benchmark"),
    }

    assert_interpreter(py, venv, env)
    print(f"shared virtualenv: {venv}")
    for key, source in sources.items():
        print(f"{key:16}: {source} ({source_name(source)} {source_version(source)})")

    if args.verify_only:
        verify_stack(py=py, venv=venv, env=env, sources=sources)
        return 0

    if not args.no_bootstrap_deps:
        bootstrap(py, env)

    with tempfile.TemporaryDirectory(prefix="agent-workflow-stack-build-") as raw:
        stage = Path(raw)
        build_and_install_local(
            py=py,
            env=env,
            source=sources["contracts"],
            expected_distribution=DISTRIBUTIONS["contracts"],
            stage=stage,
        )
        build_and_install_local(
            py=py,
            env=env,
            source=sources["comparative_eval"],
            expected_distribution=DISTRIBUTIONS["comparative_eval"],
            stage=stage,
        )

        run(
            [
                "bash",
                ROOT / "scripts" / "build-install.sh",
                "--venv",
                venv,
            ],
            env=env,
            cwd=ROOT,
        )

        release_env = dict(env)
        release_env["SPECGEN_AGENT_WORKFLOW_ROOT"] = str(ROOT)
        run(
            [py, sources["specgen"] / "tests" / "release" / "verify_versions.py"],
            env=release_env,
            cwd=sources["specgen"],
        )
        build_and_install_local(
            py=py,
            env=env,
            source=sources["specgen"],
            expected_distribution=DISTRIBUTIONS["specgen"],
            stage=stage,
        )

        run(
            [
                "bash",
                sources["benchmark"] / "scripts" / "build-install.sh",
                "--venv",
                venv,
                "--comparative-eval-source",
                sources["comparative_eval"],
            ],
            env=env,
            cwd=sources["benchmark"],
        )

    write_stack_config(venv, py, env)
    verify_stack(py=py, venv=venv, env=env, sources=sources)

    print("")
    print("Agent-Workflow stack installed successfully")
    print(f"  virtualenv: {venv}")
    print(f"  config:     {env['XDG_CONFIG_HOME']}/agent-workflow/config.toml")
    print("  decision:   comparative")
    print("  semantic:   typesafe")
    print("  plugins:    agent-workflow-benchmark, agent-workflow-spec")
    print("  executor:   codex (direct)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InstallError as exc:
        print(f"build-install-all: {exc}", file=sys.stderr)
        raise SystemExit(1)
