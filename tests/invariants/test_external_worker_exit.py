from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.external_bindings import external_exit
from agent_workflow.terminal_pipeline import TerminalObservation, derive_terminal_outcome


def _settings(tmp_path: Path):
    settings = defaults(tmp_path / "config.toml")
    object.__setattr__(settings, "state_root", tmp_path / "state")
    run = settings.state_root / "runs" / "run-1"
    run.mkdir(parents=True)
    (run / "agent-run-contract.json").write_text(
        json.dumps({"worker_plan": {"mode": "external"}}), encoding="utf-8"
    )
    return settings, run


def test_external_exit_is_authorized_generation_bound_and_idempotent(tmp_path: Path) -> None:
    settings, run = _settings(tmp_path)
    binding = {
        "bound": True, "worker_id": "worker-1", "generation": 4,
        "external_runtime_type": "host", "external_worker_id": "host-1",
    }
    with patch("agent_workflow.external_bindings._require_external_run"), \
         patch("agent_workflow.external_bindings.status", return_value=binding), \
         patch("agent_workflow.external_bindings.authoritative_execution_status", return_value="running"):
        first = external_exit(settings, "run-1", generation=4, actor="operator", reason="host confirmed exit")
        second = external_exit(settings, "run-1", generation=4, actor="different", reason="replay")
    assert second == first
    assert first["completion_reported"] is True
    assert first["exit_observed"] is True
    assert "pid" not in first and "returncode" not in first
    assert json.loads((run / "external-worker-exit.json").read_text()) == first


@pytest.mark.parametrize("status", ["prepared", "completed", "failed"])
def test_external_exit_requires_current_running_binding(tmp_path: Path, status: str) -> None:
    settings, _ = _settings(tmp_path)
    binding = {"bound": True, "worker_id": "worker-1", "generation": 1}
    with patch("agent_workflow.external_bindings._require_external_run"), \
         patch("agent_workflow.external_bindings.status", return_value=binding), \
         patch("agent_workflow.external_bindings.authoritative_execution_status", return_value=status):
        with pytest.raises(WorkflowError, match="running"):
            external_exit(settings, "run-1", generation=1, actor="operator", reason="exit")


@pytest.mark.parametrize(
    ("binding", "generation", "message"),
    [
        ({"bound": False, "generation": 1}, 1, "not bound"),
        ({"bound": True, "generation": 2}, 1, "stale"),
    ],
)
def test_external_exit_rejects_unbound_and_stale_generation(
    tmp_path: Path, binding: dict[str, object], generation: int, message: str
) -> None:
    settings, _ = _settings(tmp_path)
    with patch("agent_workflow.external_bindings.status", return_value=binding):
        with pytest.raises(WorkflowError, match=message):
            external_exit(settings, "run-1", generation=generation, actor="operator", reason="exit")


def test_external_exit_rejects_sealed_run(tmp_path: Path) -> None:
    settings, _ = _settings(tmp_path)
    binding = {"bound": True, "worker_id": "worker-1", "generation": 1}
    with patch("agent_workflow.external_bindings.status", return_value=binding), \
         patch("agent_workflow.external_bindings.authoritative_execution_status", return_value="completed"):
        with pytest.raises(WorkflowError, match="running"):
            external_exit(settings, "run-1", generation=1, actor="operator", reason="exit")


@pytest.mark.parametrize(
    ("validation_status", "failure_category"),
    [("missing", "completion_missing"), ("invalid", "completion_invalid")],
)
def test_external_exit_cannot_produce_completed_outcome_without_valid_completion(
    validation_status: str, failure_category: str
) -> None:
    outcome = derive_terminal_outcome(
        TerminalObservation(
            executor_result="completed",
            exit_code=None,
            failure_category="external_exit_observed",
        ),
        completion_result=validation_status,
        policy_result="passed",
    )

    assert outcome.status == "failed"
    assert outcome.acceptance_eligible is False
    assert outcome.failure_category == failure_category
    assert outcome.exit_code == 1
