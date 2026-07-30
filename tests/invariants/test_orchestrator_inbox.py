from __future__ import annotations

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
from agent_workflow.sessions import launch
from agent_workflow.util import atomic_write_json, utc_now
from tests.conftest import git_repo


def _make_child(tmp_path: Path, settings, session_id: str, summary: str, monkeypatch) -> None:
    repo = tmp_path / f"repo-{session_id}"
    git_repo(repo)
    prompt = tmp_path / f"{session_id}.md"
    prompt.write_text("child\n", encoding="utf-8")
    monkeypatch.setattr("agent_workflow.tmux.create_session", lambda *args: None)
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
