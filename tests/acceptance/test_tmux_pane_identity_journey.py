from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path

from tests.conftest import InstalledProduct, fake_agent_path, git_repo, wait_for_status, write_config


def _fake_session(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_fake_session(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def _assert_stable_pane_through_layout_churn(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    case_root = tmp_path / "stable"
    case_root.mkdir()
    repo = case_root / "repo"
    head = git_repo(repo)
    prompt = case_root / "prompt.md"
    prompt.write_text("Remain available while the window layout changes.\n", encoding="utf-8")
    config = write_config(product_env, fake_agent=fake_agent_path)
    env = dict(product_env)
    env.update({"TMUX": "fake-server", "TMUX_PANE": "%0", "FAKE_AGENT_MODE": "slow", "FAKE_AGENT_DELAY": "4"})

    launched = installed_product.json(
        "launch", "stable-pane", repo, prompt, "--config", config,
        "--ticket", "PROC-006", "--agent-class", "implementation", "--interactive",
        "--", fake_agent_path, env=env,
    )
    assert launched["tmux_mode"] == "shared_window"
    pane_id = launched["tmux_pane_id"]
    assert isinstance(pane_id, str) and pane_id.startswith("%")
    assert launched["tmux_target"] == pane_id
    assert launched["tmux_window_target"] == "fake:0"

    state_path = Path(env["FAKE_TMUX_STATE"]) / "fake.json"
    state = _fake_session(state_path)
    target = next(item for item in state["panes"] if item["id"] == pane_id)
    assert target["run_id"] == "stable-pane"
    state["panes"].insert(0, {"id": "%99", "pid": 0, "index": 0, "role": "agent"})
    for index, item in enumerate(state["panes"]):
        item["index"] = index
    _write_fake_session(state_path, state)

    handoff = repo / ".agent-workflow-handoff" / "stable-pane"
    (handoff / "completion.json").write_text(json.dumps({
        "schema": "agent-workflow/completion/v1",
        "session_id": "stable-pane",
        "ticket_id": "PROC-006",
        "pack_id": None,
        "result": "completed",
        "base_revision": head,
        "head_revision": head,
        "changed_files": [],
        "criteria": [{
            "id": "pane-binding",
            "result": "pass",
            "evidence": ["bound pane remained live through layout churn"],
        }],
        "commands": [{
            "argv": ["fake-agent", "slow"],
            "cwd": str(repo),
            "exit_code": 0,
            "receipt": "pane identity fixture completion",
        }],
        "unresolved": [],
        "usage": None,
    }), encoding="utf-8")

    completed = installed_product.json(
        "agent", "task-complete", "stable-pane", "--config", config,
        "--actor", "acceptance-worker", "--summary", "Layout changed but the bound pane remained live.",
        "--keep-alive",
        env=env,
    )
    assert completed["state"] == "idle_reusable"
    assert target["id"] == pane_id


def _assert_destroyed_pane_is_not_rebound(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    case_root = tmp_path / "destroyed"
    case_root.mkdir()
    repo = case_root / "repo"
    git_repo(repo)
    prompt = case_root / "prompt.md"
    prompt.write_text("The pane may be destroyed.\n", encoding="utf-8")
    config = write_config(product_env, fake_agent=fake_agent_path)
    env = dict(product_env)
    env.update({"TMUX": "fake-server", "TMUX_PANE": "%0", "FAKE_AGENT_MODE": "slow", "FAKE_AGENT_DELAY": "4"})

    launched = installed_product.json(
        "launch", "destroyed-pane", repo, prompt, "--config", config,
        "--ticket", "PROC-006", "--agent-class", "implementation", "--interactive",
        "--", fake_agent_path, env=env,
    )
    pane_id = launched["tmux_pane_id"]
    state_path = Path(env["FAKE_TMUX_STATE"]) / "fake.json"
    state = _fake_session(state_path)
    destroyed = next(item for item in state["panes"] if item["id"] == pane_id)
    state["panes"] = [item for item in state["panes"] if item["id"] != pane_id]
    state["panes"].append({"id": "%98", "pid": 0, "index": 1, "role": "agent"})
    _write_fake_session(state_path, state)

    result = installed_product.run(
        "--json", "agent", "task-complete", "destroyed-pane", "--config", config,
        "--actor", "acceptance-worker", "--summary", "Must fail closed.", env=env,
    )
    assert result.returncode != 0
    assert "live agent pane" in result.stderr
    try:
        os.killpg(int(destroyed["pid"]), signal.SIGTERM)
    except (ProcessLookupError, PermissionError, ValueError):
        pass


def _assert_completed_run_closes_bound_pane(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    case_root = tmp_path / "closeout"
    case_root.mkdir()
    repo = case_root / "repo"
    git_repo(repo)
    prompt = case_root / "prompt.md"
    prompt.write_text("Complete and close the shared pane.\n", encoding="utf-8")
    config = write_config(product_env, fake_agent=fake_agent_path)
    env = dict(product_env)
    env.update({
        "TMUX": "fake-server", "TMUX_PANE": "%0", "FAKE_AGENT_MODE": "task-complete",
        "FAKE_AGENT_DELAY": "0.2",
    })

    launched = installed_product.json(
        "launch", "closeout-pane", repo, prompt, "--config", config,
        "--ticket", "PROC-006", "--agent-class", "implementation", "--interactive",
        "--", fake_agent_path, env=env,
    )
    pane_id = launched["tmux_pane_id"]
    status = wait_for_status(env, "closeout-pane")
    assert status["status"] == "completed"
    terminated = installed_product.json(
        "terminate", "closeout-pane", "--grace-seconds", "0", env=env
    )
    assert terminated["status"] == "completed"

    state_path = Path(env["FAKE_TMUX_STATE"]) / "fake.json"
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        state = _fake_session(state_path)
        if all(item["id"] != pane_id for item in state.get("panes", [])):
            break
        time.sleep(0.05)
    state = _fake_session(state_path)
    assert all(item["id"] != pane_id for item in state.get("panes", []))
    observed = installed_product.json("status", "closeout-pane", env=env)
    assert observed["tmux_alive"] is False


def test_installed_tmux_pane_identity_lifecycle_is_stable_and_fail_closed(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    _assert_stable_pane_through_layout_churn(
        installed_product, product_env, fake_agent_path, tmp_path
    )
    _assert_destroyed_pane_is_not_rebound(
        installed_product, product_env, fake_agent_path, tmp_path
    )
    _assert_completed_run_closes_bound_pane(
        installed_product, product_env, fake_agent_path, tmp_path
    )
