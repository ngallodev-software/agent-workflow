from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import call, patch

from agent_workflow.cli_handlers.session import handle_session_command
from agent_workflow.config import defaults
from agent_workflow.errors import InteractiveCapacityError, WorkflowError


def _args(command: str, **values: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "command": command,
        "json": False,
        "session_id": "session-1",
        "session_ids": ["session-1"],
        "all_verified": False,
        "verified": True,
        "dry_run": False,
        "reason": "operator reason",
        "capture": -1,
        "lines": 20,
        "actor": "operator",
        "content": "message",
        "correlation_id": "corr-1",
        "outcome": "acknowledged",
        "after": 3,
        "timeout": 10.0,
        "grace_seconds": 4.0,
        "new_session": "session-2",
        "revision": "abc123",
        "acknowledge": "I understand",
        "interactive": True,
        "structured": False,
        "pane_limit_action": "cancel",
        "workdir": Path("/tmp/work"),
        "prompt": Path("prompt.md"),
        "executor": "codex",
        "agent_name": "worker",
        "agent_class": "implementation",
        "model": "gpt-test",
        "reasoning_effort": "medium",
        "allow_no_go_model": False,
        "explicit_command": None,
        "ticket": "T-1",
        "tier": "worker",
        "pack": "pack-1",
        "job": Path("job.json"),
        "allow_dirty": False,
        "prerequisites": ["T-0"],
        "evaluation": Path("evaluation.yaml"),
    }
    base.update(values)
    return argparse.Namespace(**base)


def test_launch_preserves_authority_arguments(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    args = _args("launch")
    expected = {"session_id": "session-1"}
    with patch(
        "agent_workflow.cli_handlers.session.launch_session",
        return_value=expected,
    ) as launch:
        result, complete = handle_session_command(settings, args)
    assert result is expected
    assert complete is False
    launch.assert_called_once_with(
        settings,
        session_id="session-1",
        workdir=Path("/tmp/work"),
        prompt_path=Path("prompt.md"),
        executor="codex",
        agent_name="worker",
        agent_class="implementation",
        model="gpt-test",
        reasoning_effort="medium",
        allow_no_go_model=False,
        explicit_command=None,
        ticket_id="T-1",
        tier="worker",
        pack_id="pack-1",
        job_path=Path("job.json"),
        allow_dirty=False,
        structured=False,
        interactive=True,
        prerequisite_ids=["T-0"],
        evaluation_path=Path("evaluation.yaml"),
    )


def test_launch_noninteractive_capacity_fallback_is_evidence_safe(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    args = _args("launch", pane_limit_action="non-interactive")
    capacity = InteractiveCapacityError(count=4, maximum=3, idle_sessions=[])
    with patch(
        "agent_workflow.cli_handlers.session.launch_session",
        side_effect=[capacity, {"session_id": "session-1"}],
    ) as launch:
        result, complete = handle_session_command(settings, args)
    assert result == {"session_id": "session-1"}
    assert complete is False
    assert launch.call_count == 2
    assert launch.call_args_list[0].kwargs["interactive"] is True
    assert launch.call_args_list[0].kwargs["structured"] is False
    assert launch.call_args_list[1].kwargs["interactive"] is False
    assert launch.call_args_list[1].kwargs["structured"] is True


def test_list_falls_back_to_durable_status_when_observation_fails(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    durable = {"session_id": "session-1", "status": "running"}
    with (
        patch("agent_workflow.cli_handlers.session.list_statuses", return_value=[durable]),
        patch(
            "agent_workflow.cli_handlers.session.observe",
            side_effect=WorkflowError("tmux unavailable"),
        ),
        patch("agent_workflow.cli_handlers.session.print_table") as render,
    ):
        result, complete = handle_session_command(settings, _args("list"))
    assert result is None
    assert complete is True
    assert render.call_args.args[0] == [durable]


def test_message_commands_preserve_cursor_and_correlation_fields(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    with (
        patch("agent_workflow.cli_handlers.session.acknowledge_message", return_value={}) as ack,
        patch("agent_workflow.cli_handlers.session.wait_for_message", return_value={}) as watch,
    ):
        handle_session_command(settings, _args("ack"))
        handle_session_command(settings, _args("watch"))
    ack.assert_called_once_with(
        settings,
        "session-1",
        actor="operator",
        content="message",
        correlation_id="corr-1",
        outcome="acknowledged",
    )
    watch.assert_called_once_with(
        settings,
        "session-1",
        after_sequence=3,
        timeout_seconds=10.0,
    )


def test_lifecycle_and_force_accept_preserve_audit_inputs(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    with (
        patch("agent_workflow.cli_handlers.session.record_lifecycle", return_value={}) as lifecycle,
        patch("agent_workflow.cli_handlers.session.force_accept", return_value={}) as force,
    ):
        handle_session_command(settings, _args("accept"))
        handle_session_command(
            settings,
            _args("force-accept"),
            argv=["force-accept", "session-1", "--actor", "operator"],
        )
    lifecycle.assert_called_once_with(
        settings,
        "session-1",
        action="accepted",
        actor="operator",
        reason="operator reason",
        revision="abc123",
    )
    force.assert_called_once_with(
        settings,
        "session-1",
        actor="operator",
        reason="operator reason",
        acknowledgement="I understand",
        command=[
            "agent-workflow",
            "force-accept",
            "session-1",
            "--actor",
            "operator",
        ],
    )


def test_attach_verifies_durable_status_before_tmux(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    with (
        patch("agent_workflow.cli_handlers.session.read_status") as read,
        patch("agent_workflow.cli_handlers.session.attach_tmux") as attach,
    ):
        result, complete = handle_session_command(settings, _args("attach"))
    assert result is None
    assert complete is True
    assert [read.call_args, attach.call_args] == [call(settings, "session-1"), call("session-1")]
