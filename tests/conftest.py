from __future__ import annotations

import json
import importlib.metadata
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import jsonschema
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TERMINAL_STATES = {"completed", "failed", "interrupted", "terminated", "retired"}


@dataclass(frozen=True)
class InstalledProduct:
    root: Path
    python: Path
    cli: Path
    mcp: Path
    wheel: Path
    mcp_sdk_available: bool

    def run(
        self,
        *args: str | os.PathLike[str],
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        check: bool = False,
        timeout: float = 30,
    ) -> subprocess.CompletedProcess[str]:
        command = [str(self.cli), *(str(value) for value in args)]
        # Regular files, unlike capture_output pipes, are safe when an installed
        # command launches descendants that briefly outlive the parent process.
        # This keeps assertion-dense multi-command journeys deterministic.
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=env,
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=timeout,
                check=False,
            )
            stdout_file.seek(0)
            stderr_file.seek(0)
            result = subprocess.CompletedProcess(
                command,
                completed.returncode,
                stdout_file.read().decode("utf-8", errors="replace"),
                stderr_file.read().decode("utf-8", errors="replace"),
            )
        if check and result.returncode:
            raise AssertionError(
                f"command failed ({result.returncode}): {' '.join(command)}\n"
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
            )
        return result

    def json(
        self,
        *args: str | os.PathLike[str],
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        timeout: float = 30,
    ) -> Any:
        result = self.run("--json", *args, env=env, cwd=cwd, check=True, timeout=timeout)
        return json.loads(result.stdout)


@pytest.fixture(scope="session")
def installed_product(tmp_path_factory: pytest.TempPathFactory) -> InstalledProduct:
    root = tmp_path_factory.mktemp("installed-product")
    source = root / "source"
    shutil.copytree(
        REPO_ROOT,
        source,
        ignore=shutil.ignore_patterns(
            ".git", ".pytest_cache", "__pycache__", "*.pyc", "build", "dist", "*.egg-info"
        ),
    )
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheelhouse),
            str(source),
        ],
        text=True,
        capture_output=True,
        check=True,
        timeout=120,
    )
    wheel = next(wheelhouse.glob("agent_workflow-*.whl"))
    environment = root / "venv"
    venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
    python = environment / "bin" / "python"
    venv_site = environment / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"
    runtime_paths = {
        str(Path(jsonschema.__file__).resolve().parents[1]),
        str(Path(yaml.__file__).resolve().parents[1]),
    }
    mcp_sdk_available = False
    try:
        mcp_distribution = importlib.metadata.distribution("mcp")
    except importlib.metadata.PackageNotFoundError:
        mcp_distribution = None
    if mcp_distribution is not None and mcp_distribution.version == "1.28.1":
        runtime_paths.add(str(mcp_distribution.locate_file("")))
        mcp_sdk_available = True
    (venv_site / "agent_workflow_configured_dependencies.pth").write_text(
        "\n".join(sorted(runtime_paths)) + "\n", encoding="utf-8"
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", "--ignore-installed", "--no-deps", str(wheel)],
        text=True,
        capture_output=True,
        check=True,
        timeout=120,
    )
    dependency = subprocess.run(
        [
            str(python),
            "-c",
            (
                "import importlib.metadata as metadata; import jsonschema, yaml; "
                "print(metadata.version('jsonschema')); print(metadata.version('PyYAML'))"
            ),
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if dependency.returncode:
        detail = (dependency.stderr or dependency.stdout).strip()
        pytest.fail(f"installed-product fixture could not import core dependencies: {detail}")
    return InstalledProduct(
        root=root,
        python=python,
        cli=environment / "bin" / "agent-workflow",
        mcp=environment / "bin" / "agent-workflow-mcp",
        wheel=wheel,
        mcp_sdk_available=mcp_sdk_available,
    )


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def product_env(tmp_path: Path, installed_product: InstalledProduct) -> dict[str, str]:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    for path in (home, fake_bin):
        path.mkdir(parents=True)

    _write_executable(
        fake_bin / "fake-agent",
        r'''#!/usr/bin/env python3
import json
import hashlib
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

mode = os.environ.get("FAKE_AGENT_MODE", "success")
prompt = sys.stdin.read()
handoff = Path(os.environ["AGENT_WORKFLOW_HANDOFF_DIR"])
handoff.mkdir(parents=True, exist_ok=True)
(handoff / "prompt-seen.txt").write_text(prompt, encoding="utf-8")
(handoff / "command-contract-env.json").write_text(
    json.dumps(
        {
            "catalog": os.environ.get("AGENT_WORKFLOW_COMMAND_CATALOG"),
            "card": os.environ.get("AGENT_WORKFLOW_COMMAND_CARD"),
            "cli": os.environ.get("AGENT_WORKFLOW_CLI"),
        },
        sort_keys=True,
    ),
    encoding="utf-8",
)
if os.environ.get("FAKE_AGENT_EMIT_PROGRESS") == "1":
    subprocess.run(
        [
            os.environ["AGENT_WORKFLOW_CLI"], "agent-run", "progress",
            os.environ["AGENT_WORKFLOW_AGENT_RUN_ID"],
            "fixture durable progress", "--actor", "fixture-child",
        ],
        check=True,
    )
if mode == "slow":
    deadline = time.monotonic() + float(os.environ.get("FAKE_AGENT_DELAY", "1.0"))
    steering_inbox = Path(os.environ["AGENT_WORKFLOW_STEERING_INBOX"])
    processed = set()
    while time.monotonic() < deadline:
        request_paths = (
            steering_inbox.glob("steer-*.json")
            if os.environ.get("FAKE_AGENT_AUTO_STEER") == "1"
            else ()
        )
        for request_path in request_paths:
            if request_path.name in processed:
                continue
            request = json.loads(request_path.read_text(encoding="utf-8"))
            outcome = os.environ.get("FAKE_AGENT_STEER_OUTCOME", "applied")
            subprocess.run(
                [
                    os.environ["AGENT_WORKFLOW_CLI"], "agent-run", "ack",
                    os.environ["AGENT_WORKFLOW_AGENT_RUN_ID"],
                    request["message_id"],
                    f"Fixture executor {outcome} steering",
                    "--actor", "fixture-child", "--outcome", outcome,
                ],
                check=True,
            )
            processed.add(request_path.name)
        time.sleep(0.05)
if mode == "hang":
    time.sleep(float(os.environ.get("FAKE_AGENT_DELAY", "30.0")))
try:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=True
    ).stdout.strip()
except subprocess.CalledProcessError:
    head = None
result = "failed" if mode == "fail" else "completed"
result_json = os.environ.get("FAKE_AGENT_RESULT_JSON")
ticket_override = None
if result_json:
    try:
        ticket_override = json.loads(result_json).get("ticket_id")
    except (TypeError, json.JSONDecodeError):
        ticket_override = None
completion = {
    "schema": "agent-workflow/completion/v1",
    "agent_run_id": os.environ["AGENT_WORKFLOW_AGENT_RUN_ID"],
    "ticket_id": ticket_override or os.environ.get("FAKE_AGENT_TICKET_ID", os.environ.get("AGENT_WORKFLOW_TICKET_ID")),
    "pack_id": os.environ.get("AGENT_WORKFLOW_PACK_ID"),
    "result": result,
    "base_revision": head,
    "head_revision": head,
    "changed_files": [],
    "criteria": [
        {
            "id": "fixture-executor-finished",
            "result": "fail" if mode == "fail" else "pass",
            "evidence": [
                "fake-agent reached its terminal completion handoff"
            ],
        }
    ],
    "commands": [
        {
            "argv": ["fake-agent", mode],
            "cwd": str(Path.cwd()),
            "exit_code": 7 if mode == "fail" else 0,
            "receipt": "intentional fixture execution evidence",
        }
    ],
    "unresolved": ["intentional failure"] if mode == "fail" else [],
    "usage": None,
}
if os.environ.get("FAKE_AGENT_EMPTY_COMPLETION") == "1":
    completion.update(
        {
            "base_revision": None,
            "head_revision": None,
            "criteria": [],
            "commands": [],
        }
    )
(handoff / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
if result_json:
    (handoff / "result.json").write_text(result_json, encoding="utf-8")
if mode in {"task-complete", "task-complete-terminate"}:
    subprocess.run(
        [
            os.environ["AGENT_WORKFLOW_CLI"], "agent", "task-complete",
            os.environ["AGENT_WORKFLOW_AGENT_RUN_ID"],
            "--actor", "fixture-child", "--summary", "fixture assignment complete",
        ],
        check=True,
    )
if mode == "task-complete-mutate":
    subprocess.run(
        [
            os.environ["AGENT_WORKFLOW_CLI"], "agent", "task-complete",
            os.environ["AGENT_WORKFLOW_AGENT_RUN_ID"],
            "--actor", "fixture-child", "--summary", "fixture assignment complete",
        ],
        check=True,
    )
    completion["result"] = "blocked"
    completion["unresolved"] = ["fixture replaced completion after task-complete"]
    (handoff / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
if mode == "task-complete-terminate":
    subprocess.run(
        [
            os.environ["AGENT_WORKFLOW_CLI"], "agent-run", "terminate",
            os.environ["AGENT_WORKFLOW_AGENT_RUN_ID"], "--grace-seconds", "0",
        ],
        check=True,
    )
if mode == "post-exit-intent":
    request_id = str(uuid.uuid4())
    intent = {
        "schema": "agent-workflow/control-intent/v1",
        "request_id": request_id,
        "agent_run_id": os.environ["AGENT_WORKFLOW_AGENT_RUN_ID"],
        "sequence": 1,
        "kind": "progress",
        "actor": "fixture-child",
        "content": "arrived after executor exit",
        "correlation_id": None,
        "outcome": None,
        "completion_sha256": None,
        "terminal": None,
    }
    intent["digest"] = "sha256:" + hashlib.sha256(
        json.dumps(intent, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    bridge = Path(os.environ["AGENT_WORKFLOW_CONTROL_BRIDGE"])
    (bridge / f"intent-{request_id}-1.json").write_text(
        json.dumps(intent, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    # Leave no user-space work after the intent. The runner must observe the
    # executor exit before its terminal bridge drain handles this request.
    os._exit(0)
if mode == "structured":
    print(json.dumps({"event_id": "message-1", "type": "item.completed", "item": {"type": "agent_message", "text": "fake agent completed"}}))
    print(json.dumps({"event_id": "usage-1", "type": "turn.completed", "usage": {"input_tokens": 5, "cached_input_tokens": 1, "output_tokens": 3}}))
else:
    print("fake agent completed")
if "--secret" in sys.argv:
    print("argv=" + repr(sys.argv))
if mode == "noisy":
    sys.stdout.write("O" * (17 * 1024 * 1024))
    sys.stderr.write("E" * (17 * 1024 * 1024))
if mode == "fail":
    print("intentional executor failure", file=sys.stderr)
    raise SystemExit(7)
''',
    )

    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "PATH": os.pathsep.join(
                [str(fake_bin), str(installed_product.cli.parent), environment.get("PATH", "")]
            ),
            "PYTHONUNBUFFERED": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": "",
        }
    )
    try:
        yield environment
    finally:
        # Acceptance commands intentionally create detached process groups.
        # Reap every fixture-owned group so one assertion-dense journey cannot
        # leak lifecycle state into the next journey.
        pids: set[int] = set()
        runs_root = Path(environment["XDG_STATE_HOME"]) / "agent-workflow" / "runs"
        for status_path in runs_root.glob("*/status.json"):
            try:
                status = json.loads(status_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for key in ("worker_pid", "worker_process_group_id"):
                candidate = status.get(key)
                if isinstance(candidate, int) and candidate > 1:
                    pids.add(candidate)
        for heartbeat_path in runs_root.glob("*/heartbeat.json"):
            try:
                heartbeat = json.loads(heartbeat_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for key in ("runner_pid", "executor_pid", "pid"):
                candidate = heartbeat.get(key)
                if isinstance(candidate, int) and candidate > 1:
                    pids.add(candidate)
        own_group = os.getpgrp()
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for pid in sorted(pids):
                try:
                    group = os.getpgid(pid)
                    if group != own_group:
                        os.killpg(group, sig)
                except (ProcessLookupError, PermissionError):
                    pass
            if sig == signal.SIGTERM:
                time.sleep(0.05)



def prepare_and_start_agent_run(
    installed_product: InstalledProduct,
    *prepare_args: str | os.PathLike[str],
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    timeout: float = 30,
) -> dict[str, Any]:
    """Exercise the public two-step headless Agent Run API in one test helper."""
    prepared = installed_product.json(
        "agent-run", "prepare", *prepare_args, env=env, cwd=cwd, timeout=timeout
    )
    agent_run_id = str(prepare_args[0])
    started = installed_product.json(
        "agent-run", "start", agent_run_id, env=env, cwd=cwd, timeout=timeout
    )
    return {"prepared": prepared, "started": started}

def git_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "tests@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Acceptance Tests"], check=True)
    (path / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True)
    return subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def wait_for_status(env: dict[str, str], agent_run_id: str, *, timeout: float = 20) -> dict[str, Any]:
    status_path = Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / agent_run_id / "status.json"
    deadline = time.monotonic() + timeout
    last: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        if status_path.is_file():
            try:
                last = json.loads(status_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                last = None
            if last and last.get("status") in TERMINAL_STATES:
                return last
        time.sleep(0.05)
    raise AssertionError(f"Agent Run did not reach a terminal state: {agent_run_id}; last={last}")


def write_config(env: dict[str, str], *, fake_agent: Path, structured_executor: bool = False) -> Path:
    path = Path(env["XDG_CONFIG_HOME"]) / "agent-workflow" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "[executors.codex]",
                f'command = ["{fake_agent}"]',
                'models = ["gpt-5.6-luna"]',
                'default_model = "gpt-5.6-luna"',
                'model_arg = ["--model"]',
                'interactive_permission_args = []',
                'non_interactive_permission_args = []',
                'environment_allowlist = ["FAKE_AGENT_MODE", "FAKE_AGENT_DELAY", "FAKE_AGENT_RESULT_JSON", "FAKE_AGENT_AUTO_STEER", "FAKE_AGENT_EMPTY_COMPLETION", "FAKE_AGENT_STEER_OUTCOME", "FAKE_AGENT_TICKET_ID", "FAKE_AGENT_EMIT_PROGRESS"]',
                'steering_adapter = "control-file-v1"',
                "",
                "[git]",
                "require_clean_source = false",
                "",
                "[agents]",
                'default_executor = "codex"',
                'default_class = "review"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def fake_agent_path(product_env: dict[str, str]) -> Path:
    return Path(product_env["PATH"].split(os.pathsep)[0]) / "fake-agent"
