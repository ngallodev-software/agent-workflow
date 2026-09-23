from __future__ import annotations

import json
import os
import time
from pathlib import Path

from tests.conftest import (
    InstalledProduct,
    git_repo,
    prepare_and_start_agent_run,
    wait_for_status,
    write_config,
)


def _run_dir(env: dict[str, str], agent_run_id: str) -> Path:
    return Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / agent_run_id


def test_headless_completion_is_sealed_and_lifecycle_is_separate(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    head = git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Inspect the repository and report completion.\n", encoding="utf-8")

    prepare_and_start_agent_run(
        installed_product,
        "success-run", repo, prompt, "--tier", "low", "--", fake_agent_path,
        env=product_env,
    )
    status = wait_for_status(product_env, "success-run")
    assert status["status"] == "completed"
    assert status["disposition"] is None

    run = _run_dir(product_env, "success-run")
    completion = json.loads((run / "completion.json").read_text())
    assert completion["head_revision"] == head
    assert (run / "final-receipt.json").is_file()
    assert (run / "final-receipt.json").stat().st_mode & 0o222 == 0
    timing = json.loads((run / "terminal-timing.json").read_text())
    assert timing["schema"] == "agent-workflow/terminal-timing/v1"
    assert timing["agent_run_id"] == "success-run"
    assert timing["pre_seal_total_seconds"] >= 0
    assert timing["sections"]["completion_collection"] >= 0
    assert timing["sections"]["execution_evidence"] >= 0
    receipt = json.loads((run / "final-receipt.json").read_text())
    sealed_paths = {item["path"] for item in receipt["artifacts"]}
    assert "terminal-timing.json" in sealed_paths

    reviewed = installed_product.json(
        "agent-run", "review", "success-run", "--actor", "reviewer", "--reason", "evidence inspected",
        env=product_env,
    )
    assert reviewed["disposition"] == "reviewed"
    accepted = installed_product.json(
        "agent-run", "accept", "success-run", "--actor", "maintainer", "--reason", "accepted",
        env=product_env,
    )
    assert accepted["disposition"] == "accepted"
    projected = installed_product.json("agent-run", "status", "success-run", env=product_env)
    assert projected["disposition"] == "accepted"
    summary = installed_product.json("agent-run", "summary", "success-run", env=product_env)
    assert summary["review"]["state"] == "reviewed"
    assert summary["review"]["actor"] == "reviewer"
    assert summary["acceptance"]["state"] == "accepted"
    assert summary["acceptance"]["actor"] == "maintainer"


def test_persist_first_steer_ack_and_replay_survive_process_boundaries(
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
    env.update({"FAKE_AGENT_MODE": "slow", "FAKE_AGENT_DELAY": "30"})

    prepare_and_start_agent_run(
        installed_product,
        "message-run", repo, prompt, "--tier", "low", "--", fake_agent_path,
        env=env,
    )
    steer = installed_product.json(
        "agent-run", "steer", "message-run", "Check the release docs too.",
        "--actor", "orchestrator", env=env,
    )
    run = _run_dir(env, "message-run")
    messages_path = run / "messages.jsonl"
    persisted = [
        json.loads(line)
        for line in messages_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert persisted[0]["message_id"] == steer["message_id"]
    assert persisted[0]["kind"] == "steer"

    ack = installed_product.json(
        "agent-run", "ack", "message-run", steer["message_id"], "Applied",
        "--actor", "agent", env=env,
    )
    assert ack["correlation_id"] == steer["message_id"]
    duplicate = installed_product.json(
        "agent-run", "ack", "message-run", steer["message_id"], "Applied again",
        "--actor", "agent", env=env,
    )
    assert duplicate["duplicate"] is True

    installed_product.json(
        "agent-run", "terminate", "message-run", "--grace-seconds", "0", env=env,
    )
    replayed = [
        json.loads(line)
        for line in messages_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [item["kind"] for item in replayed] == ["steer", "ack"]


def test_invalid_completion_fails_but_evidence_is_preserved(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Return a substantive completion report.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_EMPTY_COMPLETION"] = "1"

    prepare_and_start_agent_run(
        installed_product,
        "empty-completion", repo, prompt, "--tier", "low", "--", fake_agent_path,
        env=env,
    )
    status = wait_for_status(env, "empty-completion")
    assert status["status"] == "failed"
    assert status["completion_validation_status"] == "invalid"
    run = _run_dir(env, "empty-completion")
    collection = json.loads((run / "collections" / "completion.json").read_text())
    assert collection["validation_status"] == "invalid"
    assert (run / "process-result.json").is_file()
    assert (run / "final-receipt.json").is_file()


def test_valid_completion_survives_bounded_auxiliary_output(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Complete despite noisy diagnostics.\n", encoding="utf-8")
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "noisy"

    prepare_and_start_agent_run(
        installed_product,
        "noisy-completion",
        repo,
        prompt,
        "--tier",
        "low",
        "--",
        fake_agent_path,
        env=env,
    )
    status = wait_for_status(env, "noisy-completion")
    assert status["status"] == "completed"
    assert status["completion_validation_status"] == "valid"
    assert status["stdout_truncated"] is True
    assert status["stderr_truncated"] is True


def test_failed_headless_run_restarts_as_new_agent_run_with_lineage(
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

    prepare_and_start_agent_run(
        installed_product,
        "failed-run", repo, prompt, "--tier", "low", "--", fake_agent_path,
        env=env,
    )
    failed = wait_for_status(env, "failed-run")
    assert failed["status"] == "failed"
    assert failed["exit_code"] == 7

    env["FAKE_AGENT_MODE"] = "success"
    restarted = installed_product.json(
        "agent-run", "restart", "failed-run", "--new-agent-run-id", "failed-run-retry", "--start", env=env,
    )
    assert restarted["retry_of_agent_run_id"] == "failed-run"
    retry = wait_for_status(env, "failed-run-retry")
    assert retry["status"] == "completed"
    contract = json.loads((_run_dir(env, "failed-run-retry") / "agent-run-contract.json").read_text())
    assert contract["agent_run"]["retry_of_agent_run_id"] == "failed-run"


def test_retry_refreshes_configured_executor_and_environment_policy(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Retry with current executor configuration.\n", encoding="utf-8")
    config = write_config(product_env, fake_agent=fake_agent_path)
    codex = fake_agent_path.parent / "codex"
    codex.symlink_to(fake_agent_path)
    config_text = config.read_text(encoding="utf-8").replace(
        f'command = ["{fake_agent_path}"]', f'command = ["{codex}"]'
    )
    config.write_text(config_text, encoding="utf-8")

    prepare_and_start_agent_run(
        installed_product, "configured-retry", repo, prompt, "--tier", "low",
        env=product_env,
    )
    assert wait_for_status(product_env, "configured-retry")["status"] == "completed"
    original_run = _run_dir(product_env, "configured-retry")
    original_command = json.loads((original_run / "command.json").read_text())

    wrapper = tmp_path / "codex-wrapper"
    wrapper.write_text(f"#!/bin/sh\nexec {os.fspath(fake_agent_path)} \"$@\"\n", encoding="utf-8")
    wrapper.chmod(0o755)
    config.write_text(
        config_text.replace(f'command = ["{codex}"]', f'command = ["{wrapper}"]')
        .replace('"FAKE_AGENT_EMIT_PROGRESS"]', '"FAKE_AGENT_EMIT_PROGRESS", "TYPESAFE_API_KEY"]'),
        encoding="utf-8",
    )
    retry = installed_product.json(
        "agent-run", "restart", "configured-retry", "--new-agent-run-id", "configured-retry-2",
        env={**product_env, "TYPESAFE_API_KEY": "secret"},
    )
    assert retry["retry_of_agent_run_id"] == "configured-retry"
    retry_run = _run_dir(product_env, "configured-retry-2")
    retry_command = json.loads((retry_run / "command.json").read_text())
    assert retry_command["argv"][0] == str(wrapper)
    assert retry_command["argv"] != original_command["argv"]
    assert "TYPESAFE_API_KEY" in retry_command["environment_allowlist"]
    assert json.loads((original_run / "command.json").read_text()) == original_command


def test_headless_codex_automatically_captures_structured_provider_usage(
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

    prepare_and_start_agent_run(
        installed_product,
        "structured-run", repo, prompt,
        "--config", config, "--executor", "codex", "--tier", "low",
        env=env,
    )
    assert wait_for_status(env, "structured-run")["status"] == "completed"
    run = _run_dir(env, "structured-run")
    command = json.loads((run / "command.json").read_text())
    assert command["stream_format"] == "codex-jsonl"
    assert "--json" in command["argv"]

    evidence = json.loads((run / "provider-evidence.json").read_text())
    assert evidence["usage_complete"] is True
    assert evidence["aggregate"]["input_tokens"] == 5
    assert evidence["aggregate"]["cached_input_tokens"] == 1
    assert evidence["aggregate"]["cache_write_input_tokens"] == 0
    assert evidence["aggregate"]["output_tokens"] == 3
    assert evidence["aggregate"]["reasoning_output_tokens"] == 2
    assert evidence["aggregate"]["provider_total_tokens"] == 8

    metrics = json.loads((run / "execution-metrics.json").read_text())
    total = next(item for item in metrics["stages"] if item["stage"] == "total")
    assert total["input_tokens"] == 5
    assert total["cached_input_tokens"] == 1
    assert total["cache_write_input_tokens"] == 0
    assert total["output_tokens"] == 3
    assert total["reasoning_output_tokens"] == 2
    assert total["provider_total_tokens"] == 8
