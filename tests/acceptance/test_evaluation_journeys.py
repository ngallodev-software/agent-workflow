from __future__ import annotations

import json
from pathlib import Path

from tests.conftest import (
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

    validated = installed_product.json("eval", "validate", plan, env=env)
    assert validated["task_ids"] == ["EVAL-1"]

    evidence_files: list[Path] = []
    for session_id in ("baseline-eval", "candidate-eval"):
        installed_product.json(
            "launch",
            session_id,
            repo,
            prompt,
            "--ticket",
            "EVAL-1",
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
        status = wait_for_status(env, session_id)
        assert status["status"] == "completed"
        run_dir = state_runs / session_id

        score = installed_product.json("eval", "score", run_dir, env=env)
        assert score["verdict"] == "pass"
        assert {item["scorer"]["id"] for item in score["scores"]} >= {
            "schema_validity",
            "writable_scope",
        }

        report = tmp_path / f"{session_id}-report.md"
        rendered = installed_product.json(
            "eval", "report", run_dir, "--format", "markdown", "--output", report, env=env
        )
        assert rendered["output"] == str(report)
        assert "Overall deterministic verdict: `pass`" in report.read_text(encoding="utf-8")

        evidence = tmp_path / f"{session_id}-evidence.json"
        collected = installed_product.json("eval", "collect", run_dir, "--output", evidence, env=env)
        assert collected["trials"] == 1
        trial = json.loads(evidence.read_text(encoding="utf-8"))["trials"][0]
        assert trial["task_id"] == "EVAL-1"
        assert trial["verdict"] == "pass"
        assert trial["input_tokens"] == 5
        assert trial["output_tokens"] == 3
        evidence_files.append(evidence)

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
