from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent_workflow.cli_handlers.eval import handle_eval_command
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError


def _args(command: str, **values: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "eval_command": command,
        "source": Path("evaluation.yaml"),
        "pack": None,
        "kind": "evaluation",
        "output": Path("output.json"),
        "manifest": Path("manifest.json"),
        "baseline": Path("baseline.json"),
        "candidate": Path("candidate.json"),
        "markdown": None,
        "run": "run-1",
        "retention_class": "standard",
        "output_dir": None,
        "oracle_root": None,
        "format": "json",
        "prompt": Path("prompt.md"),
        "executor": "codex",
        "dockerfile": Path("Dockerfile"),
        "model": "model",
        "log_dir": Path("logs"),
        "instance_id": "instance-1",
        "runs": [Path("run-a"), Path("run-b")],
    }
    base.update(values)
    return argparse.Namespace(**base)


def test_validate_preserves_plan_identity(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    plan = SimpleNamespace(
        path=tmp_path / "evaluation.yaml",
        data={"schema": "agent-workflow/evaluation/v1"},
        sha256="a" * 64,
        task_ids=("T-1", "T-2"),
    )
    with patch(
        "agent_workflow.cli_handlers.eval.validate_evaluation", return_value=plan
    ) as call:
        data, output_complete = handle_eval_command(settings, _args("validate"))

    assert output_complete is False
    assert data == {
        "path": str(plan.path),
        "schema": "agent-workflow/evaluation/v1",
        "sha256": "a" * 64,
        "task_ids": ["T-1", "T-2"],
    }
    call.assert_called_once()


def test_report_without_output_owns_rendering(tmp_path: Path, capsys) -> None:
    settings = defaults(tmp_path / "config.toml")
    run = tmp_path / "run"
    run.mkdir()
    args = _args("report", run=run, output=None, format="markdown")
    with (
        patch(
            "agent_workflow.cli_handlers.eval.verify_seal_details",
            return_value=({}, "b" * 64),
        ),
        patch(
            "agent_workflow.cli_handlers.eval.build_report",
            return_value={"schema": "agent-workflow/evaluation-report/v1"},
        ),
        patch(
            "agent_workflow.cli_handlers.eval.render_markdown",
            return_value="# Report\n",
        ),
    ):
        data, output_complete = handle_eval_command(settings, args)

    assert data is None
    assert output_complete is True
    assert capsys.readouterr().out == "# Report\n"


def test_compare_rejects_mixed_currencies_before_writing(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    args = _args(
        "compare",
        baseline=tmp_path / "baseline.json",
        candidate=tmp_path / "candidate.json",
        output=tmp_path / "comparison.json",
    )
    with patch(
        "agent_workflow.cli_handlers.eval.load_trials",
        side_effect=[
            [{"trial_id": "a", "cost": 1, "currency": "USD"}],
            [{"trial_id": "b", "cost": 1, "currency": "EUR"}],
        ],
    ):
        with pytest.raises(WorkflowError, match="different currencies"):
            handle_eval_command(settings, args)
    assert not args.output.exists()


def test_benchmark_report_rejects_input_overwrite(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    manifest = tmp_path / "manifest.json"
    args = _args(
        "benchmark-report",
        manifest=manifest,
        baseline=tmp_path / "baseline.json",
        candidate=tmp_path / "candidate.json",
        output=manifest,
    )
    with pytest.raises(WorkflowError, match="must not overwrite"):
        handle_eval_command(settings, args)
