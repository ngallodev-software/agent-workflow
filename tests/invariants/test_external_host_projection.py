from pathlib import Path

import pytest

from agent_workflow.external_host_projection import ExternalHostProjection, status_presentation


def _binding(worker="w1", generation=1):
    return {"agent_run_id": "run-1", "bound": True, "worker_id": worker, "generation": generation}


def test_terminal_completion_retires_once(tmp_path: Path):
    current = {"status": "running"}
    closed = []
    adapter = ExternalHostProjection(tmp_path / "projection.jsonl", status_reader=lambda _: current, binding_reader=lambda _: _binding(), close=lambda handle: closed.append(dict(handle)))
    handle = {"pane": "p1", "pid": 12, "started_at": "t1"}
    adapter.register("run-1", _binding(), handle)
    assert adapter.reconcile("run-1").action == "open"
    current["status"] = "completed"
    assert adapter.reconcile("run-1").action == "retired"
    assert adapter.reconcile("run-1").action == "noop"
    assert closed == [handle]


@pytest.mark.parametrize("terminal", ["failed", "interrupted", "terminated", "retired"])
def test_all_terminal_statuses_retire(terminal, tmp_path: Path):
    current = {"status": terminal}
    closed = []
    adapter = ExternalHostProjection(tmp_path / "p.jsonl", status_reader=lambda _: current, binding_reader=lambda _: _binding(), close=closed.append)
    handle = {"pane": terminal}
    adapter.register("run-1", _binding(), handle)
    assert adapter.reconcile("run-1", handle=handle).action == "retired"
    assert closed == [handle]


def test_missing_or_stale_views_never_retire(tmp_path: Path):
    current = {"status": "running"}
    closed = []
    adapter = ExternalHostProjection(tmp_path / "p.jsonl", status_reader=lambda _: current, binding_reader=lambda _: _binding(), close=closed.append)
    adapter.register("run-1", _binding(), {"pane": "p"})
    current.clear()
    assert adapter.reconcile("run-1").action == "unknown"
    current.update(status="completed", stale=True)
    assert adapter.reconcile("run-1").action == "unknown"
    assert not closed


def test_generation_and_handle_reuse_are_safe(tmp_path: Path):
    binding = _binding()
    current = {"status": "completed"}
    closed = []
    adapter = ExternalHostProjection(tmp_path / "p.jsonl", status_reader=lambda _: current, binding_reader=lambda _: binding, close=closed.append)
    old = {"pane": "p", "pid": 10, "started_at": "old"}
    adapter.register("run-1", binding, old)
    binding = _binding(generation=2)
    assert adapter.reconcile("run-1", handle={"pane": "p", "pid": 10, "started_at": "new"}).action == "unknown"
    assert not closed
    new = {"pane": "p", "pid": 10, "started_at": "new"}
    adapter.register("run-1", binding, new)
    assert adapter.reconcile("run-1", handle=new).action == "retired"
    assert closed == [new]


def test_presentation_separates_authority():
    view = status_presentation(worker={"id": "w"}, execution={"status": "completed"}, review={"state": "pending"}, acceptance={"state": "pending"}, projection={"state": "retired"})
    assert set(view) == {"schema", "worker", "execution", "review", "acceptance", "projection"}


def test_restart_replays_retired_projection_without_closing_again(tmp_path: Path):
    current = {"status": "completed"}
    closed = []
    path = tmp_path / "p.jsonl"
    handle = {"pane": "restart"}
    first = ExternalHostProjection(path, status_reader=lambda _: current, binding_reader=lambda _: _binding(), close=closed.append)
    first.register("run-1", _binding(), handle)
    assert first.reconcile("run-1", handle=handle).action == "retired"
    second = ExternalHostProjection(path, status_reader=lambda _: current, binding_reader=lambda _: _binding(), close=closed.append)
    assert second.reconcile("run-1", handle=handle).action == "noop"
    assert closed == [handle]
