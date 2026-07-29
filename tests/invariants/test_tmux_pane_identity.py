from __future__ import annotations

from agent_workflow import tmux


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
