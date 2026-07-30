from __future__ import annotations

import pytest

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.executors import prepare_executor


@pytest.mark.parametrize("effort", ["low", "medium", "high"])
def test_codex_plan_is_luna_and_passes_supported_effort(effort: str) -> None:
    plan = prepare_executor(defaults(), "codex", None, structured=True, reasoning_effort=effort)
    assert plan.model == "gpt-5.6-luna"
    assert plan.reasoning_effort == effort
    argv = list(plan.argv)
    assert ["-c", f"model_reasoning_effort={effort}"] == argv[
        argv.index("-c") : argv.index("-c") + 2
    ]


@pytest.mark.parametrize(
    "command",
    [
        ["codex", "exec", "--model", "gpt-5.4-mini", "-"],
        ["codex", "exec", "-c", "model=gpt-5.4-mini", "-"],
        ["codex", "exec", "-c", "model_reasoning_effort=invalid", "-"],
    ],
)
def test_codex_bypasses_fail_before_launch(command: list[str]) -> None:
    with pytest.raises(WorkflowError):
        prepare_executor(defaults(), None, command, structured=True)


def test_explicit_non_codex_command_remains_manual() -> None:
    plan = prepare_executor(defaults(), None, ["sh", "-c", "exit 0"], structured=True)
    assert plan.name is None
    assert plan.reasoning_effort is None


def test_interactive_explicit_codex_command_retains_model_and_effort() -> None:
    plan = prepare_executor(
        defaults(),
        None,
        [
            "codex",
            "exec",
            "--model",
            "gpt-5.6-luna",
            "-c",
            "model_reasoning_effort=high",
            "-",
        ],
        interactive=True,
    )
    assert list(plan.argv).count("gpt-5.6-luna") == 1
    assert ["-c", "model_reasoning_effort=high"] == list(plan.argv)[
        list(plan.argv).index("-c") : list(plan.argv).index("-c") + 2
    ]
