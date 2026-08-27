from __future__ import annotations

import json
import time
from pathlib import Path

from tests.conftest import (
    prepare_and_start_agent_run,
    InstalledProduct,
    fake_agent_path,
    git_repo,
    wait_for_status,
    write_config,
)


def test_sealed_evaluation_runs_score_report_collect_and_compare_through_installed_cli(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    fake_agent_path: Path,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    git_repo(repo)
    prompt = tmp_path / "evaluation-task.md"
    prompt.write_text("Inspect README.md without modifying the repository.\n", encoding="utf-8")
    plan = tmp_path / "evaluation.json"
    plan.write_text(
        json.dumps(
            {
                "schema": "agent-workflow/evaluation-plan/v1",
                "dataset_split": "development",
                "task_ids": ["EVAL-1"],
                "repetitions": 1,
                "timeout_seconds": 60,
                "max_retries": 0,
                "scorers": ["schema_validity", "writable_scope"],
                "scope": {
                    "writable_paths": [],
                    "writable_trees": [],
                    "disposable_trees": [".agent-workflow-handoff/", ".delegations/"],
                },
                "sandbox": "docker",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    config = write_config(product_env, fake_agent=fake_agent_path)
    env = dict(product_env)
    env["FAKE_AGENT_MODE"] = "structured"
    state_runs = Path(env["XDG_STATE_HOME"]) / "agent-workflow" / "runs"

    # One sealed evaluated Agent Run exercises the full automatic lifecycle.
    # Comparison/reporting is pure evidence processing, so duplicate the collected
    # trial artifact rather than paying for a second equivalent worker execution.
    agent_run_id = "baseline-eval"
    prepare_and_start_agent_run(
        installed_product, agent_run_id, repo, prompt,
        "--ticket", "EVAL-1", "--tier", "low", "--evaluation", plan,
        "--config", config, "--executor", "codex", "--structured", "--no-interactive",
        env=env,
    )
    status = wait_for_status(env, agent_run_id)
    assert status["status"] == "completed"
    run_dir = state_runs / agent_run_id
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not (run_dir / "ledger-row.json").is_file():
        time.sleep(0.05)
    assert (run_dir / "scores" / "score-set.json").is_file()
    assert (run_dir / "reports" / "evaluation.md").is_file()
    assert (run_dir / "ledger-row.json").is_file()
    auto_ledger = json.loads((run_dir / "ledger-row.json").read_text(encoding="utf-8"))
    assert auto_ledger["receipt_verification"] == "verified"
    assert auto_ledger["attempt_classification"] == "acceptance-eligible"
    assert auto_ledger["acceptance_eligible"] is True

    evidence = run_dir / "trials.json"
    collected = installed_product.json("eval", "collect", run_dir, "--output", evidence, env=env)
    assert collected["trials"] == 1
    trial = json.loads(evidence.read_text(encoding="utf-8"))["trials"][0]
    assert trial["task_id"] == "EVAL-1"
    assert trial["verdict"] == "pass"
    assert trial["input_tokens"] == 5
    assert trial["output_tokens"] == 3

    candidate_evidence = tmp_path / "candidate-trials.json"
    candidate_evidence.write_bytes(evidence.read_bytes())
    evidence_files = [evidence, candidate_evidence]

    comparison_path = tmp_path / "comparison.json"
    comparison = installed_product.json(
        "eval",
        "compare",
        evidence_files[0],
        evidence_files[1],
        "--output",
        comparison_path,
        env=env,
    )
    assert comparison["paired_n"] == 1
    assert comparison["winner"] is None
    assert comparison["baseline"]["rate"] == 1.0
    assert comparison["candidate"]["rate"] == 1.0
    assert json.loads(comparison_path.read_text(encoding="utf-8"))["schema"] == "agent-workflow/comparison/v1"
