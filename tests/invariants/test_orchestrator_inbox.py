from __future__ import annotations

import fcntl
import json
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

import agent_workflow.orchestrator_inbox as orchestrator_inbox
from agent_workflow.agent_runs import prepare
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.messages import append_message
from agent_workflow.orchestrator_inbox import (
    OrchestratorInboxError,
    create_registry,
    import_registered,
    orchestrator_dir,
    read_inbox,
    register_child,
    replay_registered,
)
from agent_workflow.orchestrator_supervisor import watch
from agent_workflow.state import run_dir


def _git_repo(path: Path) -> None:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.email", "fixture@example.com"], check=True)
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Fixture"], check=True)
    (path / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True)


def _make_child(tmp_path: Path, settings, agent_run_id: str, content: str) -> dict:
    repo = tmp_path / f"repo-{agent_run_id}"
    _git_repo(repo)
    prompt = tmp_path / f"{agent_run_id}.md"
    prompt.write_text("fixture task\n", encoding="utf-8")
    prepare(
        settings,
        agent_run_id=agent_run_id,
        workdir=repo,
        prompt_path=prompt,
        explicit_command=["/bin/true"],
        structured=True,
        worker_mode="headless",
    )
    return append_message(
        run_dir(settings, agent_run_id),
        agent_run_id=agent_run_id,
        direction="child_to_parent",
        kind="progress",
        actor="fixture-child",
        content=content,
    )


def _settings(tmp_path: Path):
    return replace(defaults(tmp_path / "missing.toml"), state_root=tmp_path / "state")


def test_registry_import_is_identity_bound_and_idempotent(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = _make_child(tmp_path, settings, "child-one", "implemented first step")
    create_registry(settings, "root")
    registered = register_child(settings, "root", "child-one")
    assert registered["child"]["agent_run_id"] == "child-one"

    first = import_registered(settings, "root")
    assert first["count"] == 1
    assert first["imported"][0]["kind"] == "agent_progress"
    second = import_registered(settings, "root")
    assert second["count"] == 1
    assert second["imported"][0]["duplicate"] is True

    metadata = read_inbox(settings, "root")
    assert len(metadata) == 1
    assert metadata[0]["source_message_id"] == source["message_id"]
    assert "summary" not in metadata[0]
    assert read_inbox(settings, "root", include_content=True)[0]["summary"] == "implemented first step"


def test_replay_uses_durable_per_child_cursors_and_fairness(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    for child in ("child-a", "child-b"):
        _make_child(tmp_path, settings, child, f"progress from {child}")
    create_registry(settings, "root")
    register_child(settings, "root", "child-a")
    register_child(settings, "root", "child-b")

    first = replay_registered(settings, "root", batch_size=1, max_per_child=1)
    second = replay_registered(settings, "root", batch_size=1, max_per_child=1)
    third = replay_registered(settings, "root", batch_size=2, max_per_child=1)

    assert first["advanced"] == 1
    assert second["advanced"] == 1
    assert third["advanced"] == 0
    events = read_inbox(settings, "root", include_content=True)
    assert {event["sender_agent_run_id"] for event in events} == {"child-a", "child-b"}


def test_completion_message_without_closed_sealed_assignment_fails_closed(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _make_child(tmp_path, settings, "child-one", "still working")
    append_message(
        run_dir(settings, "child-one"),
        agent_run_id="child-one",
        direction="child_to_parent",
        kind="task_complete",
        actor="fixture-child",
        content="complete",
    )
    create_registry(settings, "root")
    register_child(settings, "root", "child-one")

    with pytest.raises(OrchestratorInboxError, match="closed assignment evidence"):
        import_registered(settings, "root")


def test_watch_replays_durable_messages_without_wakeup_channel(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _make_child(tmp_path, settings, "child-one", "durable progress")
    create_registry(settings, "watcher")
    register_child(settings, "watcher", "child-one")

    first = watch(settings, "watcher", interval_seconds=0.01, poll_seconds=0.01, max_cycles=1)
    second = watch(settings, "watcher", interval_seconds=0.01, poll_seconds=0.01, max_cycles=1)

    assert first["advanced"] == 1
    assert first["imported"] == 1
    assert second["advanced"] == 0
    assert len(read_inbox(settings, "watcher")) == 1


def test_watch_notifies_after_persisting_bounded_projection(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    source = _make_child(tmp_path, settings, "child-one", "x" * 700)
    create_registry(settings, "watcher")
    register_child(settings, "watcher", "child-one")
    delivered: list[dict] = []

    def adapter(record: dict) -> None:
        # The adapter observes the durable state before it is called.
        assert read_inbox(settings, "watcher", event_id=record["event_id"])
        delivered.append(record)

    result = watch(
        settings,
        "watcher",
        interval_seconds=0.01,
        notification_adapter=adapter,
        max_cycles=1,
    )

    assert result["imported"] == 1
    assert delivered[0]["event_id"] == read_inbox(settings, "watcher")[0]["event_id"]
    assert len(delivered[0]["summary"]) <= 512
    assert set(delivered[0]) == {
        "event_id", "orchestrator_id", "sender_agent_run_id", "kind", "summary",
    }
    assert source["content"] not in delivered[0]["summary"]


def test_watch_notification_failure_does_not_stop_or_lose_event(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _make_child(tmp_path, settings, "child-one", "durable progress")
    create_registry(settings, "watcher")
    register_child(settings, "watcher", "child-one")

    def failing_adapter(_record: dict) -> None:
        raise RuntimeError("host unavailable")

    result = watch(
        settings,
        "watcher",
        interval_seconds=0.01,
        notification_adapter=failing_adapter,
        max_cycles=1,
    )

    assert result["state"] == "completed"
    assert len(read_inbox(settings, "watcher")) == 1
    recovered = watch(settings, "watcher", interval_seconds=0.01, max_cycles=1)
    assert recovered["advanced"] == 0
    assert len(read_inbox(settings, "watcher")) == 1


def test_watch_keeps_one_registry_alive_for_successive_children(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _make_child(tmp_path, settings, "child-a", "first")
    create_registry(settings, "watcher")
    register_child(settings, "watcher", "child-a")

    watcher_code = """
import json
import sys
from dataclasses import replace
from pathlib import Path
from agent_workflow.config import defaults
from agent_workflow.orchestrator_supervisor import watch

settings = replace(defaults(Path(sys.argv[1])), state_root=Path(sys.argv[2]))
print(json.dumps(watch(settings, "watcher", interval_seconds=0.01, max_cycles=200, batch_size=1)), flush=True)
"""
    process = subprocess.Popen(
        [sys.executable, "-c", watcher_code, str(settings.config_path), str(settings.state_root)],
        cwd=Path(__file__).parents[2],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        events_path = orchestrator_dir(settings, "watcher") / "supervisor-events.jsonl"
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if events_path.exists() and '"reason":"startup"' in events_path.read_text(encoding="utf-8"):
                break
            time.sleep(0.01)
        else:
            raise AssertionError("watcher did not start")

        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not read_inbox(settings, "watcher"):
            time.sleep(0.01)
        assert read_inbox(settings, "watcher")[0]["sender_agent_run_id"] == "child-a"

        _make_child(tmp_path, settings, "child-b", "second")
        register_child(settings, "watcher", "child-b")
        stdout, stderr = process.communicate(timeout=5)
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=5)

    assert process.returncode == 0, stderr
    result = json.loads(stdout)
    assert result["state"] == "completed"
    assert result["advanced"] == 2
    assert {event["sender_agent_run_id"] for event in read_inbox(settings, "watcher")} == {
        "child-a", "child-b"
    }


def test_watch_duplicate_delivery_after_cursor_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings(tmp_path)
    _make_child(tmp_path, settings, "child-one", "cursor recovery")
    create_registry(settings, "watcher")
    register_child(settings, "watcher", "child-one")

    def fail_cursor_write(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated cursor write failure")

    monkeypatch.setattr(orchestrator_inbox, "_write_source_cursor", fail_cursor_write)
    failed = watch(settings, "watcher", interval_seconds=0.01, max_cycles=1)
    assert failed["state"] == "completed"
    assert failed["advanced"] == 0
    assert len(read_inbox(settings, "watcher")) == 1

    monkeypatch.undo()
    recovered = watch(settings, "watcher", interval_seconds=0.01, max_cycles=1)
    assert recovered["advanced"] == 1
    assert recovered["imported"] == 1
    assert recovered["state"] == "completed"
    assert len(read_inbox(settings, "watcher")) == 1


def test_watch_has_a_single_writer_lease(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    create_registry(settings, "leased-watcher")
    directory = orchestrator_dir(settings, "leased-watcher")
    lock_path = directory / ".supervisor.lock"
    with lock_path.open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(WorkflowError, match="orchestrator supervisor already active"):
            watch(settings, "leased-watcher", interval_seconds=0.01, max_cycles=1)
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
