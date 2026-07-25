from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from tests.conftest import InstalledProduct, fake_agent_path, git_repo, wait_for_status


def _real_host_env(product_env: dict[str, str]) -> dict[str, str]:
    env = dict(product_env)
    path_parts = env.get("PATH", "").split(os.pathsep)
    # product_env prepends the deterministic fake-command directory. Live tests
    # keep the installed wheel but deliberately cross the real host tmux boundary.
    env["PATH"] = os.pathsep.join(path_parts[1:])
    return env


def _cleanup_tmux(session_id: str, env: dict[str, str]) -> None:
    tmux = shutil.which("tmux", path=env.get("PATH"))
    if tmux:
        subprocess.run(
            [tmux, "kill-session", "-t", session_id],
            env=env,
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )


@pytest.mark.live
def test_real_tmux_runs_the_installed_product_to_a_sealed_terminal_receipt(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    if os.environ.get("AGENT_WORKFLOW_LIVE_TMUX") != "1":
        pytest.skip("set AGENT_WORKFLOW_LIVE_TMUX=1")
    env = _real_host_env(product_env)
    if not shutil.which("tmux", path=env.get("PATH")):
        pytest.skip("real tmux is not installed")

    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Read README.md and complete without modifying files.\n", encoding="utf-8")
    session_id = f"live-tmux-{uuid.uuid4().hex[:10]}"
    try:
        installed_product.json(
            "launch",
            session_id,
            repo,
            prompt,
            "--tier",
            "low",
            "--no-interactive",
            "--",
            fake_agent_path,
            env=env,
        )
        status = wait_for_status(env, session_id, timeout=60)
        assert status["status"] == "completed"
        run_dir = Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / session_id
        assert (run_dir / "final-receipt.json").is_file()
        assert (run_dir / "output.log").read_text(encoding="utf-8").strip()
    finally:
        _cleanup_tmux(session_id, env)


@pytest.mark.live
def test_real_configured_executor_completes_a_read_only_smoke_journey(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    tmp_path: Path,
) -> None:
    executor = os.environ.get("AGENT_WORKFLOW_LIVE_EXECUTOR")
    if executor not in {"codex", "claude"}:
        pytest.skip("set AGENT_WORKFLOW_LIVE_EXECUTOR=codex or claude")
    env = _real_host_env(product_env)
    if not shutil.which("tmux", path=env.get("PATH")):
        pytest.skip("real tmux is not installed")
    if not shutil.which(executor, path=env.get("PATH")):
        pytest.skip(f"configured executor is not installed: {executor}")

    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text(
        "Inspect README.md. Do not edit any files. Produce the required completion handoff.\n",
        encoding="utf-8",
    )
    session_id = f"live-{executor}-{uuid.uuid4().hex[:10]}"
    try:
        installed_product.json(
            "launch",
            session_id,
            repo,
            prompt,
            "--ticket",
            "LIVE-SMOKE",
            "--tier",
            "low",
            "--executor",
            executor,
            "--structured",
            "--no-interactive",
            env=env,
            timeout=60,
        )
        status = wait_for_status(env, session_id, timeout=600)
        assert status["status"] == "completed"
        run_dir = Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / session_id
        assert (run_dir / "final-receipt.json").is_file()
        assert (run_dir / "completion.json").is_file()
    finally:
        _cleanup_tmux(session_id, env)
