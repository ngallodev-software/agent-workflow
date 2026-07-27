from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import venv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import jsonschema

REPO_ROOT = Path(__file__).resolve().parents[1]
TERMINAL_STATES = {"completed", "failed", "interrupted", "killed"}


@dataclass(frozen=True)
class InstalledProduct:
    root: Path
    python: Path
    cli: Path
    mcp: Path

    def run(
        self,
        *args: str | os.PathLike[str],
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        check: bool = False,
        timeout: float = 30,
    ) -> subprocess.CompletedProcess[str]:
        command = [str(self.cli), *(str(value) for value in args)]
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
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
    subprocess.run(
        [str(python), "-m", "pip", "install", "--ignore-installed", "--no-deps", str(wheel)],
        text=True,
        capture_output=True,
        check=True,
        timeout=120,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", "--ignore-installed", "mcp==1.28.1"],
        text=True,
        capture_output=True,
        check=True,
        timeout=120,
    )
    return InstalledProduct(
        root=root,
        python=python,
        cli=environment / "bin" / "agent-workflow",
        mcp=environment / "bin" / "agent-workflow-mcp",
    )


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def product_env(tmp_path: Path, installed_product: InstalledProduct) -> dict[str, str]:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    tmux_state = tmp_path / "fake-tmux"
    for path in (home, fake_bin, tmux_state):
        path.mkdir(parents=True)

    _write_executable(
        fake_bin / "tmux",
        r'''#!/usr/bin/env python3
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

root = Path(os.environ["FAKE_TMUX_STATE"])
root.mkdir(parents=True, exist_ok=True)
args = sys.argv[1:]
command = args[0] if args else ""

def value(flag, default=None):
    try:
        return args[args.index(flag) + 1]
    except (ValueError, IndexError):
        return default

def marker(session):
    return root / f"{session}.json"

if command in {"set-option", "select-pane", "send-keys", "wait-for"}:
    raise SystemExit(0)
if command == "has-session":
    raise SystemExit(0 if marker(value("-t", "")).exists() else 1)
if command == "new-session":
    session = value("-s")
    workdir = value("-c", os.getcwd())
    runner = args[-1]
    process = subprocess.Popen(
        [runner], cwd=workdir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    marker(session).write_text(json.dumps({"pid": process.pid, "runner": runner}), encoding="utf-8")
    raise SystemExit(0)
if command == "list-panes":
    session = value("-t", "")
    data = json.loads(marker(session).read_text(encoding="utf-8")) if marker(session).exists() else {"pid": 0}
    fmt = value("-F", "")
    if "pane_pid" in fmt:
        print(f"{data['pid']}\t0\tpython3")
    elif "pane_left" in fmt:
        print("%1\torchestrator\t0\t0\t0\t")
    elif "pane_id" in fmt:
        print("%1\torchestrator\t0")
    raise SystemExit(0)
if command == "kill-session":
    session = value("-t", "")
    path = marker(session)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        try:
            os.killpg(int(data["pid"]), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, ValueError):
            pass
        path.unlink(missing_ok=True)
    raise SystemExit(0)
if command == "capture-pane":
    raise SystemExit(0)
if command == "display-message":
    print("fake:0")
    raise SystemExit(0)
if command == "split-window":
    print("fake:0.1")
    raise SystemExit(0)
raise SystemExit(0)
''',
    )

    _write_executable(
        fake_bin / "fake-agent",
        r'''#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from pathlib import Path

mode = os.environ.get("FAKE_AGENT_MODE", "success")
prompt = sys.stdin.read()
handoff = Path(os.environ["AGENT_WORKFLOW_HANDOFF_DIR"])
handoff.mkdir(parents=True, exist_ok=True)
(handoff / "prompt-seen.txt").write_text(prompt, encoding="utf-8")
if mode == "slow":
    time.sleep(float(os.environ.get("FAKE_AGENT_DELAY", "1.0")))
if mode == "hang":
    time.sleep(float(os.environ.get("FAKE_AGENT_DELAY", "30.0")))
try:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], text=True, capture_output=True, check=True
    ).stdout.strip()
except subprocess.CalledProcessError:
    head = None
result = "failed" if mode == "fail" else "completed"
completion = {
    "schema": "agent-workflow/completion/v1",
    "session_id": os.environ["AGENT_WORKFLOW_SESSION_ID"],
    "ticket_id": None,
    "pack_id": None,
    "result": result,
    "base_revision": head,
    "head_revision": head,
    "changed_files": [],
    "criteria": [],
    "commands": [],
    "unresolved": ["intentional failure"] if mode == "fail" else [],
    "usage": None,
}
(handoff / "completion.json").write_text(json.dumps(completion), encoding="utf-8")
result_json = os.environ.get("FAKE_AGENT_RESULT_JSON")
if result_json:
    (handoff / "result.json").write_text(result_json, encoding="utf-8")
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
    # The fake tmux executable models a dedicated session. Do not let the
    # host test runner's real tmux topology select its unsupported shared path.
    environment.pop("TMUX", None)
    environment.pop("TMUX_PANE", None)
    environment.update(
        {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(tmp_path / "config"),
            "XDG_DATA_HOME": str(tmp_path / "data"),
            "XDG_STATE_HOME": str(tmp_path / "state"),
            "FAKE_TMUX_STATE": str(tmux_state),
            "PATH": os.pathsep.join(
                [str(fake_bin), str(installed_product.cli.parent), environment.get("PATH", "")]
            ),
            "PYTHONUNBUFFERED": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": "",
        }
    )
    return environment


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


def wait_for_status(env: dict[str, str], session_id: str, *, timeout: float = 20) -> dict[str, Any]:
    status_path = Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / session_id / "status.json"
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
    raise AssertionError(f"session did not reach a terminal state: {session_id}; last={last}")


def write_config(env: dict[str, str], *, fake_agent: Path, structured_executor: bool = False) -> Path:
    path = Path(env["XDG_CONFIG_HOME"]) / "agent-workflow" / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "[executors.codex]",
                f'command = ["{fake_agent}"]',
                'models = ["gpt-5.4-mini"]',
                'default_model = "gpt-5.4-mini"',
                'model_arg = ["--model"]',
                'interactive_permission_args = []',
                'non_interactive_permission_args = []',
                'environment_allowlist = ["FAKE_AGENT_MODE", "FAKE_AGENT_DELAY", "FAKE_AGENT_RESULT_JSON"]',
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
