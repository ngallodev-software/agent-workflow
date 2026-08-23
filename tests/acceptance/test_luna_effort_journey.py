from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import InstalledProduct, fake_agent_path, git_repo, wait_for_status


def _contract(env: dict[str, str], session_id: str) -> dict:
    run = Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / session_id
    return json.loads((run / "launch-contract.json").read_text(encoding="utf-8"))


def test_installed_executor_policy_records_luna_effort_and_rejects_bypasses(
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

    # One installed lifecycle owns all supported Codex effort choices.
    for effort in ("low", "medium", "high"):
        session_id = f"luna-effort-{effort}"
        installed_product.json(
            "launch",
            session_id,
            repo,
            prompt,
            "--config",
            config,
            "--executor",
            "codex",
            "--reasoning-effort",
            effort,
            "--structured",
            env=env,
        )
        wait_for_status(env, session_id)
        contract = _contract(env, session_id)
        assert contract["command_plan"]["model"] == "gpt-5.6-luna"
        assert contract["runtime_policy"]["codex_reasoning_effort"] == effort
        assert f"model_reasoning_effort={effort}" in contract["command_plan"]["argv"]
        handoff = repo / ".agent-workflow-handoff" / session_id
        add_dir = contract["command_plan"]["argv"].index("--add-dir")
        assert contract["command_plan"]["argv"][add_dir + 1] == str(handoff)

    # Explicit non-provider commands remain manual and gain no inferred model policy.
    manual_env = dict(product_env)
    manual_env["FAKE_AGENT_MODE"] = "success"
    installed_product.json(
        "launch",
        "manual-explicit-command",
        repo,
        prompt,
        "--structured",
        "--no-interactive",
        "--",
        "sh",
        "-c",
        "exit 0",
        env=manual_env,
    )
    wait_for_status(manual_env, "manual-explicit-command")
    manual = _contract(manual_env, "manual-explicit-command")["command_plan"]
    assert manual["executor"] is None
    assert manual["model"] is None
    assert manual.get("reasoning_effort") is None

    # Explicit Codex commands cannot bypass the Luna model or effort policy.
    rejected_commands = (
        ("codex", "exec", "--model", "gpt-5.4-mini", "-"),
        ("codex", "exec", "-c", "model=gpt-5.4-mini", "-"),
        ("codex", "exec", "-c", "model_reasoning_effort=invalid", "-"),
    )
    for index, command in enumerate(rejected_commands, start=1):
        rejected = installed_product.run(
            "launch",
            f"rejected-codex-bypass-{index}",
            repo,
            prompt,
            "--structured",
            "--no-interactive",
            "--",
            *command,
            env=product_env,
        )
        assert rejected.returncode == 2

    # Interactive explicit Codex execution preserves exactly one Luna model and
    # the explicit effort after the argv is rebuilt for interactive operation.
    codex_shim = fake_agent_path.with_name("codex")
    codex_shim.symlink_to(fake_agent_path)
    interactive_env = dict(product_env)
    interactive_env.update({"FAKE_AGENT_MODE": "slow", "FAKE_AGENT_DELAY": "30"})
    installed_product.json(
        "launch",
        "interactive-explicit-codex",
        repo,
        prompt,
        "--interactive",
        "--",
        "codex",
        "exec",
        "--model",
        "gpt-5.6-luna",
        "-c",
        "model_reasoning_effort=high",
        "-",
        env=interactive_env,
    )
    interactive = _contract(interactive_env, "interactive-explicit-codex")["command_plan"]
    assert interactive["argv"].count("gpt-5.6-luna") == 1
    effort_index = interactive["argv"].index("-c")
    assert interactive["argv"][effort_index : effort_index + 2] == [
        "-c",
        "model_reasoning_effort=high",
    ]
    installed_product.json(
        "terminate", "interactive-explicit-codex", "--grace-seconds", "0", env=interactive_env
    )
