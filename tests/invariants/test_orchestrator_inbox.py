from __future__ import annotations

import fcntl
import json
import uuid
from dataclasses import replace
from pathlib import Path

import pytest

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.orchestrator_inbox import (
    create_registry,
    import_registered,
    read_inbox,
    register_child,
    unregister_child,
)
from agent_workflow.orchestrator_inbox import orchestrator_dir, replay_registered
from agent_workflow.orchestrator_supervisor import watch
from agent_workflow.messages import append_message
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


def test_terminal_import_rejects_missing_seal_and_stale_assignment_evidence(tmp_path: Path, monkeypatch) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "terminal-child", "terminal complete", monkeypatch)
    create_registry(settings, "terminal-root")
    register_child(settings, "terminal-root", "terminal-child")
    run = settings.state_root / "runs" / "terminal-child"
    context = json.loads((run / "agent-context.json").read_text(encoding="utf-8"))
    context["state"] = "closed"
    atomic_write_json(run / "agent-context.json", context)
    events = json.loads((run / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])
    events["new"] = "closed"
    (run / "events.jsonl").write_text(json.dumps(events, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="sealed receipt"):
        import_registered(settings, "terminal-root")

    _make_child(tmp_path, settings, "stale-child", "stale complete", monkeypatch)
    register_child(settings, "terminal-root", "stale-child")
    stale_run = settings.state_root / "runs" / "stale-child"
    stale_events = json.loads((stale_run / "events.jsonl").read_text(encoding="utf-8").splitlines()[0])
    stale_events["new"] = "busy"
    (stale_run / "events.jsonl").write_text(json.dumps(stale_events, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(WorkflowError, match="terminal or idle_reusable"):
        import_registered(settings, "terminal-root", session_id="stale-child")


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


def test_registered_child_message_replay_does_not_require_terminal_wakeup(tmp_path: Path, monkeypatch) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "wake-child", "wake complete", monkeypatch)
    create_registry(settings, "wake-watcher")
    register_child(settings, "wake-watcher", "wake-child")
    append_message(
        settings.state_root / "runs" / "wake-child",
        session_id="wake-child", direction="child_to_parent", kind="progress",
        actor="child", content="durable progress",
    )
    report = replay_registered(settings, "wake-watcher", batch_size=1, max_per_child=1)
    assert report["count"] == 1


def test_watch_rejects_second_active_supervisor_with_stable_diagnostic(tmp_path: Path, monkeypatch) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    create_registry(settings, "leased-watcher")
    directory = orchestrator_dir(settings, "leased-watcher")
    with (directory / ".supervisor.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(WorkflowError, match="orchestrator supervisor already active"):
            watch(settings, "leased-watcher", interval_seconds=0.01, max_cycles=1)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def test_polling_watch_preserves_cursor_resume_boundary(tmp_path: Path, monkeypatch) -> None:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    _make_child(tmp_path, settings, "signal-child", "signal complete", monkeypatch)
    create_registry(settings, "signal-watcher")
    register_child(settings, "signal-watcher", "signal-child")

    result = watch(settings, "signal-watcher", interval_seconds=0.01, poll_seconds=0.01, max_cycles=1)
    assert result["state"] == "completed"
    assert result["advanced"] == 1
    resumed = replay_registered(settings, "signal-watcher", batch_size=1)
    assert resumed["advanced"] == 0
    events = (orchestrator_dir(settings, "signal-watcher") / "supervisor-events.jsonl").read_text()
    assert '"reason":"shutdown"' in events
