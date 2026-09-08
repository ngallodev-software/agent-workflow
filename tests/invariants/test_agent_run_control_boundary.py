from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.agent_run_control import (
    acknowledge,
    interrupt,
    messages,
    progress,
    steer,
    terminate,
    wait_for_message,
)
from agent_workflow.agent_identity import can_retire_prepared, retire_external_agent


def _settings(tmp_path: Path):
    settings = defaults(tmp_path / "config.toml")
    object.__setattr__(settings, "state_root", tmp_path / "state")
    return settings


def test_steer_persists_before_delivery_and_preserves_delivery_evidence(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    message = {"event_id": "msg-1", "sequence": 1}
    delivery = {"event_id": "delivery-1", "outcome": "queued"}
    with (
        patch("agent_workflow.agent_run_control._active_run"),
        patch("agent_workflow.agent_run_control._append_control_message", return_value=message) as append,
        patch("agent_workflow.agent_run_control.queue_request", return_value=delivery) as queue,
        patch("agent_workflow.agent_run_control.run_dir", return_value=tmp_path / "run"),
    ):
        result = steer(settings, "run-1", actor="parent", content="inspect")
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
        patch("agent_workflow.agent_run_control.bridge_available", return_value=True),
        patch("agent_workflow.agent_run_control.write_control_intent", return_value=expected) as intent,
        patch("agent_workflow.agent_run_control._active_run") as active,
    ):
        result = progress(settings, "run-1", actor="child", content="working")
    assert result is expected
    intent.assert_called_once_with(
        agent_run_id="run-1", kind="progress", actor="child", content="working"
    )
    active.assert_not_called()


def test_acknowledgement_rejects_invalid_outcome_before_side_effects(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with pytest.raises(WorkflowError, match="applied or rejected"):
        acknowledge(
            settings,
            "run-1",
            actor="child",
            content="done",
            correlation_id="msg-1",
            outcome="ignored",
        )


def test_message_replay_and_wait_use_durable_polling_only(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    run = tmp_path / "run"
    rows = [{"sequence": 3}]
    with (
        patch("agent_workflow.agent_run_control.read_status"),
        patch("agent_workflow.agent_run_control.run_dir", return_value=run),
        patch("agent_workflow.agent_run_control.replay_messages", return_value=rows) as replay,
    ):
        assert messages(settings, "run-1", after_sequence=2) is rows
    replay.assert_called_once_with(run, after_sequence=2)

    with (
        patch("agent_workflow.agent_run_control.read_status"),
        patch("agent_workflow.agent_run_control.run_dir", return_value=run),
        patch("agent_workflow.agent_run_control.wait_for_messages", return_value=rows) as wait,
    ):
        assert wait_for_message(settings, "run-1", after_sequence=2, timeout_seconds=1.5) is rows
    wait.assert_called_once_with(run, after_sequence=2, timeout_seconds=1.5)


def test_external_lifecycle_control_is_explicitly_unavailable(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    external = {"status": "running", "worker_mode": "external"}
    with (
        patch("agent_workflow.agent_run_control._child_lifecycle_control", return_value=None),
        patch("agent_workflow.agent_run_control.synchronize_projection", return_value=external),
        patch("agent_workflow.agent_run_control.authoritative_execution_status", return_value="running"),
        patch("agent_workflow.agent_run_control.transition_execution") as transition,
    ):
        interrupted = interrupt(settings, "run-1")
        terminated = terminate(settings, "run-1", grace_seconds=0)
    assert interrupted["outcome"] == "unavailable"
    assert terminated["outcome"] == "unavailable"
    transition.assert_not_called()


def test_terminal_status_is_returned_without_lifecycle_rewrite(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    terminal = {"status": "completed", "worker_mode": "headless"}
    with (
        patch("agent_workflow.agent_run_control._child_lifecycle_control", return_value=None),
        patch("agent_workflow.agent_run_control.synchronize_projection", return_value=terminal),
        patch("agent_workflow.agent_run_control.authoritative_execution_status", return_value="completed"),
        patch("agent_workflow.agent_run_control.transition_execution") as transition,
    ):
        assert interrupt(settings, "run-1") is terminal
        assert terminate(settings, "run-1", 0) is terminal
    transition.assert_not_called()


def test_external_retirement_requires_unbound_prepared_run_and_releases_name(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    status = {"agent_run_id": "run-1", "agent_name": "worker", "worker_mode": "external"}
    retired = {**status, "status": "retired", "retirement_authority": {"action": "retire"}}
    with (
        patch("agent_workflow.agent_run_control._child_lifecycle_control", return_value=None),
        patch("agent_workflow.run_lifecycle.synchronize_projection", return_value=status),
        patch("agent_workflow.agent_identity.authoritative_execution_status", return_value="prepared"),
        patch("agent_workflow.external_bindings.status", return_value={"bound": False, "generation": 2}),
        patch("agent_workflow.run_lifecycle.transition_execution", return_value=retired) as transition,
        patch("agent_workflow.agent_identity.release_agent_name") as release,
        patch("agent_workflow.agent_identity.run_dir", return_value=tmp_path / "run"),
    ):
        result = retire_external_agent(settings, agent_run_id="run-1", reason="abandoned")
    assert result["outcome"] == "retired"
    transition.assert_called_once()
    release.assert_called_once_with(settings, agent_name="worker", agent_run_id="run-1")


def test_external_retirement_refuses_bound_and_non_external_runs(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    with patch("agent_workflow.agent_identity.authoritative_execution_status", return_value="prepared"):
        assert not can_retire_prepared(
            settings, {"agent_run_id": "run-1", "worker_mode": "headless"}
        )
