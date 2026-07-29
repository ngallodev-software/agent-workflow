from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from agent_workflow.agent_context import idle_interactive_sessions
from agent_workflow import tmux
from agent_workflow.config import Settings, defaults
from agent_workflow.state import list_statuses, read_status


def pane(pane_id: str, *, run_id: str | None = None) -> tmux.PaneInfo:
    return tmux.PaneInfo(
        pid=123,
        dead=False,
        command="agent",
        pane_id=pane_id,
        session_name="shared",
        window_index="0",
        run_id=run_id,
    )


def test_stable_pane_id_survives_layout_churn(monkeypatch) -> None:
    current = pane("%112", run_id="run-1")
    monkeypatch.setattr(tmux, "pane_info", lambda target: current if target == "%112" else None)
    monkeypatch.setattr(tmux, "list_panes", lambda target: [current])

    resolved = tmux.resolve_pane(
        "%112", host_session="shared", run_id="run-1", require_binding=True
    )
    assert resolved is current


def test_binding_mismatch_fails_closed_even_when_pane_is_live(monkeypatch) -> None:
    current = pane("%112", run_id="other-run")
    monkeypatch.setattr(tmux, "pane_info", lambda target: current)
    monkeypatch.setattr(tmux, "list_panes", lambda target: [current])

    assert tmux.resolve_pane(
        "%112", host_session="shared", run_id="run-1", require_binding=True
    ) is None


def test_legacy_position_recovers_only_unique_run_bound_pane(monkeypatch) -> None:
    legacy_location = pane("%101", run_id="other-run")
    bound = pane("%112", run_id="run-1")
    monkeypatch.setattr(tmux, "pane_info", lambda target: legacy_location)
    monkeypatch.setattr(tmux, "list_panes", lambda target: [legacy_location, bound])

    resolved = tmux.resolve_pane(
        "shared:0.1", host_session="shared", run_id="run-1", require_binding=True
    )
    assert resolved is bound


def _legacy_status() -> dict[str, object]:
    return {
        "schema": "agent-workflow/session-status/v2",
        "session_id": "run-1",
        "status": "running",
        "tmux_mode": "shared_window",
        "tmux_session": "shared",
        "tmux_target": "shared:0.1",
        "tmux_pane_id": None,
    }


def _write_status(tmp_path: Path, value: dict[str, object]) -> tuple[Settings, Path]:
    settings = replace(defaults(tmp_path / "config.toml"), state_root=tmp_path / "state")
    run = settings.state_root / "runs" / "run-1"
    run.mkdir(parents=True)
    path = run / "status.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return settings, path


def test_status_migration_persists_stable_identity_on_unique_recovery(monkeypatch, tmp_path: Path) -> None:
    settings, path = _write_status(tmp_path, _legacy_status())
    bound = pane("%112", run_id="run-1")
    monkeypatch.setattr(tmux, "resolve_pane", lambda *args, **kwargs: bound)

    migrated = read_status(settings, "run-1")

    assert migrated["tmux_pane_id"] == "%112"
    assert migrated["tmux_target"] == "%112"
    assert migrated["tmux_window_target"] == "shared:0"
    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["tmux_pane_id"] == "%112"
    assert persisted["tmux_target"] == "%112"
    assert persisted["tmux_window_target"] == "shared:0"


def test_migrated_live_pane_remains_discoverable_in_its_window(
    monkeypatch, tmp_path: Path
) -> None:
    settings, path = _write_status(tmp_path, _legacy_status())
    (path.parent / "agent-context.json").write_text(
        json.dumps(
            {
                "schema": "agent-workflow/agent-context/v1",
                "interactive": True,
                "state": "idle_reusable",
                "updated_at": "2026-07-29T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    bound = pane("%112", run_id="run-1")
    monkeypatch.setattr(tmux, "resolve_pane", lambda *args, **kwargs: bound)

    rows = idle_interactive_sessions(settings, window_target="shared:0")

    assert [row["session_id"] for row in rows] == ["run-1"]
    assert rows[0]["tmux_pane_id"] == "%112"
    assert json.loads(path.read_text(encoding="utf-8"))["tmux_window_target"] == "shared:0"


def test_status_migration_is_fail_closed_for_ambiguous_recovery(
    monkeypatch, tmp_path: Path
) -> None:
    original = _legacy_status()
    settings, path = _write_status(tmp_path, original)
    first = pane("%112", run_id="run-1")
    second = pane("%113", run_id="run-1")
    monkeypatch.setattr(tmux, "pane_info", lambda target: None)
    monkeypatch.setattr(tmux, "list_panes", lambda target: [first, second])

    observed = list_statuses(settings)

    assert observed == [original]
    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_status_migration_is_fail_closed_when_binding_is_missing(monkeypatch, tmp_path: Path) -> None:
    original = _legacy_status()
    settings, path = _write_status(tmp_path, original)
    monkeypatch.setattr(tmux, "resolve_pane", lambda *args, **kwargs: None)

    observed = read_status(settings, "run-1")

    assert observed == original
    assert json.loads(path.read_text(encoding="utf-8")) == original


def test_dedicated_session_status_is_not_migrated(monkeypatch, tmp_path: Path) -> None:
    dedicated = _legacy_status()
    dedicated.update(
        tmux_mode="dedicated_session",
        tmux_session="run-1",
        tmux_target="run-1",
    )
    settings, path = _write_status(tmp_path, dedicated)
    def fail_if_called(*args, **kwargs):
        raise AssertionError("dedicated session status must not trigger migration")

    monkeypatch.setattr(tmux, "resolve_pane", fail_if_called)

    observed = read_status(settings, "run-1")

    assert observed == dedicated
    assert json.loads(path.read_text(encoding="utf-8")) == dedicated


def test_legacy_position_with_ambiguous_binding_is_unavailable(monkeypatch) -> None:
    first = pane("%112", run_id="run-1")
    second = pane("%113", run_id="run-1")
    monkeypatch.setattr(tmux, "pane_info", lambda target: pane("%101"))
    monkeypatch.setattr(tmux, "list_panes", lambda target: [first, second])

    assert tmux.resolve_pane(
        "shared:0.1", host_session="shared", run_id="run-1", require_binding=True
    ) is None


def test_dedicated_session_target_remains_compatible_without_metadata(monkeypatch) -> None:
    current = pane("%1")
    monkeypatch.setattr(tmux, "pane_info", lambda target: current)

    resolved = tmux.resolve_pane(
        "run-1", host_session="run-1", run_id="run-1", require_binding=False
    )
    assert resolved is current


def test_destroyed_stable_pane_is_not_rebound(monkeypatch) -> None:
    monkeypatch.setattr(tmux, "pane_info", lambda target: None)
    replacement = pane("%113", run_id=None)
    monkeypatch.setattr(tmux, "list_panes", lambda target: [replacement])

    assert tmux.resolve_pane(
        "%112", host_session="shared", run_id="run-1", require_binding=True
    ) is None
