from __future__ import annotations

from pathlib import Path


from tests.conftest import (
    InstalledProduct,
    fake_agent_path,
    git_repo,
    write_config,
)


def test_detached_executor_consumes_post_launch_steer_without_restart(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Remain active long enough to receive steering.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "slow"
    env["FAKE_AGENT_DELAY"] = "30"
    env["FAKE_AGENT_AUTO_STEER"] = "1"
    config = write_config(env, fake_agent=fake_agent_path)

    installed_product.json(
        "launch",
        "late-steer-future",
        repo,
        prompt,
        "--tier",
        "low",
        "--config",
        config,
        "--executor",
        "codex",
        "--no-interactive",
        env=env,
    )
    steer = installed_product.json(
        "steer",
        "late-steer-future",
        "Report progress before continuing.",
        "--actor",
        "orchestrator",
        env=env,
    )
    try:
        messages = installed_product.json(
            "watch", "late-steer-future", "--after", steer["sequence"],
            "--timeout", "3.0", env=env
        )
        assert any(
            item.get("kind") == "ack" and item.get("correlation_id") == steer["message_id"]
            for item in messages
        )
    finally:
        installed_product.json(
            "terminate", "late-steer-future", "--grace-seconds", "0", env=env
        )


def test_cooperative_executor_can_reject_and_unverified_mode_is_unsupported(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    import json

    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Remain active for steering disposition.\n", encoding="utf-8")

    rejected_env = dict(product_env)
    rejected_env.update(
        {
            "FAKE_AGENT_MODE": "slow",
            "FAKE_AGENT_DELAY": "30",
            "FAKE_AGENT_AUTO_STEER": "1",
            "FAKE_AGENT_STEER_OUTCOME": "rejected",
        }
    )
    config = write_config(rejected_env, fake_agent=fake_agent_path)
    installed_product.json(
        "launch", "late-steer-rejected", repo, prompt, "--tier", "low",
        "--config", config, "--executor", "codex", "--no-interactive",
        env=rejected_env,
    )
    steer = installed_product.json(
        "steer", "late-steer-rejected", "Do not apply this instruction.",
        "--actor", "orchestrator", env=rejected_env,
    )
    messages = installed_product.json(
        "watch", "late-steer-rejected", "--after", steer["sequence"],
        "--timeout", "3.0", env=rejected_env,
    )
    assert any(
        item.get("kind") == "ack"
        and item.get("correlation_id") == steer["message_id"]
        for item in messages
    )
    journal = (
        Path(rejected_env["XDG_STATE_HOME"])
        / "agent-workflow" / "runs" / "late-steer-rejected"
        / "steering-delivery.jsonl"
    )
    outcomes = [json.loads(line)["outcome"] for line in journal.read_text().splitlines()]
    assert outcomes[-1] == "rejected"
    assert "applied" not in outcomes
    installed_product.json(
        "terminate", "late-steer-rejected", "--grace-seconds", "0", env=rejected_env
    )

    unsupported_env = dict(product_env)
    unsupported_env.update({"FAKE_AGENT_MODE": "slow", "FAKE_AGENT_DELAY": "30"})
    installed_product.json(
        "launch", "late-steer-unsupported", repo, prompt, "--tier", "low",
        "--no-interactive", "--", fake_agent_path, env=unsupported_env,
    )
    unsupported = installed_product.json(
        "steer", "late-steer-unsupported", "Attempt unsupported delivery.",
        "--actor", "orchestrator", env=unsupported_env,
    )
    assert unsupported["delivery_outcome"] == "unsupported"
    installed_product.json(
        "terminate", "late-steer-unsupported", "--grace-seconds", "0", env=unsupported_env
    )
