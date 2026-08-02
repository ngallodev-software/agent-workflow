from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import agent_workflow.cli_handlers.orchestrator as handler
from agent_workflow.config import defaults


def test_orchestrator_registry_routes_exact_operations(tmp_path: Path, monkeypatch) -> None:
    settings = defaults(tmp_path / "config.toml")
    calls = []
    monkeypatch.setattr(handler, "create_registry", lambda *a, **k: calls.append(("create", a, k)) or "created")
    monkeypatch.setattr(handler, "read_child_registry", lambda *a, **k: calls.append(("inspect", a, k)) or "inspected")
    monkeypatch.setattr(handler, "register_child", lambda *a, **k: calls.append(("register", a, k)) or "registered")
    monkeypatch.setattr(handler, "unregister_child", lambda *a, **k: calls.append(("unregister", a, k)) or "unregistered")

    cases = [
        (Namespace(orchestrator_command="registry", registry_command="create", orchestrator_id="root", workflow_id="wf"), "created"),
        (Namespace(orchestrator_command="registry", registry_command="inspect", orchestrator_id="root"), "inspected"),
        (Namespace(orchestrator_command="registry", registry_command="register", orchestrator_id="root", session_id="child"), "registered"),
        (Namespace(orchestrator_command="registry", registry_command="unregister", orchestrator_id="root", session_id="child", state="closed"), "unregistered"),
    ]
    for args, expected in cases:
        assert handler.handle_orchestrator_command(settings, args) == expected

    assert calls == [
        ("create", (settings, "root"), {"workflow_id": "wf"}),
        ("inspect", (settings, "root"), {}),
        ("register", (settings, "root", "child"), {}),
        ("unregister", (settings, "root", "child"), {"state": "closed"}),
    ]


def test_orchestrator_watch_import_and_read_preserve_bounds(tmp_path: Path, monkeypatch) -> None:
    settings = defaults(tmp_path / "config.toml")
    calls = []
    monkeypatch.setattr(handler, "watch_orchestrator", lambda *a, **k: calls.append(("watch", a, k)) or "watched")
    monkeypatch.setattr(handler, "import_registered", lambda *a, **k: calls.append(("import", a, k)) or "imported")
    monkeypatch.setattr(handler, "read_inbox", lambda *a, **k: calls.append(("read", a, k)) or "read")

    watch = Namespace(
        orchestrator_command="watch", orchestrator_id="root", interval_seconds=2.0,
        poll_seconds=0.5, batch_size=10, max_per_child=3, max_cycles=4,
    )
    imported = Namespace(
        orchestrator_command="inbox", inbox_command="import", orchestrator_id="root",
        session_id="child", max_per_child=7,
    )
    read = Namespace(
        orchestrator_command="inbox", inbox_command="read", orchestrator_id="root",
        after=11, limit=12, event_id="event-1", include_content=True,
    )

    assert handler.handle_orchestrator_command(settings, watch) == "watched"
    assert handler.handle_orchestrator_command(settings, imported) == "imported"
    assert handler.handle_orchestrator_command(settings, read) == "read"
    assert calls == [
        ("watch", (settings, "root"), {
            "interval_seconds": 2.0, "poll_seconds": 0.5, "batch_size": 10,
            "max_per_child": 3, "max_cycles": 4,
        }),
        ("import", (settings, "root"), {"session_id": "child", "max_per_child": 7}),
        ("read", (settings, "root"), {
            "after_sequence": 11, "limit": 12, "event_id": "event-1",
            "include_content": True,
        }),
    ]
