from __future__ import annotations

import json
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

    reviewed = installed_product.json(
        "agent-run", "review", "success-run", "--actor", "reviewer", "--reason", "evidence inspected",
        env=product_env,
    )
    assert reviewed["disposition"] == "reviewed"
    accepted = installed_product.json(
        "agent-run", "accept", "success-run", "--actor", "maintainer", "--reason", "accepted",
        "--revision", head, env=product_env,
    )
    assert accepted["disposition"] == "accepted"
    projected = installed_product.json("agent-run", "status", "success-run", env=product_env)
    assert projected["disposition"] == "accepted"


def test_persist_first_steer_progress_ack_and_replay_survive_process_boundaries(
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
    watched = installed_product.json(
        "agent-run", "watch", "message-run", "--after", "0", "--timeout", "0.5", env=env,
    )
    assert watched[0]["message_id"] == steer["message_id"]
    assert watched[0]["kind"] == "steer"

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
    replayed = installed_product.json(
        "agent-run", "watch", "message-run", "--after", "0", "--timeout", "0", env=env,
    )
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
        "agent-run", "restart", "failed-run", "--new-agent-run-id", "failed-run-retry", env=env,
    )
    assert restarted["retry_of_agent_run_id"] == "failed-run"
    retry = wait_for_status(env, "failed-run-retry")
    assert retry["status"] == "completed"
    contract = json.loads((_run_dir(env, "failed-run-retry") / "agent-run-contract.json").read_text())
    assert contract["agent_run"]["retry_of_agent_run_id"] == "failed-run"


def test_structured_provider_usage_reaches_sealed_evidence(
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
        "--config", config, "--executor", "codex", "--structured", "--tier", "low",
        env=env,
    )
    assert wait_for_status(env, "structured-run")["status"] == "completed"
    evidence = json.loads((_run_dir(env, "structured-run") / "provider-evidence.json").read_text())
    assert evidence["usage_complete"] is True
    assert evidence["aggregate"]["input_tokens"] == 5
    assert evidence["aggregate"]["cached_input_tokens"] == 1
    assert evidence["aggregate"]["output_tokens"] == 3
