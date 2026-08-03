from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import InstalledProduct, fake_agent_path, git_repo, wait_for_status


def _run_dir(env: dict[str, str], session_id: str) -> Path:
    return Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs" / session_id


def _timeout_plan(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema": "agent-workflow/evaluation-plan/v1",
                "dataset_split": "development",
                "task_ids": ["HARD-001"],
                "repetitions": 1,
                "timeout_seconds": 1,
                "max_retries": 0,
                "scorers": ["schema_validity"],
                "scope": {
                    "writable_paths": [],
                    "writable_trees": [],
                    "disposable_trees": [".agent-workflow-handoff/", ".delegations/"],
                },
                "sandbox": "docker",
            }
        ),
        encoding="utf-8",
    )
    return path


def test_installed_executor_bounds_timeout_output_and_secret_evidence(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Exercise bounded execution.\n", encoding="utf-8")
    plan = _timeout_plan(tmp_path / "timeout.json")

    timeout_env = dict(product_env)
    timeout_env["FAKE_AGENT_MODE"] = "hang"
    timeout_env["FAKE_AGENT_DELAY"] = "30"
    installed_product.json(
        "launch",
        "bounded-timeout",
        repo,
        prompt,
        "--ticket",
        "HARD-001",
        "--evaluation",
        plan,
        "--no-interactive",
        "--",
        fake_agent_path,
        env=timeout_env,
    )
    timeout_status = wait_for_status(timeout_env, "bounded-timeout")
    assert timeout_status["status"] == "failed"
    timeout_run = _run_dir(timeout_env, "bounded-timeout")
    assert json.loads((timeout_run / "final-status.json").read_text())["failure_category"] == "timeout"

    noisy_env = dict(product_env)
    noisy_env["FAKE_AGENT_MODE"] = "noisy"
    installed_product.json(
        "launch",
        "bounded-noisy",
        repo,
        prompt,
        "--ticket",
        "HARD-001",
        "--no-interactive",
        "--",
        fake_agent_path,
        env=noisy_env,
    )
    wait_for_status(noisy_env, "bounded-noisy")
    noisy_run = _run_dir(noisy_env, "bounded-noisy")
    cap = 16 * 1024 * 1024
    assert (noisy_run / "executor-events.jsonl").stat().st_size <= cap
    assert (noisy_run / "executor-stderr.log").stat().st_size <= cap
    assert (noisy_run / "output.log").stat().st_size <= 2 * cap

    secret = "INSTALLED-SYNTHETIC-SECRET"
    secret_env = dict(product_env)
    installed_product.json(
        "launch",
        "bounded-secret",
        repo,
        prompt,
        "--no-interactive",
        "--",
        fake_agent_path,
        "--secret",
        secret,
        env=secret_env,
    )
    wait_for_status(secret_env, "bounded-secret")
    secret_run = _run_dir(secret_env, "bounded-secret")
    for artifact in secret_run.rglob("*"):
        if artifact.is_file() and artifact.stat().st_size <= 2 * 1024 * 1024:
            assert secret.encode() not in artifact.read_bytes(), artifact


def test_completed_executor_over_budget_remains_completed_but_ineligible(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    from tests.conftest import write_config

    repo = tmp_path / "budget-repo"
    git_repo(repo)
    prompt = tmp_path / "budget-prompt.md"
    prompt.write_text("Emit structured evidence.\n", encoding="utf-8")
    plan = tmp_path / "budget-plan.json"
    plan.write_text(
        json.dumps(
            {
                "schema": "agent-workflow/evaluation-plan/v1",
                "dataset_split": "development",
                "task_ids": ["BUDGET-1"],
                "repetitions": 1,
                "timeout_seconds": 60,
                "max_retries": 0,
                "scorers": ["schema_validity"],
                "budgets": {"max_input_tokens": 1, "max_output_tokens": 10},
                "scope": {
                    "writable_paths": [],
                    "writable_trees": [],
                    "disposable_trees": [".agent-workflow-handoff/", ".delegations/"],
                },
                "sandbox": "docker",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    config = write_config(product_env, fake_agent=fake_agent_path)
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "structured"
    installed_product.json(
        "launch",
        "budget-policy-run",
        repo,
        prompt,
        "--ticket",
        "BUDGET-1",
        "--tier",
        "low",
        "--evaluation",
        plan,
        "--config",
        config,
        "--executor",
        "codex",
        "--structured",
        "--no-interactive",
        env=env,
    )
    status = wait_for_status(env, "budget-policy-run")
    assert status["status"] == "completed"
    final = json.loads(
        (_run_dir(env, "budget-policy-run") / "final-status.json").read_text()
    )
    assert final["executor_result"] == "completed"
    assert final["completion_result"] == "valid"
    assert final["policy_result"] == "failed"
    assert final["policy_failure_category"] == "budget_exhausted"
    assert final["acceptance_eligible"] is False
    assert final["failure_category"] is None
