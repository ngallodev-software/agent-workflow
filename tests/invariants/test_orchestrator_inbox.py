from __future__ import annotations

import fcntl
import hashlib
import json
import os
import signal
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.orchestrator_inbox import (
    acknowledge_event,
    create_registry,
    event_digest,
    import_registered,
    record_action,
    read_child_registry,
    read_inbox,
    register_child,
    unregister_child,
)
from agent_workflow.orchestrator_inbox import orchestrator_dir, replay_registered
from agent_workflow.orchestrator_supervisor import watch
from agent_workflow.messages import append_message
from agent_workflow.tmux import orchestrator_wakeup_channel
from agent_workflow.sessions import launch
from agent_workflow.util import atomic_write_json, utc_now
from tests.conftest import git_repo


def _make_child(tmp_path: Path, settings, session_id: str, summary: str, monkeypatch) -> None:
    repo = tmp_path / f"repo-{session_id}"
    git_repo(repo)
    prompt = tmp_path / f"{session_id}.md"
    prompt.write_text("child\n", encoding="utf-8")
    monkeypatch.setattr("agent_workflow.tmux.session_exists", lambda *args: False)
    monkeypatch.setattr("agent_workflow.tmux.create_session", lambda *args: None)
    monkeypatch.setattr("agent_workflow.tmux.pane_info", lambda *args: None)
    launch(
        settings,
        session_id=session_id,
        workdir=repo,
        prompt_path=prompt,
        explicit_command=["true"],
        structured=True,
        interactive=False,
        allow_dirty=False,
    )
    run = settings.state_root / "runs" / session_id
    assignment_id = str(uuid.uuid4())
    now = utc_now()
    contract = json.loads((run / "launch-contract.json").read_text(encoding="utf-8"))
    atomic_write_json(
        run / "agent-context.json",
        {
            "schema": "agent-workflow/agent-context/v1",
            "session_id": session_id,
            "agent_name": None,
            "agent_class": "implementation",
            "executor": None,
            "model": None,
            "interactive": True,
            "provider_session_id": None,
            "repository_root": str(repo),
            "worktree": contract["worktree"]["path"],
            "source_revision": contract["worktree"]["source_revision"],
            "state": "idle_reusable",
            "current_assignment": None,
            "completed_assignments": [{"assignment_id": assignment_id, "summary": summary}],
            "reuse_count": 0,
            "created_at": now,
            "updated_at": now,
        },
    )
    (run / "assignments.jsonl").write_text(
        json.dumps(
            {
                "schema": "agent-workflow/assignment-event/v1", "sequence": 1,
                "timestamp": now, "event": "task_completed", "session_id": session_id,
                "assignment_id": assignment_id, "actor": "child", "ticket_id": None,
                "pack_id": None, "correlation_id": None, "summary": summary,
                "tags": [], "files": [],
            }, sort_keys=True,
        ) + "\n", encoding="utf-8",
    )
    (run / "events.jsonl").write_text(
        json.dumps(
            {
                "schema": "agent-workflow/lifecycle-event/v1", "sequence": 1,
                "timestamp": now, "dimension": "assignment", "prior": "busy",
                "new": "idle_reusable", "actor": "child", "reason": "complete",
                "receipt_refs": ["assignments.jsonl", "agent-context.json"],
            }, sort_keys=True,
        ) + "\n", encoding="utf-8",
    )
    (run / "messages.jsonl").write_text(
        json.dumps(
            {
                "schema": "agent-workflow/session-message/v1", "sequence": 1,
                "message_id": str(uuid.uuid4()), "session_id": session_id,
                "timestamp": now, "direction": "child_to_parent", "kind": "task_complete",
                "actor": "child", "content": summary,
            }, sort_keys=True,
        ) + "\n", encoding="utf-8",
    )


def test_registry_inbox_import_restart_dedup_and_terminal_retention(tmp_path: Path, monkeypatch) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "child-one", "one complete", monkeypatch)
    _make_child(tmp_path, settings, "child-two", "two complete", monkeypatch)

    create_registry(settings, "main-orchestrator")
    register_child(settings, "main-orchestrator", "child-one")
    register_child(settings, "main-orchestrator", "child-two")
    first = import_registered(settings, "main-orchestrator")
    assert first["count"] == 2
    assert [item["sequence"] for item in read_inbox(settings, "main-orchestrator")] == [1, 2]
    assert all("summary" not in item for item in read_inbox(settings, "main-orchestrator"))
    assert len(read_inbox(settings, "main-orchestrator", include_content=True)[0]["summary"]) > 0

    second = import_registered(settings, "main-orchestrator")
    assert second["count"] == 2
    assert all(item["duplicate"] for item in second["imported"])
    assert len(read_inbox(settings, "main-orchestrator")) == 2

    registry_path = settings.state_root / "orchestrators" / next(
        path.name for path in (settings.state_root / "orchestrators").iterdir()
        if path.is_dir()
    ) / "registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    registry["children"][0]["state"] = "completed"
    atomic_write_json(registry_path, registry)
    with pytest.raises(WorkflowError):
        import_registered(settings, "main-orchestrator", session_id="child-one")

    source = settings.state_root / "runs" / "child-one" / "messages.jsonl"
    assert source.is_file()
    unregister_child(settings, "main-orchestrator", "child-two", state="abandoned")
    assert source.is_file()


def test_inbox_rejects_unverified_source_claim_and_symlink(tmp_path: Path, monkeypatch) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "child-one", "one complete", monkeypatch)
    create_registry(settings, "main-orchestrator")
    register_child(settings, "main-orchestrator", "child-one")
    message = json.loads(
        (settings.state_root / "runs" / "child-one" / "messages.jsonl").read_text(encoding="utf-8")
    )
    message["session_id"] = "other-child"
    with pytest.raises(WorkflowError, match="another registered session"):
        from agent_workflow.orchestrator_inbox import import_message

        import_message(settings, "main-orchestrator", "child-one", message)

    inbox = next((settings.state_root / "orchestrators").iterdir()) / "inbox.jsonl"
    inbox.unlink()
    inbox.symlink_to(settings.state_root / "runs" / "child-one" / "messages.jsonl")
    with pytest.raises(WorkflowError):
        import_registered(settings, "main-orchestrator")


def test_replay_uses_bounded_round_robin_across_small_batches(tmp_path: Path, monkeypatch) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    for session_id in ("child-one", "child-two", "child-three"):
        _make_child(tmp_path, settings, session_id, session_id, monkeypatch)
    create_registry(settings, "fair-watcher")
    for session_id in ("child-one", "child-two", "child-three"):
        register_child(settings, "fair-watcher", session_id)

    delivered = []
    for _ in range(3):
        report = replay_registered(settings, "fair-watcher", batch_size=1, max_per_child=1)
        delivered.extend(item["sender_session_id"] for item in report["imported"])
    assert delivered == ["child-one", "child-two", "child-three"]


def test_registered_child_message_signals_one_shared_opaque_channel(tmp_path: Path, monkeypatch) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "wake-child", "wake complete", monkeypatch)
    create_registry(settings, "wake-watcher")
    register_child(settings, "wake-watcher", "wake-child")
    channels: list[str] = []
    monkeypatch.setattr("agent_workflow.tmux.signal_waiters", channels.append)
    append_message(
        settings.state_root / "runs" / "wake-child",
        session_id="wake-child", direction="child_to_parent", kind="progress",
        actor="child", content="durable progress",
    )
    assert channels == [orchestrator_wakeup_channel("wake-watcher")]


def test_watch_rejects_second_active_supervisor_with_stable_diagnostic(tmp_path: Path, monkeypatch) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    create_registry(settings, "leased-watcher")
    directory = orchestrator_dir(settings, "leased-watcher")
    with (directory / ".supervisor.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(WorkflowError, match="orchestrator supervisor already active"):
            watch(settings, "leased-watcher", interval_seconds=0.01, max_cycles=1)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


@pytest.mark.parametrize("shutdown_signal", [signal.SIGTERM, signal.SIGINT])
def test_signal_shutdown_preserves_cursor_resume_boundary(
    tmp_path: Path, monkeypatch, shutdown_signal: signal.Signals
) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "signal-child", "signal complete", monkeypatch)
    create_registry(settings, "signal-watcher")
    register_child(settings, "signal-watcher", "signal-child")

    def interrupting_wait(_channel: str, _timeout: float) -> bool:
        os.kill(os.getpid(), shutdown_signal)
        return False

    monkeypatch.setattr("agent_workflow.orchestrator_supervisor.wait_for_wakeup", interrupting_wait)
    result = watch(settings, "signal-watcher", interval_seconds=0.01, poll_seconds=0.01)
    assert result["state"] == "shutdown"
    assert result["advanced"] == 1
    resumed = replay_registered(settings, "signal-watcher", batch_size=1)
    assert resumed["advanced"] == 0
    events = (orchestrator_dir(settings, "signal-watcher") / "supervisor-events.jsonl").read_text()
    assert '"reason":"shutdown"' in events


def test_missing_and_corrupt_cursor_rebuild_from_durable_inbox_and_quarantine(
    tmp_path: Path, monkeypatch
) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "rebuild-child", "rebuild complete", monkeypatch)
    create_registry(settings, "rebuild-watcher")
    register_child(settings, "rebuild-watcher", "rebuild-child")
    assert replay_registered(settings, "rebuild-watcher")["advanced"] == 1
    directory = orchestrator_dir(settings, "rebuild-watcher")
    child = read_child_registry(settings, "rebuild-watcher")["children"][0]
    cursor = directory / "cursors" / f"{hashlib.sha256(child['identity_digest'].encode()).hexdigest()}.json"

    cursor.unlink()
    missing = replay_registered(settings, "rebuild-watcher")
    assert missing["advanced"] == 0
    assert missing["reconstructed"] is True

    cursor.write_text("{not-json", encoding="utf-8")
    corrupt = replay_registered(settings, "rebuild-watcher")
    assert corrupt["advanced"] == 0
    quarantine = directory / "cursors" / "cursor-quarantine"
    report = next(quarantine.glob("*.json"))
    assert json.loads(report.read_text(encoding="utf-8"))["content_redacted"] is True


def test_replay_retries_after_inbox_commit_crash_without_duplicate_event(
    tmp_path: Path, monkeypatch
) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "crash-child", "crash complete", monkeypatch)
    create_registry(settings, "crash-watcher")
    register_child(settings, "crash-watcher", "crash-child")
    original = __import__("agent_workflow.orchestrator_inbox", fromlist=["_write_source_cursor"])._write_source_cursor
    calls = 0

    def crash_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected after inbox commit")
        return original(*args, **kwargs)

    monkeypatch.setattr("agent_workflow.orchestrator_inbox._write_source_cursor", crash_once)
    with pytest.raises(RuntimeError, match="after inbox commit"):
        replay_registered(settings, "crash-watcher")
    monkeypatch.setattr("agent_workflow.orchestrator_inbox._write_source_cursor", original)
    recovered = replay_registered(settings, "crash-watcher")
    assert recovered["advanced"] == 0
    assert len(read_inbox(settings, "crash-watcher")) == 1


def test_replay_retries_when_source_read_finishes_before_inbox_append(
    tmp_path: Path, monkeypatch
) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "before-append-child", "before append", monkeypatch)
    create_registry(settings, "before-append-watcher")
    register_child(settings, "before-append-watcher", "before-append-child")
    module = __import__("agent_workflow.orchestrator_inbox", fromlist=["import_message"])
    original = module.import_message

    def crash_before_append(*args, **kwargs):
        raise RuntimeError("injected before inbox append")

    monkeypatch.setattr(module, "import_message", crash_before_append)
    with pytest.raises(RuntimeError, match="before inbox append"):
        replay_registered(settings, "before-append-watcher")
    monkeypatch.setattr(module, "import_message", original)
    recovered = replay_registered(settings, "before-append-watcher")
    assert recovered["advanced"] == 1
    assert recovered["count"] == 1


def test_stale_lock_uses_process_identity_and_bounded_override(tmp_path: Path) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    create_registry(settings, "stale-watcher")
    lock = orchestrator_dir(settings, "stale-watcher") / ".supervisor.lock"
    lock.write_text("not-json", encoding="utf-8")
    with pytest.raises(WorkflowError, match="operator-override"):
        watch(settings, "stale-watcher", interval_seconds=0.01, max_cycles=1)
    recovered = watch(settings, "stale-watcher", interval_seconds=0.01, max_cycles=1, operator_override=True)
    assert recovered["state"] == "completed"


def test_acknowledged_unactioned_restart_uses_event_id_and_digest_projection(
    tmp_path: Path, monkeypatch
) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "ack-child", "ack complete", monkeypatch)
    create_registry(settings, "ack-watcher")
    register_child(settings, "ack-watcher", "ack-child")
    first = replay_registered(settings, "ack-watcher")
    event = read_inbox(settings, "ack-watcher", include_content=True)[0]
    acknowledged = acknowledge_event(
        settings,
        "ack-watcher",
        event["event_id"],
        actor_principal="principal:orchestrator",
        reason="accepted for scheduling",
    )
    assert acknowledged["duplicate"] is False
    pending = replay_registered(settings, "ack-watcher")
    assert pending["pending_acknowledgements"] == []
    assert pending["pending_actions"] == [event["event_id"]]
    assert pending["pending_action_digests"] == {event["event_id"]: event_digest(event)}
    assert first["count"] == 1


def test_action_requires_validated_acknowledgement(tmp_path: Path, monkeypatch) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "action-child", "action complete", monkeypatch)
    create_registry(settings, "action-watcher")
    register_child(settings, "action-watcher", "action-child")
    replay_registered(settings, "action-watcher")
    event = read_inbox(settings, "action-watcher", include_content=True)[0]

    with pytest.raises(WorkflowError, match="action requires a validated acknowledgement"):
        record_action(
            settings,
            "action-watcher",
            event["event_id"],
            action="none",
            target_session_id=None,
            evidence_refs=["no-action-required"],
        )
    actions_path = orchestrator_dir(settings, "action-watcher") / "actions.jsonl"
    assert not actions_path.exists()

    acknowledge_event(
        settings,
        "action-watcher",
        event["event_id"],
        actor_principal="principal:orchestrator",
        reason="accepted for scheduling",
    )
    actioned = record_action(
        settings,
        "action-watcher",
        event["event_id"],
        action="none",
        target_session_id=None,
        evidence_refs=["no-action-required"],
    )
    assert actioned["duplicate"] is False
    assert actioned["action"]["event_id"] == event["event_id"]


def test_same_length_pending_projection_id_or_digest_tampering_is_quarantined(
    tmp_path: Path, monkeypatch
) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "projection-child", "projection complete", monkeypatch)
    create_registry(settings, "projection-watcher")
    register_child(settings, "projection-watcher", "projection-child")
    watch(settings, "projection-watcher", interval_seconds=0.01, max_cycles=1)
    event = read_inbox(settings, "projection-watcher", include_content=True)[0]
    directory = orchestrator_dir(settings, "projection-watcher")
    status_path = directory / "supervisor-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["pending_acknowledgements"] = [str(uuid.uuid4())]
    status["pending_acknowledgement_digests"] = {status["pending_acknowledgements"][0]: "sha256:" + "0" * 64}
    status_path.write_text(json.dumps(status), encoding="utf-8")

    repaired = watch(settings, "projection-watcher", interval_seconds=0.01, max_cycles=1)
    assert repaired["pending_acknowledgements"] == [event["event_id"]]
    rebuilt = json.loads(status_path.read_text(encoding="utf-8"))
    assert rebuilt["pending_acknowledgements"] == [event["event_id"]]
    assert rebuilt["pending_acknowledgement_digests"] == {event["event_id"]: event_digest(event)}
    quarantine = directory / "supervisor-status-quarantine"
    assert any(json.loads(path.read_text(encoding="utf-8"))["content_redacted"] for path in quarantine.glob("*.json"))


def test_post_notification_and_post_action_crashes_replay_durable_state(
    tmp_path: Path, monkeypatch
) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "crash-window-child", "crash-window complete", monkeypatch)
    create_registry(settings, "crash-window-watcher")
    register_child(settings, "crash-window-watcher", "crash-window-child")
    event = read_inbox(settings, "crash-window-watcher", include_content=True)
    assert not event

    module = __import__("agent_workflow.orchestrator_supervisor", fromlist=["_notify_orchestrator"])
    original_notify = module._notify_orchestrator

    def crash_after_notification(report):
        original_notify(report)
        raise RuntimeError("injected after notification")

    monkeypatch.setattr(module, "_notify_orchestrator", crash_after_notification)
    with pytest.raises(RuntimeError, match="after notification"):
        watch(settings, "crash-window-watcher", interval_seconds=0.01, max_cycles=1)
    monkeypatch.setattr(module, "_notify_orchestrator", original_notify)
    event = read_inbox(settings, "crash-window-watcher", include_content=True)[0]
    acknowledge_event(
        settings,
        "crash-window-watcher",
        event["event_id"],
        actor_principal="principal:orchestrator",
        reason="accepted after notification retry",
    )
    record_action(
        settings,
        "crash-window-watcher",
        event["event_id"],
        action="none",
        target_session_id=None,
        evidence_refs=["no-action-required"],
    )
    original_status = module._write_status
    writes = 0

    def crash_after_action(*args, **kwargs):
        nonlocal writes
        writes += 1
        if writes == 2:
            raise RuntimeError("injected after action")
        return original_status(*args, **kwargs)

    monkeypatch.setattr(module, "_write_status", crash_after_action)
    with pytest.raises(RuntimeError, match="after action"):
        watch(settings, "crash-window-watcher", interval_seconds=0.01, max_cycles=1)
    monkeypatch.setattr(module, "_write_status", original_status)
    recovered = watch(settings, "crash-window-watcher", interval_seconds=0.01, max_cycles=1)
    assert recovered["pending_acknowledgements"] == []
    assert recovered["pending_actions"] == []
    assert len(read_inbox(settings, "crash-window-watcher")) == 1
