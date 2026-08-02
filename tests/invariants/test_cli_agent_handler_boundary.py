from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

from agent_workflow.cli_handlers.agent import handle_agent_command
from agent_workflow.config import defaults


def _args(command: str, **values: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "agent_command": command,
        "session_id": "session-1",
        "workdir": Path("/tmp/work"),
        "prompt": Path("prompt.md"),
        "actor": "operator",
        "summary": "done",
        "ticket": "T-1",
        "pack": "pack-1",
        "retry_of": "session-0",
        "agent_class": "implementation",
        "tag": ["python"],
        "file": ["src/example.py"],
    }
    defaults.update(values)
    return argparse.Namespace(**defaults)


def test_context_dispatches_without_transforming_result(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    expected = {"schema": "agent-workflow/agent-context/v1"}
    with patch("agent_workflow.cli_handlers.agent.read_agent_context", return_value=expected) as call:
        assert handle_agent_command(settings, _args("context")) is expected
    call.assert_called_once_with(settings, "session-1")


def test_task_complete_preserves_all_arguments(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    with patch("agent_workflow.cli_handlers.agent.complete_agent_task", return_value={}) as call:
        handle_agent_command(settings, _args("task-complete"))
    call.assert_called_once_with(
        settings,
        "session-1",
        actor="operator",
        summary="done",
        tags=["python"],
        files=["src/example.py"],
    )


def test_candidates_preserves_ranking_filters(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    with patch("agent_workflow.cli_handlers.agent.reuse_candidates", return_value=[]) as call:
        handle_agent_command(settings, _args("candidates"))
    call.assert_called_once_with(
        settings,
        workdir=Path("/tmp/work"),
        ticket_id="T-1",
        pack_id="pack-1",
        retry_of="session-0",
        agent_class="implementation",
        tags=["python"],
    )


def test_reuse_preserves_assignment_authority_fields(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    with patch("agent_workflow.cli_handlers.agent.reuse_agent", return_value={}) as call:
        handle_agent_command(settings, _args("reuse"))
    call.assert_called_once_with(
        settings,
        "session-1",
        prompt_path=Path("prompt.md"),
        actor="operator",
        ticket_id="T-1",
        pack_id="pack-1",
        retry_of="session-0",
        tags=["python"],
    )


def test_auto_reuse_preserves_exact_match_inputs(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    with patch("agent_workflow.cli_handlers.agent.auto_reuse_agent", return_value={}) as call:
        handle_agent_command(settings, _args("auto-reuse"))
    call.assert_called_once_with(
        settings,
        workdir=Path("/tmp/work"),
        prompt_path=Path("prompt.md"),
        actor="operator",
        ticket_id="T-1",
        pack_id="pack-1",
        retry_of="session-0",
        agent_class="implementation",
        tags=["python"],
    )
