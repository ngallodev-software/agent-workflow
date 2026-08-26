from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.run_lifecycle import initialize_execution_path, transition_execution_path
from agent_workflow.state import STATUS_SCHEMA, read_status_path, update_projection_path


def _status(status: str = "prepared") -> dict[str, object]:
    return {
        "schema": STATUS_SCHEMA,
        "agent_run_id": "run-1",
        "status": status,
    }


def _events(path: Path) -> list[dict[str, object]]:
    events = path.parent / "events.jsonl"
    if not events.is_file():
        return []
    return [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines() if line]


def test_projection_api_cannot_mutate_execution_status(tmp_path: Path) -> None:
    path = tmp_path / "run-1" / "status.json"
    path.parent.mkdir()
    initialize_execution_path(path, _status())

    with pytest.raises(WorkflowError, match="run_lifecycle.transition_execution"):
        update_projection_path(path, status="running")

    assert read_status_path(path)["status"] == "prepared"
    assert [event["new"] for event in _events(path)] == ["prepared"]


def test_unsealed_execution_transition_appends_authority_event(tmp_path: Path) -> None:
    path = tmp_path / "run-1" / "status.json"
    path.parent.mkdir()
    initialize_execution_path(path, _status())

    transition_execution_path(
        path,
        "running",
        actor="test",
        reason="worker started",
        worker_id="worker-1",
    )

    assert read_status_path(path)["status"] == "running"
    assert [event["new"] for event in _events(path)] == ["prepared", "running"]


def test_sealed_terminal_outcome_only_refreshes_projection(tmp_path: Path) -> None:
    path = tmp_path / "run-1" / "status.json"
    path.parent.mkdir()
    initialize_execution_path(path, _status("prepared"))
    transition_execution_path(path, "running", actor="test", reason="worker started")
    before = _events(path)
    (path.parent / "final-receipt.json").write_text("{}\n", encoding="utf-8")

    with patch(
        "agent_workflow.run_lifecycle.authoritative_execution_status",
        return_value="completed",
    ):
        projected = transition_execution_path(
            path,
            "completed",
            actor="runner",
            reason="terminal evidence sealed",
            final_receipt_sha256="abc",
        )

    assert projected["status"] == "completed"
    assert projected["final_receipt_sha256"] == "abc"
    assert _events(path) == before


def test_sealed_terminal_outcome_cannot_be_reinterpreted(tmp_path: Path) -> None:
    path = tmp_path / "run-1" / "status.json"
    path.parent.mkdir()
    initialize_execution_path(path, _status("prepared"))
    (path.parent / "final-receipt.json").write_text("{}\n", encoding="utf-8")

    with patch(
        "agent_workflow.run_lifecycle.authoritative_execution_status",
        return_value="completed",
    ):
        with pytest.raises(WorkflowError, match="immutable"):
            transition_execution_path(
                path,
                "failed",
                actor="runner",
                reason="late reinterpretation",
            )
