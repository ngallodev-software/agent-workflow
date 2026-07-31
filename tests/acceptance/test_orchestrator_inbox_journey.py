from __future__ import annotations

import subprocess
from pathlib import Path

from agent_workflow.tmux import orchestrator_wakeup_channel
from tests.conftest import InstalledProduct, git_repo, wait_for_status


def test_installed_cli_registers_verified_children_and_deduplicates_inbox(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("fixture child\n", encoding="utf-8")
    child_env = dict(product_env)
    child_env["FAKE_AGENT_MODE"] = "task-complete"
    for session_id in ("child-one", "child-two"):
        repo = tmp_path / session_id
        git_repo(repo)
        installed_product.json(
            "launch", session_id, repo, prompt, "--interactive", "--", fake_agent_path,
            env=child_env,
        )
        assert wait_for_status(child_env, session_id)["status"] == "completed"

    created = installed_product.json(
        "orchestrator", "registry", "create", "main-orchestrator", env=product_env
    )
    assert "/orchestrators/" in created["path"]
    assert "main-orchestrator" not in Path(created["path"]).parent.name
    for session_id in ("child-one", "child-two"):
        installed_product.json(
            "orchestrator", "registry", "register", "main-orchestrator", session_id,
            env=product_env,
        )

    imported = installed_product.json(
        "orchestrator", "inbox", "import", "main-orchestrator", env=product_env
    )
    assert imported["count"] == 2
    events = installed_product.json(
        "orchestrator", "inbox", "list", "main-orchestrator", "--after", "0", env=product_env
    )
    assert [event["sequence"] for event in events] == [1, 2]
    assert [event["kind"] for event in events] == ["agent_idle", "agent_idle"]
    assert all("summary" not in event for event in events)

    repeated = installed_product.json(
        "orchestrator", "inbox", "import", "main-orchestrator", env=product_env
    )
    assert repeated["count"] == 2
    assert all(item["duplicate"] for item in repeated["imported"])
    assert len(installed_product.json("orchestrator", "inbox", "list", "main-orchestrator", env=product_env)) == 2


def test_installed_orchestrator_watch_replays_once_and_resumes_from_cursor(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("watch fixture\n", encoding="utf-8")
    child_env = dict(product_env)
    child_env["FAKE_AGENT_MODE"] = "task-complete"
    repo = tmp_path / "watch-child"
    git_repo(repo)
    installed_product.json(
        "launch", "watch-child", repo, prompt, "--interactive", "--", fake_agent_path,
        env=child_env,
    )
    assert wait_for_status(child_env, "watch-child")["status"] == "completed"
    installed_product.json("orchestrator", "registry", "create", "watcher", env=product_env)
    installed_product.json(
        "orchestrator", "registry", "register", "watcher", "watch-child", env=product_env
    )

    # No wake hint is required for correctness: the bounded replay cycle sees
    # the durable child journal even when the hint is lost.
    first = installed_product.json(
        "orchestrator", "watch", "watcher", "--interval-seconds", "0.01",
        "--poll-seconds", "0.01", "--max-cycles", "1", env=product_env
    )
    assert first["state"] == "completed"
    assert first["advanced"] >= 1
    assert first["imported"] == 1

    # Duplicate best-effort hints remain harmless because source identity and
    # the durable cursor make normalization idempotent.
    channel = orchestrator_wakeup_channel("watcher")
    subprocess.run(["tmux", "wait-for", "-S", channel], env=product_env, check=False)
    subprocess.run(["tmux", "wait-for", "-S", channel], env=product_env, check=False)
    second = installed_product.json(
        "orchestrator", "watch", "watcher", "--interval-seconds", "0.01",
        "--poll-seconds", "0.01", "--max-cycles", "2", env=product_env
    )
    assert second["advanced"] == 0
    assert len(installed_product.json("orchestrator", "inbox", "list", "watcher", env=product_env)) == 1
