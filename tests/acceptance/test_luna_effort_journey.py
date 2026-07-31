from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import InstalledProduct, fake_agent_path, git_repo, wait_for_status


def test_installed_codex_fixture_records_luna_effort(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Use the controlled fixture.\n", encoding="utf-8")
    config = tmp_path / "config.toml"
    config.write_text(
        "\n".join(
            [
                "schema_version = 1",
                "[git]",
                "require_clean_source = false",
                "[executors.codex]",
                f'command = ["{fake_agent_path}"]',
                'models = ["gpt-5.6-luna"]',
                'default_model = "gpt-5.6-luna"',
                'reasoning_effort = "high"',
                'model_arg = ["--model"]',
                "[agents]",
                'default_executor = "codex"',
                'default_class = "implementation"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "structured"
    installed_product.json(
        "launch",
        "luna-effort-journey",
        repo,
        prompt,
        "--config",
        config,
        "--executor",
        "codex",
        "--structured",
        env=env,
    )
    wait_for_status(env, "luna-effort-journey")
    run = Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / "luna-effort-journey"
    contract = json.loads((run / "launch-contract.json").read_text(encoding="utf-8"))
    assert contract["command_plan"]["model"] == "gpt-5.6-luna"
    assert contract["runtime_policy"]["codex_reasoning_effort"] == "high"
    assert "model_reasoning_effort=high" in contract["command_plan"]["argv"]
    handoff = repo / ".agent-workflow-handoff" / "luna-effort-journey"
    add_dir = contract["command_plan"]["argv"].index("--add-dir")
    assert contract["command_plan"]["argv"][add_dir + 1] == str(handoff)
