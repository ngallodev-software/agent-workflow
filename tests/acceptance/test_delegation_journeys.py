from __future__ import annotations

import json
from pathlib import Path

from agent_workflow.util import sha256_file
from tests.conftest import (
    InstalledProduct,
    fake_agent_path,
    git_repo,
    wait_for_status,
    write_config,
)


def _run_dir(env: dict[str, str], session_id: str) -> Path:
    return Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / session_id


def test_external_executor_completes_with_sealed_user_visible_evidence(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    head = git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Inspect the repository and report completion.\n", encoding="utf-8")

    command_contract = installed_product.json(
        "commands", "--role", "implementation", env=product_env
    )
    represented = {item["command"] for item in command_contract["commands"]}
    assert {"progress", "ack", "agent task-complete"} <= represented

    launched = installed_product.json(
        "launch",
        "success-run",
        repo,
        prompt,
        "--tier",
        "low",
        "--no-interactive",
        "--",
        fake_agent_path,
        env=product_env,
    )
    assert launched["session_id"] == "success-run"

    status = wait_for_status(product_env, "success-run")
    assert status["status"] == "completed"
    run = _run_dir(product_env, "success-run")
    assert (run / "final-receipt.json").stat().st_mode & 0o222 == 0
    assert json.loads((run / "completion.json").read_text())["head_revision"] == head
    handoff = repo / ".agent-workflow-handoff" / "success-run"
    launch_prompt = (handoff / "prompt-seen.txt").read_text()
    assert "Inspect the repository" in launch_prompt
    assert "Do not run `--help` for commands represented in the catalog" in launch_prompt

    contract = json.loads((run / "launch-contract.json").read_text())
    assert contract["schema"] == "agent-workflow/launch-contract/v2"
    binding = contract["command_catalog"]
    assert binding["role"] == "implementation"
    assert binding["catalog_sha256"] == sha256_file(run / binding["catalog_path"])
    assert binding["card_sha256"] == sha256_file(run / binding["card_path"])
    catalog = json.loads((run / binding["catalog_path"]).read_text())
    assert catalog["schema"] == "agent-workflow/command-catalog/v1"
    assert any(item["command"] == "launch" for item in catalog["commands"])
    card = (run / binding["card_path"]).read_text()
    assert "agent-workflow progress" in card
    assert "agent-workflow worktree create" not in card
    exported = json.loads((handoff / "command-contract-env.json").read_text())
    assert exported == {
        "catalog": str(run / binding["catalog_path"]),
        "card": str(run / binding["card_path"]),
        "cli": binding["cli_invocation"][0],
    }

    review = installed_product.json(
        "review", "success-run", "--actor", "reviewer", "--reason", "evidence checked", env=product_env
    )
    assert review["disposition"] == "reviewed"
    accepted = installed_product.json(
        "accept",
        "success-run",
        "--actor",
        "reviewer",
        "--reason",
        "meets acceptance criteria",
        "--revision",
        head,
        env=product_env,
    )
    assert accepted["disposition"] == "accepted"


def test_durable_messages_survive_process_boundaries_and_are_acknowledged(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Wait briefly for steering.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "slow"
    env["FAKE_AGENT_DELAY"] = "1.5"

    installed_product.json(
        "launch", "message-run", repo, prompt, "--tier", "low", "--no-interactive", "--", fake_agent_path,
        env=env,
    )
    steer = installed_product.json(
        "steer", "message-run", "Check the release docs too.", "--actor", "orchestrator", env=env
    )
    watched = installed_product.json(
        "watch", "message-run", "--after", "0", "--timeout", "0.2", env=env
    )
    assert watched[0]["message_id"] == steer["message_id"]
    ack = installed_product.json(
        "ack", "message-run", steer["message_id"], "Applied", "--actor", "agent", env=env
    )
    assert ack["correlation_id"] == steer["message_id"]
    wait_for_status(env, "message-run")

    replayed = installed_product.json(
        "watch", "message-run", "--after", "0", "--timeout", "0", env=env
    )
    assert [item["kind"] for item in replayed] == ["steer", "ack"]



def test_interactive_agent_reuse_requires_completion_selection_and_correlated_acknowledgement(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "first-assignment.md"
    prompt.write_text("Remain available for a second assignment.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "slow"
    env["FAKE_AGENT_DELAY"] = "4.0"

    installed_product.json(
        "launch",
        "reuse-agent",
        repo,
        prompt,
        "--ticket",
        "REUSE-1",
        "--tier",
        "low",
        "--agent-class",
        "implementation",
        "--interactive",
        "--",
        fake_agent_path,
        env=env,
    )
    initial = installed_product.json("agent", "context", "reuse-agent", env=env)
    assert initial["state"] == "busy"
    assert initial["interactive"] is True

    completed = installed_product.json(
        "agent",
        "task-complete",
        "reuse-agent",
        "--actor",
        "acceptance-worker",
        "--summary",
        "First assignment complete",
        "--tag",
        "acceptance",
        env=env,
    )
    assert completed["state"] == "idle_reusable"

    candidates = installed_product.json(
        "agent",
        "candidates",
        repo,
        "--ticket",
        "REUSE-1",
        "--agent-class",
        "implementation",
        "--tag",
        "acceptance",
        env=env,
    )
    selected = next(item for item in candidates if item["session_id"] == "reuse-agent")
    assert selected["eligible"] is True
    assert selected["auto_reuse_eligible"] is True

    second_prompt = tmp_path / "second-assignment.md"
    second_prompt.write_text("Acknowledge this assignment before continuing.\n", encoding="utf-8")
    requested = installed_product.json(
        "agent",
        "reuse",
        "reuse-agent",
        second_prompt,
        "--actor",
        "orchestrator",
        "--ticket",
        "REUSE-2",
        env=env,
    )
    assert requested["context"]["state"] == "reuse_pending"
    correlation_id = requested["message"]["message_id"]
    watched = installed_product.json(
        "watch", "reuse-agent", "--after", "0", "--timeout", "0", env=env
    )
    assert any(
        item["kind"] == "steer" and item["message_id"] == correlation_id
        for item in watched
    )

    installed_product.json(
        "ack",
        "reuse-agent",
        correlation_id,
        "Second assignment accepted",
        "--actor",
        "acceptance-worker",
        env=env,
    )
    acknowledged = installed_product.json("agent", "context", "reuse-agent", env=env)
    assert acknowledged["state"] == "busy"
    assert acknowledged["reuse_count"] == 1
    wait_for_status(env, "reuse-agent")

def test_executor_failure_is_terminal_sealed_and_restartable(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Fail intentionally.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "fail"

    installed_product.json(
        "launch", "failed-run", repo, prompt, "--tier", "low", "--no-interactive", "--", fake_agent_path,
        env=env,
    )
    failed = wait_for_status(env, "failed-run")
    assert failed["status"] == "failed"
    assert failed["exit_code"] == 7
    assert (_run_dir(env, "failed-run") / "final-receipt.json").is_file()

    restarted = installed_product.json("restart", "failed-run", "--new-session", "failed-run-retry", env=env)
    assert restarted["retry_of"] == "failed-run"
    retry = wait_for_status(env, "failed-run-retry")
    assert retry["status"] == "failed"


def test_structured_provider_events_reach_normalized_sealed_evidence(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Emit structured evidence.\n", encoding="utf-8")
    config = write_config(product_env, fake_agent=fake_agent_path)
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "structured"

    installed_product.json(
        "launch",
        "structured-run",
        repo,
        prompt,
        "--config",
        config,
        "--executor",
        "codex",
        "--structured",
        "--no-interactive",
        "--tier",
        "low",
        env=env,
    )
    wait_for_status(env, "structured-run")
    evidence = json.loads((_run_dir(env, "structured-run") / "provider-evidence.json").read_text())
    assert evidence["usage_complete"] is True
    assert evidence["aggregate"]["input_tokens"] == 5
    assert evidence["aggregate"]["cached_input_tokens"] == 1
    assert evidence["aggregate"]["output_tokens"] == 3
