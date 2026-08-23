from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from agent_workflow.completion import (
    completion_revision_errors,
    substantive_completion_errors,
    validate_completion_repository_closeout,
)
from agent_workflow.contracts import validate_instance, validate_ticket_identity
from agent_workflow.errors import WorkflowError
from agent_workflow.git import snapshot
from agent_workflow.steering import append_delivery_event, replay_delivery_events
from agent_workflow.repository_closeout import create_repository_closeout


def _completion(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "agent-workflow/completion/v1",
        "session_id": "run-1",
        "ticket_id": "T-1",
        "pack_id": "pack-1",
        "result": "completed",
        "base_revision": "a" * 40,
        "head_revision": "b" * 40,
        "changed_files": ["src/example.py"],
        "criteria": [
            {
                "id": "criterion-1",
                "result": "pass",
                "evidence": ["tests/invariants/test_example.py passed"],
            }
        ],
        "commands": [
            {
                "argv": ["python3", "-m", "pytest", "-q"],
                "cwd": ".",
                "exit_code": 0,
                "receipt": "12 passed",
            }
        ],
        "unresolved": [],
    }
    value.update(overrides)
    return value


def test_substantive_completion_rejects_empty_schema_valid_success() -> None:
    value = _completion(
        base_revision=None,
        head_revision=None,
        criteria=[],
        commands=[],
    )
    errors = substantive_completion_errors(
        value, session_id="run-1", ticket_id="T-1", pack_id="pack-1"
    )
    assert "completed result requires substantive base_revision" in errors
    assert "completed result requires substantive head_revision" in errors
    assert "completed result requires at least one acceptance criterion" in errors
    assert "completed result requires at least one command receipt" in errors


def test_completion_schema_rejects_string_criteria_before_collection() -> None:
    value = _completion(criteria=["criterion text"])
    with pytest.raises(WorkflowError, match="invalid artifact"):
        validate_instance(value, "agent-workflow/completion/v1")


def test_completion_schema_requires_criterion_evidence() -> None:
    value = _completion(criteria=[{"id": "criterion-1", "result": "pass"}])
    with pytest.raises(WorkflowError, match="invalid artifact"):
        validate_instance(value, "agent-workflow/completion/v1")


def test_completion_schema_rejects_command_evidence_instead_of_receipt() -> None:
    value = _completion(
        commands=[
            {
                "argv": ["pytest", "-q"],
                "cwd": "/worktree",
                "exit_code": 0,
                "evidence": "1 passed",
            }
        ]
    )
    with pytest.raises(WorkflowError, match="invalid artifact"):
        validate_instance(value, "agent-workflow/completion/v1")


def test_review_ticket_identity_requires_explicit_match_or_omission() -> None:
    omitted = _completion(ticket_id=None)
    assert substantive_completion_errors(
        omitted, session_id="run-1", ticket_id=None, pack_id="pack-1"
    ) == []
    mismatch = _completion(ticket_id="REVIEW-FORGED")
    assert substantive_completion_errors(
        mismatch, session_id="run-1", ticket_id=None, pack_id="pack-1"
    ) == ["completion ticket_id does not match launch contract"]


def test_substantive_completion_accepts_failure_with_real_unresolved_evidence() -> None:
    value = _completion(
        result="failed",
        base_revision=None,
        head_revision=None,
        criteria=[
            {
                "id": "integration-suite",
                "result": "fail",
                "evidence": ["tests failed before MCP startup"],
            }
        ],
        commands=[
            {
                "argv": ["python3", "-m", "pytest", "-q"],
                "cwd": ".",
                "exit_code": 1,
                "receipt": "2 failed, 10 passed",
            }
        ],
        unresolved=["MCP dependency unavailable in the configured environment"],
    )
    assert substantive_completion_errors(
        value, session_id="run-1", ticket_id="T-1", pack_id="pack-1"
    ) == []


def test_substantive_completion_preserves_failed_command_as_non_success() -> None:
    value = _completion(
        commands=[
            {
                "argv": ["python3", "-m", "pytest"],
                "cwd": ".",
                "exit_code": 1,
                "receipt": "1 failed",
            }
        ]
    )
    errors = substantive_completion_errors(
        value, session_id="run-1", ticket_id="T-1", pack_id="pack-1"
    )
    assert "completed result cannot hide commands[0] exit_code 1" in errors


def test_substantive_completion_rejects_missing_command_exit_code() -> None:
    value = _completion(
        commands=[
            {
                "argv": ["python3", "-m", "pytest"],
                "cwd": ".",
                "receipt": "exit code unavailable",
            }
        ]
    )
    errors = substantive_completion_errors(
        value, session_id="run-1", ticket_id="T-1", pack_id="pack-1"
    )
    assert "commands[0].exit_code is missing or invalid" in errors


def test_completion_repository_closeout_binds_digest_root_and_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "tests@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Tests"], check=True)
    (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
    head = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    handoff = repo / ".agent-workflow-handoff"
    handoff.mkdir()
    receipt_path = handoff / "repository-closeout.json"
    create_repository_closeout(
        repo,
        output=receipt_path,
        operational_trees=(".agent-workflow-handoff/",),
    )
    import hashlib

    digest = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    value = _completion(
        base_revision=head,
        head_revision=head,
        changed_files=[],
        repository_closeout={"path": "repository-closeout.json", "sha256": digest},
    )
    summary = validate_completion_repository_closeout(
        value,
        handoff=handoff,
        expected_worktree=repo,
    )
    assert summary is not None
    assert summary["local_head"] == head
    assert summary["claims"]["pushed"] is False

    value["repository_closeout"] = {
        "path": "repository-closeout.json",
        "sha256": "0" * 64,
    }
    with pytest.raises(WorkflowError, match="digest does not match"):
        validate_completion_repository_closeout(
            value,
            handoff=handoff,
            expected_worktree=repo,
        )


def test_acknowledgement_supersedes_unsupported_delivery_but_expiry_is_immutable(
    tmp_path: Path,
) -> None:
    common = {
        "session_id": "run-1",
        "message_sha256": "sha256:" + "a" * 64,
        "adapter": "unsupported",
        "attempt": 0,
        "executor": "fake-agent",
    }
    correlation = "11111111-1111-4111-8111-111111111111"
    append_delivery_event(
        tmp_path,
        correlation_id=correlation,
        outcome="unsupported",
        reason="no configured adapter",
        **common,
    )
    applied = append_delivery_event(
        tmp_path,
        correlation_id=correlation,
        outcome="applied",
        reason="child acknowledged through bridge",
        **common,
    )
    assert applied["outcome"] == "applied"
    assert [event["outcome"] for event in replay_delivery_events(tmp_path)] == [
        "unsupported", "applied"
    ]
    duplicate = append_delivery_event(
        tmp_path,
        correlation_id=correlation,
        outcome="applied",
        reason="duplicate acknowledgement",
        **common,
    )
    assert duplicate["event_id"] == applied["event_id"]
    assert len(replay_delivery_events(tmp_path)) == 2

    expired_id = "22222222-2222-4222-8222-222222222222"
    expired = append_delivery_event(
        tmp_path,
        correlation_id=expired_id,
        outcome="expired",
        reason="deadline elapsed",
        **common,
    )
    later = append_delivery_event(
        tmp_path,
        correlation_id=expired_id,
        outcome="applied",
        reason="too late",
        **common,
    )
    assert later["event_id"] == expired["event_id"]
    assert later["outcome"] == "expired"


def test_observe_tracks_executor_event_growth_independently(
    tmp_path: Path, monkeypatch,
) -> None:
    import time
    from dataclasses import replace

    from agent_workflow import sessions
    from agent_workflow.config import defaults
    from agent_workflow.tmux import PaneInfo

    run = tmp_path / "run"
    run.mkdir()
    log = run / "output.log"
    heartbeat = run / "heartbeat.json"
    executor_events = run / "executor-events.jsonl"
    lifecycle_events = run / "events.jsonl"
    log.write_text("", encoding="utf-8")
    heartbeat.write_text("{}", encoding="utf-8")
    executor_events.write_text('{"type":"progress"}\n', encoding="utf-8")
    lifecycle_events.write_text(
        '{"schema":"agent-workflow/lifecycle-event/v1"}\n', encoding="utf-8"
    )
    old = time.time() - 120
    os.utime(log, (old, old))
    os.utime(heartbeat, (old, old))

    status = {
        "session_id": "observe-run",
        "status": "running",
        "log_path": str(log),
        "tmux_session": "observe-run",
        "tmux_target": "observe-run",
        "tmux_mode": "dedicated_session",
        "interactive": False,
    }
    monkeypatch.setattr(sessions, "read_status", lambda _settings, _session: status)
    monkeypatch.setattr(
        sessions,
        "update_status",
        lambda _settings, _session, **changes: {
            **status,
            **{key: value for key, value in changes.items() if not key.startswith("_")},
            "projection_source": changes.get("_projection_source"),
            "projection_freshness": changes.get("_projection_freshness"),
            "projection_authority": "cache",
        },
    )
    monkeypatch.setattr(sessions.tmux, "session_exists", lambda _target: True)
    monkeypatch.setattr(
        sessions.tmux,
        "resolve_status_pane",
        lambda _status: PaneInfo(pid=123, dead=False, command="python", pane_id="%1"),
    )
    settings = replace(defaults(), stall_minutes=1)

    fresh = sessions.observe(settings, "observe-run")
    assert fresh["observed_state"] == "running"
    assert fresh["seconds_since_log_growth"] >= 60
    assert fresh["seconds_since_heartbeat"] >= 60
    assert fresh["seconds_since_executor_event_growth"] < 5
    assert fresh["signals"]["executor_events_exist"] is True

    os.utime(executor_events, (old, old))
    stale = sessions.observe(settings, "observe-run")
    assert stale["observed_state"] == "possibly_stalled"
    assert stale["failure_category"] == "stalled"
    assert stale["safe_actions"][-1] == "agent-workflow interrupt observe-run"


def test_approved_review_requires_green_evidence_and_no_unresolved() -> None:
    value = _completion(
        review_disposition="approved",
        criteria=[
            {
                "id": "security",
                "result": "not_verified",
                "evidence": ["privacy test timed out"],
            }
        ],
        unresolved=["privacy boundary not verified"],
    )
    errors = substantive_completion_errors(
        value, session_id="run-1", ticket_id="T-1", pack_id="pack-1"
    )
    assert "approved review requires criteria[0] to be pass" in errors
    assert "approved review disposition requires an empty unresolved list" in errors


def test_review_schema_rejects_disposition_as_result() -> None:
    value = _completion(result="changes_requested")
    with pytest.raises(WorkflowError, match="invalid artifact"):
        validate_instance(value, "agent-workflow/completion/v1")


