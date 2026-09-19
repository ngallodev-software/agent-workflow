from __future__ import annotations
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

from agent_workflow._legacy_typesafe_eval import comparison_report, make_observation, validate_observation
from agent_workflow.config import defaults
from agent_workflow.comparative_eval_runtime import EvidenceStore
from agent_workflow.scheduler import SchedulerService


def _shared_library() -> ModuleType:
    module = ModuleType("agent_workflow_comparative_eval")
    module.make_observation = lambda **kwargs: make_observation(
        **{key: value for key, value in kwargs.items() if key not in {"candidate_applied", "authoritative_arm"}}
    )
    module.validate_observation = validate_observation
    module.comparison_report = comparison_report
    module.make_outcome = lambda observation_id, outcome_kind, outcome: {
        "observation_id": observation_id,
        "outcome_kind": outcome_kind,
        "outcome": dict(outcome),
    }
    return module


def test_scheduler_persists_precomputed_comparative_routing_without_raw_text(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "agent_workflow_comparative_eval", _shared_library())
    settings=replace(defaults(tmp_path / "missing.toml"),decision_mode="comparative")
    plugin=SimpleNamespace(descriptor=SimpleNamespace(name="semantic-plugin"))
    mode=SimpleNamespace(name="shadow-mode",provider="semantic",capture_comparison=True)
    registry=SimpleNamespace(decision_mode=lambda name:(plugin,mode))
    service=SchedulerService(settings=settings,run_dir=tmp_path / "workflow",workdir=tmp_path,plugin_registry=registry)
    control={"recommendation":{"agent_class":"implementation","executor":"codex","model":"gpt-5.6-luna","interactive":True},"enforced_selection":{"agent_class":"implementation","executor":"codex","model":"gpt-5.6-luna","interactive":True}}
    candidate={"recommendation":{"agent_class":"review","executor":"codex","model":"gpt-5.6-luna","interactive":False},"enforced_selection":{"agent_class":"review","executor":"codex","model":"gpt-5.6-luna","interactive":False}}
    advice={
        "deterministic_control":control,
        "counterfactual_candidate":candidate,
        "decision_receipts":{"routing.task_class":{"semantic":{"model":"jev-latest","question_set_version":"routing/v1alpha1"}}},
        "decision_timing":{"control_seconds":0.001,"provider_elapsed_seconds":0.02,"candidate_policy_seconds":0.001},
    }
    node={"workflow_id":"wf","node_id":"node","workflow_attempt":1,"ticket_id":"T1"}
    observation=service._capture_routing_comparison(node,"run-1",{"task_type":"implementation"},"secret-ish task text",advice)
    assert observation is not None
    assert observation["comparison"]["candidate_applied"] is False
    assert observation["comparison"]["authoritative_arm"] == "control"
    assert observation["identity"]["plugin"] == "semantic-plugin"
    assert observation["candidate"]["provider_elapsed_seconds"] == 0.02
    db=(tmp_path / "workflow" / "comparative-eval.sqlite")
    assert db.is_file()
    assert "secret-ish task text" not in db.read_bytes().decode("utf-8",errors="ignore")
    service._join_comparative_outcome(observation["observation_id"],{"child_completion_result":"completed","child_completion_validation_status":"valid","child_status":"completed"})
    store=EvidenceStore(db)
    try:
        assert len(store.observations()) == 1
        assert len(store.outcomes()) == 1
        reports=store.reports()
        assert len(reports) == 1
        assert reports[0]["feature_id"] == "routing-advice/v1"
    finally:
        store.close()
