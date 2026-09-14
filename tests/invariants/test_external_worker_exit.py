from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.external_bindings import external_exit
from agent_workflow.finalization import finalize_run


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


@pytest.mark.parametrize("validation_status", ["missing", "invalid"])
def test_external_exit_refuses_recovery_without_valid_completion(
    tmp_path: Path, validation_status: str
) -> None:
    settings, run = _settings(tmp_path)
    (run / "external-worker-exit.json").write_text("{}", encoding="utf-8")
    launch = {"worktree": {"path": str(tmp_path)}, "worker_plan": {"stream_format": "text"}}
    with (
        patch("agent_workflow.finalization.run_dir", return_value=run),
        patch("agent_workflow.finalization.synchronize_projection", return_value={"agent_run_id": "run-1", "status": "running"}),
        patch("agent_workflow.finalization._already_finalized", return_value=None),
        patch("agent_workflow.finalization.read_agent_run_contract", return_value=launch),
        patch("agent_workflow.finalization.read_contract", return_value={"schema": "agent-workflow/external-worker-exit/v1"}),
        patch("agent_workflow.finalization._heartbeat_pids", return_value=(None, None)),
        patch("agent_workflow.finalization.process_sample", return_value={"alive": False}),
        patch("agent_workflow.finalization._json_object", return_value={}),
        patch("agent_workflow.finalization.collect_completion", return_value={"validation_status": validation_status}),
        patch("agent_workflow.finalization.collect_task_result") as collect_result,
        patch("agent_workflow.finalization.capture_patch") as capture_patch,
    ):
        with pytest.raises(WorkflowError, match="schema-valid completion"):
            finalize_run(settings, "run-1")
    collect_result.assert_not_called()
    capture_patch.assert_not_called()
    assert not (run / "recovery-finalization.json").exists()
    assert not (run / "final-receipt.json").exists()
