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
    read_events,
    record_health_sample,
    record_permission_event,
    write_process_result,
)
from agent_workflow.supervisor import SupervisorOptions, supervise_once
from agent_workflow.util import atomic_write_json


def _running_status(run: Path, agent_run_id: str = "run-1") -> None:
    atomic_write_json(
        run / "status.json",
        {
            "schema": "agent-workflow/agent-run-status/v1",
            "agent_run_id": agent_run_id,
            "status": "running",
            "worker_mode": "headless",
            "worker_id": f"worker-{agent_run_id}",
            "runner_pid": None,
            "executor_pid": None,
            "started_at": None,
            "completed_at": None,
            "exit_code": None,
            "failure_category": None,
            "message": None,
            "updated_at": "2026-08-24T00:00:00+00:00",
        },
    )


def test_permission_journal_deduplicates_identical_evidence(tmp_path: Path) -> None:
    first = record_permission_event(
        tmp_path,
        agent_run_id="run-1",
        state="pending",
        source="executor_stderr",
        evidence_sha256="a" * 64,
    )
    assert first is not None
    assert record_permission_event(
        tmp_path,
        agent_run_id="run-1",
        state="pending",
        source="executor_stderr",
        evidence_sha256="a" * 64,
    ) is None

    second = record_permission_event(
        tmp_path,
        agent_run_id="run-1",
        state="denied",
        source="executor_stderr",
        evidence_sha256="b" * 64,
    )
    assert second is not None
    assert [event["state"] for event in read_events(tmp_path / "permission-events.jsonl")] == [
        "pending",
        "denied",
    ]


def test_health_sample_distinguishes_process_liveness_from_semantic_progress(
    tmp_path: Path,
) -> None:
    output = tmp_path / "output.log"
    output.write_text("started\n", encoding="utf-8")
    old = time.time() - 120
    os.utime(output, (old, old))

    sample = record_health_sample(
        tmp_path,
        agent_run_id="run-1",
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
    _running_status(run)
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
            "latest_health": {"executor": {"alive": True}},
        },
    )
    calls: list[str] = []

    def fake_steer(_settings, agent_run_id, *, actor, content):
        calls.append(agent_run_id)
        return {"message_id": "message-1", "delivery_outcome": "queued"}

    monkeypatch.setattr(supervisor, "steer", fake_steer)
    options = SupervisorOptions.from_settings(settings)

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
    _running_status(run)

    monkeypatch.setattr(supervisor, "record_health_sample", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        supervisor,
        "observe",
        lambda *_args, **_kwargs: {
            "observed_state": "possibly_stalled",
            "failure_category": "stalled",
            "seconds_since_semantic_progress": 999,
            "latest_health": {"executor": {"alive": True}},
        },
    )
    calls = 0

    def failing_steer(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise WorkflowError("delivery unavailable")

    monkeypatch.setattr(supervisor, "steer", failing_steer)
    options = SupervisorOptions.from_settings(settings)

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
    _running_status(run)

    monkeypatch.setattr(supervisor, "record_health_sample", lambda *args, **kwargs: {})
    observation = {
        "observed_state": "possibly_stalled",
        "failure_category": "stalled",
        "seconds_since_semantic_progress": 999,
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
    options = SupervisorOptions.from_settings(settings)

    report = supervise_once(settings, options=options)

    details = report["runs"][0]["remediations"][0]["details"]
    assert details["verification"] == "authoritative_post_action_observation"
    assert details["post_action_observation"]["observed_state"] == "possibly_stalled"
    assert details["post_action_observation"]["last_event"] == {"event": "steer-delivered"}


def test_health_journals_validate_on_read(tmp_path: Path) -> None:
    record_permission_event(
        tmp_path,
        agent_run_id="run-1",
        state="pending",
        source="executor_stderr",
        evidence_sha256="c" * 64,
    )
    journal = tmp_path / "permission-events.jsonl"
    value = json.loads(journal.read_text(encoding="utf-8"))
    value["state"] = "not-a-valid-state"
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
