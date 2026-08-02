from __future__ import annotations

from pathlib import Path
from unittest.mock import ANY, patch

import pytest

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.session_control import (
    _child_lifecycle_control,
    acknowledge,
    kill,
    messages,
    progress,
    steer,
    wait_for_message,
)


def _settings(tmp_path: Path):
    settings = defaults(tmp_path / "config.toml")
    object.__setattr__(settings, "state_root", tmp_path / "state")
    return settings


def test_child_lifecycle_controls_fail_closed_when_bridge_is_required() -> None:
    with (
        patch("agent_workflow.session_control.bridge_available", return_value=False),
        patch("agent_workflow.session_control.bridge_required", return_value=True),
    ):
        assert _child_lifecycle_control("session-1") == {
            "outcome": "unavailable",
            "reason": "lifecycle controls are host-owned; exit the child normally",
        }


def test_steer_persists_before_delivery_and_preserves_delivery_evidence(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    message = {"event_id": "msg-1", "sequence": 1}
    delivery = {"event_id": "delivery-1", "outcome": "queued"}
    with (
        patch("agent_workflow.session_control._active_run"),
        patch("agent_workflow.session_control._append_control_message", return_value=message) as append,
        patch("agent_workflow.session_control.queue_request", return_value=delivery) as queue,
        patch("agent_workflow.session_control.run_dir", return_value=tmp_path / "run"),
    ):
        result = steer(settings, "session-1", actor="parent", content="inspect")
    append.assert_called_once()
    queue.assert_called_once_with(tmp_path / "run", message)
    assert result == {
        "event_id": "msg-1",
        "sequence": 1,
        "delivery_outcome": "queued",
        "delivery_event_id": "delivery-1",
    }


def test_progress_uses_child_bridge_without_touching_host_state(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    expected = {"outcome": "recorded"}
    with (
        patch("agent_workflow.session_control.bridge_available", return_value=True),
        patch("agent_workflow.session_control.write_control_intent", return_value=expected) as intent,
        patch("agent_workflow.session_control._active_run") as active,
    ):
        result = progress(settings, "session-1", actor="child", content="working")
    assert result is expected
    intent.assert_called_once_with(
        session_id="session-1", kind="progress", actor="child", content="working"
    )
    active.assert_not_called()


def test_acknowledgement_rejects_invalid_outcome_before_side_effects(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with pytest.raises(WorkflowError, match="applied or rejected"):
        acknowledge(
            settings,
            "session-1",
            actor="child",
            content="done",
            correlation_id="msg-1",
            outcome="ignored",
        )


def test_message_replay_and_wait_preserve_cursor_and_wakeup_channel(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    run = tmp_path / "run"
    rows = [{"sequence": 3}]
    with (
        patch("agent_workflow.session_control.read_status"),
        patch("agent_workflow.session_control.run_dir", return_value=run),
        patch("agent_workflow.session_control.replay_messages", return_value=rows) as replay,
    ):
        assert messages(settings, "session-1", after_sequence=2) is rows
    replay.assert_called_once_with(run, after_sequence=2)

    with (
        patch("agent_workflow.session_control.read_status"),
        patch("agent_workflow.session_control.run_dir", return_value=run),
        patch("agent_workflow.session_control.tmux.wakeup_channel", return_value="wake"),
        patch("agent_workflow.session_control.wait_for_messages", return_value=rows) as wait,
    ):
        assert wait_for_message(
            settings, "session-1", after_sequence=2, timeout_seconds=1.5
        ) is rows
    wait.assert_called_once_with(
        run,
        after_sequence=2,
        timeout_seconds=1.5,
        wakeup_channel="wake",
        wait_for_wakeup=ANY,
    )


def test_kill_returns_terminal_status_without_rewriting_it(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    terminal = {"status": "completed", "tmux_session": "session-1"}
    with (
        patch("agent_workflow.session_control._child_lifecycle_control", return_value=None),
        patch("agent_workflow.session_control.read_status", side_effect=[terminal, terminal]),
        patch("agent_workflow.session_control.tmux.session_exists", return_value=False),
        patch("agent_workflow.session_control.update_status") as update,
    ):
        assert kill(settings, "session-1") is terminal
    update.assert_not_called()
