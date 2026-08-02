from __future__ import annotations

import json
import os
import time
from dataclasses import replace
from pathlib import Path

import pytest

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.health import (
    last_event,
    read_events,
    write_process_result,
    record_health_sample,
    record_terminal_capture,
)
from agent_workflow.supervisor import SupervisorOptions, supervise_once
from agent_workflow.util import atomic_write_json


def test_terminal_capture_is_change_driven_and_tracks_permission_transitions(
    tmp_path: Path,
) -> None:
    first = record_terminal_capture(
        tmp_path,
        session_id="run-1",
        pane_id="%1",
        content="Approval required. Allow this command?",
    )
    assert first is not None
    assert first["stored"] is True
    assert record_terminal_capture(
        tmp_path,
        session_id="run-1",
        pane_id="%1",
        content="Approval required. Allow this command?",
    ) is None
    pending = last_event(tmp_path / "permission-events.jsonl")
    assert pending is not None
    assert pending["state"] == "pending"

    record_terminal_capture(
        tmp_path,
        session_id="run-1",
        pane_id="%1",
        content="Command completed successfully.",
    )
    cleared = last_event(tmp_path / "permission-events.jsonl")
    assert cleared is not None
    assert cleared["state"] == "cleared"
    assert len(read_events(tmp_path / "terminal-events.jsonl")) == 2


def test_health_sample_distinguishes_process_liveness_from_semantic_progress(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output.log"
    output.write_text("started\n", encoding="utf-8")
    old = time.time() - 120
    os.utime(output, (old, old))

    sample = record_health_sample(
        tmp_path,
        session_id="run-1",
        runner_pid=os.getpid(),
        executor_pid=os.getpid(),
    )
    assert sample["runner"]["alive"] is True
    assert sample["executor"]["alive"] is True
    assert sample["seconds_since_semantic_progress"] >= 100
    assert sample["last_semantic_progress_source"] == "output"


def test_supervisor_sends_only_one_bounded_stall_probe(
    tmp_path: Path, monkeypatch
) -> None:
    from agent_workflow import supervisor

    settings = replace(
        defaults(tmp_path / "missing-config.toml"),
        state_root=tmp_path / "state",
        supervisor_max_remediation_attempts=1,
    )
    run = settings.state_root / "runs" / "run-1"
    run.mkdir(parents=True)
    atomic_write_json(
        run / "status.json",
        {
            "schema": "agent-workflow/session-status/v2",
            "session_id": "run-1",
            "status": "running",
            "log_path": str(run / "output.log"),
            "interactive": False,
            "executor_interactive": False,
        },
    )
    (run / "output.log").write_text("", encoding="utf-8")

    monkeypatch.setattr(supervisor, "record_health_sample", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        supervisor,
        "observe",
        lambda *_args, **_kwargs: {
            "observed_state": "possibly_stalled",
            "failure_category": "stalled",
            "permission_state": None,
            "seconds_since_semantic_progress": 999,
            "tmux_alive": True,
            "latest_health": {"executor": {"alive": True}},
        },
    )
    calls: list[str] = []

    def fake_steer(_settings, session_id, *, actor, content):
        calls.append(session_id)
        return {"message_id": "message-1", "delivery_outcome": "queued"}

    monkeypatch.setattr(supervisor, "steer", fake_steer)
    options = SupervisorOptions.from_settings(settings, capture_interactive=False)

    first = supervise_once(settings, options=options)
    second = supervise_once(settings, options=options)

    assert first["runs"][0]["remediations"][0]["action"] == "request_progress_probe"
    assert second["runs"][0]["remediations"] == []
    assert calls == ["run-1"]
    events = read_events(run / "remediation-events.jsonl")
    assert [event["rule_id"] for event in events] == ["SAFE-PROBE-STALL-v1"]


def test_failed_stall_probe_consumes_its_bounded_attempt(tmp_path: Path, monkeypatch) -> None:
    from agent_workflow import supervisor

    settings = replace(
        defaults(tmp_path / "missing-config.toml"),
        state_root=tmp_path / "state",
        supervisor_max_remediation_attempts=1,
    )
    run = settings.state_root / "runs" / "run-1"
    run.mkdir(parents=True)
    atomic_write_json(
        run / "status.json",
        {
            "schema": "agent-workflow/session-status/v2",
            "session_id": "run-1",
            "status": "running",
            "log_path": str(run / "output.log"),
            "interactive": False,
            "executor_interactive": False,
        },
    )
    monkeypatch.setattr(supervisor, "record_health_sample", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        supervisor,
        "observe",
        lambda *_args, **_kwargs: {
            "observed_state": "possibly_stalled",
            "failure_category": "stalled",
            "seconds_since_semantic_progress": 999,
            "tmux_alive": True,
            "latest_health": {"executor": {"alive": True}},
        },
    )
    calls = 0

    def failing_steer(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise WorkflowError("delivery unavailable")

    monkeypatch.setattr(supervisor, "steer", failing_steer)
    options = SupervisorOptions.from_settings(settings, capture_interactive=False)

    first = supervise_once(settings, options=options)
    second = supervise_once(settings, options=options)

    assert first["runs"][0]["remediations"][0]["outcome"] == "failed"
    assert second["runs"][0]["remediations"] == []
    assert calls == 1


def test_successful_stall_probe_records_authoritative_post_action_observation(
    tmp_path: Path, monkeypatch
) -> None:
    from agent_workflow import supervisor

    settings = replace(
        defaults(tmp_path / "missing-config.toml"),
        state_root=tmp_path / "state",
        supervisor_max_remediation_attempts=1,
    )
    run = settings.state_root / "runs" / "run-1"
    run.mkdir(parents=True)
    atomic_write_json(
        run / "status.json",
        {
            "schema": "agent-workflow/session-status/v2",
            "session_id": "run-1",
            "status": "running",
            "log_path": str(run / "output.log"),
            "interactive": False,
            "executor_interactive": False,
        },
    )
    monkeypatch.setattr(supervisor, "record_health_sample", lambda *args, **kwargs: {})
    observation = {
        "observed_state": "possibly_stalled",
        "failure_category": "stalled",
        "seconds_since_semantic_progress": 999,
        "tmux_alive": True,
        "status": "running",
        "latest_health": {"executor": {"alive": True}},
        "last_event": {"event": "steer-delivered"},
    }
    monkeypatch.setattr(supervisor, "observe", lambda *_args, **_kwargs: observation)
    monkeypatch.setattr(
        supervisor,
        "steer",
        lambda *_args, **_kwargs: {
            "message_id": "message-1",
            "delivery_outcome": "queued",
        },
    )
    options = SupervisorOptions.from_settings(settings, capture_interactive=False)

    report = supervise_once(settings, options=options)

    details = report["runs"][0]["remediations"][0]["details"]
    assert details["verification"] == "authoritative_post_action_observation"
    assert details["post_action_observation"]["observed_state"] == "possibly_stalled"
    assert details["post_action_observation"]["last_event"] == {"event": "steer-delivered"}

def test_health_journals_validate_on_read_and_terminal_capture_redacts_secrets(
    tmp_path: Path,
) -> None:
    event = record_terminal_capture(
        tmp_path,
        session_id="run-1",
        pane_id="%1",
        content="token=secret-value\x1b[31m waiting\x1b[0m",
        secret_values=("secret-value",),
    )
    assert event is not None
    assert "secret-value" not in event["content"]
    assert "\x1b" not in event["content"]

    journal = tmp_path / "terminal-events.jsonl"
    value = json.loads(journal.read_text(encoding="utf-8"))
    value["content_bytes"] = -1
    journal.write_text(json.dumps(value) + "\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="invalid"):
        read_events(journal)


def test_process_result_contract_preserves_signal_and_truncation_fields(
    tmp_path: Path,
) -> None:
    value = {
        "schema": "agent-workflow/process-result/v1",
        "argv": ["tool", "--secret", "<redacted>"],
        "resolved_executable": "/usr/bin/tool",
        "returncode": -15,
        "exit_code": None,
        "signal": 15,
        "timed_out": True,
        "cancelled": False,
        "stdout_truncated": True,
        "stderr_truncated": False,
        "stdout_bytes": 100000,
        "stderr_bytes": 0,
        "duration_seconds": 2.5,
        "error_category": "timeout",
        "runner_pid": os.getpid(),
        "executor_pid": os.getpid(),
        "recorded_at": "2026-07-30T00:00:00+00:00",
    }
    path = tmp_path / "process-result.json"
    write_process_result(path, value)
    assert json.loads(path.read_text(encoding="utf-8"))["signal"] == 15
