from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_workflow.cli_handlers.benchmark import handle_benchmark_command
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError


def _args(command: str, **values: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "benchmark_command": command,
        "spec": Path("benchmark.yaml"),
        "executor": "codex",
        "policy": Path("policy.yaml"),
        "runtime_lock": Path("runtime-lock.json"),
        "claim_level": "synthetic",
        "base_lock": Path("base-lock.json"),
        "output": Path("output.json"),
        "container_image": None,
        "destination": Path("suite"),
        "benchmark_id": "comparative-v1",
        "force": False,
        "repo": Path("repo"),
        "base_ref": "HEAD",
        "run_id": "run-1",
        "repetitions": 2,
        "worktree_root": Path("worktrees"),
        "allow_dirty": False,
        "assistance_cohort": None,
        "run": "run-1",
        "reviewer": "reviewer",
        "input": Path("review.json"),
        "remove_worktrees": False,
    }
    base.update(values)
    return argparse.Namespace(**base)


def test_plan_preserves_all_authority_inputs(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    args = _args("plan")
    with patch(
        "agent_workflow.cli_handlers.benchmark.create_benchmark_plan",
        return_value={"run_id": "run-1"},
    ) as call:
        result = handle_benchmark_command(settings, args)
    assert result == {"run_id": "run-1"}
    call.assert_called_once_with(
        settings,
        spec=args.spec,
        executor="codex",
        repo=args.repo,
        base_ref="HEAD",
        run_id="run-1",
        repetitions=2,
        worktree_root=args.worktree_root,
        allow_dirty=False,
        assistance_cohort=None,
        policy=args.policy,
        runtime_lock=args.runtime_lock,
    )


def test_review_preserves_reviewer_and_input(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    args = _args("review")
    with patch(
        "agent_workflow.cli_handlers.benchmark.benchmark_review",
        return_value={"state": "submitted"},
    ) as call:
        result = handle_benchmark_command(settings, args)
    assert result == {"state": "submitted"}
    call.assert_called_once_with(
        settings,
        "run-1",
        reviewer="reviewer",
        input_path=args.input,
    )


def test_cleanup_is_explicit_not_fallback(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    with patch(
        "agent_workflow.cli_handlers.benchmark.cleanup_benchmark",
        return_value={"removed": 3},
    ) as call:
        assert handle_benchmark_command(settings, _args("cleanup")) == {"removed": 3}
    call.assert_called_once_with(settings, "run-1", remove_worktrees=False)

    with pytest.raises(WorkflowError, match="unhandled benchmark command"):
        handle_benchmark_command(settings, _args("unknown"))
