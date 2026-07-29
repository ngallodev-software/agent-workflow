from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import InstalledProduct, fake_agent_path, git_repo, wait_for_status, write_config


def _fake_session(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_fake_session(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_shared_window_uses_stable_pane_id_through_layout_churn(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
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
    state["panes"].insert(0, {"id": "%99", "pid": 0, "index": 0, "role": "agent"})
    for index, item in enumerate(state["panes"]):
        item["index"] = index
    _write_fake_session(state_path, state)

    completed = installed_product.json(
        "agent", "task-complete", "stable-pane", "--config", config,
        "--actor", "acceptance-worker", "--summary", "Layout changed but the bound pane remained live.",
        env=env,
    )
    assert completed["state"] == "idle_reusable"
    assert target["id"] == pane_id


def test_destroyed_stable_pane_is_not_rebound_to_replacement(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
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
    state["panes"] = [item for item in state["panes"] if item["id"] != pane_id]
    state["panes"].append({"id": "%98", "pid": 0, "index": 1, "role": "agent"})
    _write_fake_session(state_path, state)

    result = installed_product.run(
        "--json", "agent", "task-complete", "destroyed-pane", "--config", config,
        "--actor", "acceptance-worker", "--summary", "Must fail closed.", env=env,
    )
    assert result.returncode != 0
    assert "live agent pane" in result.stderr
