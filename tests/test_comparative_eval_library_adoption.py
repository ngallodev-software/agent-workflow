from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from agent_workflow import comparative_eval
from agent_workflow.comparative_eval_adapters import (
    CandidateUnavailable,
    skill_behavior_candidate,
    skill_behavior_control,
)
from agent_workflow.comparative_eval_runtime import (
    EvidenceStore,
    join_agent_run_outcome,
    make_precomputed_observation,
)


def _stub_shared() -> ModuleType:
    module = ModuleType("agent_workflow_comparative_eval")
    module.__version__ = "0.2.0"

    def sha256(value):
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def make_observation(**kwargs):
        control = kwargs["control"]()
        candidate = kwargs["candidate"]()
        return {
            "schema": "agent-workflow-comparative-eval/comparison-observation/v1",
            "observation_id": kwargs["observation_id"],
            "feature_id": kwargs["feature_id"],
            "mode": kwargs["mode"],
            "identity": dict(kwargs["identity"]),
            "input": {
                "case_id": kwargs.get("case_id"),
                "input_sha256": sha256(kwargs["source_input"]),
                "projection_sha256": sha256(kwargs["projected_input"]),
                "raw_input_persisted": False,
            },
            "control": {"result": control},
            "candidate": {"result": candidate},
            "comparison": {
                "candidate_applied": bool(kwargs.get("candidate_applied", False)),
                "authoritative_arm": kwargs.get("authoritative_arm", "control"),
            },
            "privacy": {
                "data_class": kwargs.get("data_class", "production-metadata"),
                "raw_content_stored": False,
                "secret_values_stored": False,
            },
        }

    def validate_observation(value):
        assert value["schema"] == "agent-workflow-comparative-eval/comparison-observation/v1"
        assert value["comparison"]["candidate_applied"] is False

    def make_outcome(observation_id, outcome_kind, value):
        return {
            "schema": "agent-workflow-comparative-eval/comparison-outcome/v1",
            "observation_id": observation_id,
            "joined_at": "test",
            "outcome_kind": outcome_kind,
            "outcome": dict(value),
        }

    def comparison_report(observations, outcomes=()):
        return {
            "schema": "agent-workflow-comparative-eval/comparison-report/v1",
            "feature_id": observations[0]["feature_id"],
            "cohort": observations[0]["identity"],
            "counts": {"observations": len(observations), "oracle_eligible": 0},
            "correctness": {
                "control_only": 0,
                "candidate_only": 0,
                "both_correct": 0,
                "both_wrong": 0,
            },
            "efficiency": {},
            "reliability": {"candidate_timeouts": 0},
            "calibration": {},
            "downstream": {"outcomes": len(outcomes)},
            "limitations": [],
        }

    module.sha256 = sha256
    module.make_observation = make_observation
    module.validate_observation = validate_observation
    module.make_outcome = make_outcome
    module.comparison_report = comparison_report
    return module


def test_base_mode_reports_optional_shared_library_absent(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "agent_workflow_comparative_eval", raising=False)
    status = comparative_eval.shared_library_status()
    assert status["installed"] is False
    assert status["compatible"] is False


def test_shared_library_delegation_and_runtime_persistence(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setitem(sys.modules, "agent_workflow_comparative_eval", _stub_shared())
    assert comparative_eval.shared_library_status()["compatible"] is True
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    observation = make_precomputed_observation(
        feature_id="routing-advice/v1",
        identity={"cohort": "x"},
        source_input={"task": "review"},
        projected_input={"task": "review"},
        control_result={"task_class": "implementation"},
        candidate_result={"task_class": "review"},
        control_duration_seconds=0.01,
        candidate_duration_seconds=0.02,
    )
    store.put_observation(observation)
    outcome = join_agent_run_outcome(
        store, observation["observation_id"], {"accepted": True}
    )
    assert outcome["schema"] == "agent-workflow-comparative-eval/comparison-outcome/v1"
    reports = store.reports()
    assert len(reports) == 1
    assert reports[0]["schema"] == "agent-workflow-comparative-eval/comparison-report/v1"
    store.close()


def test_skill_control_requires_original_patterns() -> None:
    with pytest.raises(Exception, match="control_patterns"):
        skill_behavior_control({"skill_text": "Do the thing", "oracle": {"behavior_satisfied": True}})
    assert skill_behavior_control({
        "skill_text": "Acknowledge the durable message",
        "control_patterns": [r"acknowledge.*durable message"],
        "oracle": {"behavior_satisfied": True},
    }) == {"behavior_satisfied": True}


def test_skill_candidate_projects_noul_probability() -> None:
    value = skill_behavior_candidate(
        {"oracle": {"behavior_satisfied": True}},
        {"receipt": {"status": "advisory", "answers": {"behavior_supported": {"type": "noul", "probability": 0.8}}}},
    )
    assert value == {"behavior_satisfied": True}
    with pytest.raises(CandidateUnavailable):
        skill_behavior_candidate(
            {"oracle": {"behavior_satisfied": True}},
            {"receipt": {"status": "sdk_or_key_unavailable", "answers": {}}},
        )
