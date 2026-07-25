from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import InstalledProduct, fake_agent_path, git_repo, wait_for_status


@pytest.mark.future
@pytest.mark.xfail(
    strict=True,
    reason="BKL-002: detached executors do not yet consume and acknowledge post-launch steering",
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
    env["FAKE_AGENT_DELAY"] = "2.0"

    installed_product.json(
        "launch",
        "late-steer-future",
        repo,
        prompt,
        "--tier",
        "low",
        "--no-interactive",
        "--",
        fake_agent_path,
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
            "watch", "late-steer-future", "--after", "0", "--timeout", "1.0", env=env
        )
        assert any(
            item.get("kind") == "ack" and item.get("correlation_id") == steer["message_id"]
            for item in messages
        )
    finally:
        wait_for_status(env, "late-steer-future")
