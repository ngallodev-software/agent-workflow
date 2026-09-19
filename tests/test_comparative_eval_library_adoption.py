from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from agent_workflow import comparative_eval
from agent_workflow.comparative_eval_adapters import (
    CandidateUnavailable,
    routing_candidate,
    skill_behavior_candidate,
    skill_behavior_control,
)
from agent_workflow.comparative_eval_runtime import EvidenceStore, ShadowCapture, join_delayed_outcome
from agent_workflow.typesafe_eval import make_observation as legacy_make_observation
from agent_workflow.typesafe_eval_runtime import EvidenceStore as LegacyEvidenceStore


def _stub_shared() -> ModuleType:
    module = ModuleType("agent_workflow_comparative_eval")
    module.__version__ = "0.1.0"

    def sha256(value):
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode()).hexdigest()

    def observation(**kwargs):
        result = legacy_make_observation(**{k: v for k, v in kwargs.items() if k != "candidate_timeout"})
        result["schema"] = "agent-workflow-comparative-eval/comparison-observation/v1"
        return result

    def validate_observation(value):
        assert value["schema"] == "agent-workflow-comparative-eval/comparison-observation/v1"
        assert value["comparison"]["candidate_applied"] is False

    def outcome(observation_id, outcome_kind, value):
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
            "correctness": {"control_only": 0, "candidate_only": 0, "both_correct": 0, "both_wrong": 0},
            "efficiency": {}, "reliability": {"candidate_timeouts": 0},
            "calibration": {}, "downstream": {}, "limitations": [],
        }

    module.sha256 = sha256
    module.observation = observation
    module.validate_observation = validate_observation
    module.outcome = outcome
    module.comparison_report = comparison_report
    return module


def test_base_mode_preserves_legacy_import_and_emits_neutral_new_records(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "agent_workflow_comparative_eval", raising=False)
    status = comparative_eval.shared_library_status()
    assert status["backend"] == "legacy-compatibility"
    legacy = legacy_make_observation(
        feature_id="x/v1", mode="static", identity={"v": 1},
        source_input={"x": 1}, projected_input={"x": 1},
        control=lambda: {"ok": True}, candidate=lambda: {"ok": True},
    )
    assert legacy["schema"] == "agent-workflow-typesafe/comparison-observation/v1"
    neutral = comparative_eval.make_observation(
        feature_id="x/v1", mode="static", identity={"v": 1},
        source_input={"x": 1}, projected_input={"x": 1},
        control=lambda: {"ok": True}, candidate=lambda: {"ok": True},
    )
    assert neutral["schema"] == "agent-workflow-comparative-eval/comparison-observation/v1"
    comparative_eval.validate_observation(neutral)


def test_shared_library_delegation_and_runtime_persistence(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setitem(sys.modules, "agent_workflow_comparative_eval", _stub_shared())
    assert comparative_eval.shared_library_status()["backend"] == "shared"
    store = EvidenceStore(tmp_path / "evidence.sqlite")
    capture = ShadowCapture(store, enabled=True, sample_rate=1.0, seed=1)
    observation = capture.capture(
        feature_id="routing-advice/v1", identity={"cohort": "x"},
        source_input={"task": "review"}, projected_input={"task": "review"},
        control=lambda: {"task_class": "implementation"},
        candidate=lambda: {"task_class": "review"},
    )
    assert observation is not None
    assert observation["schema"] == "agent-workflow-comparative-eval/comparison-observation/v1"
    outcome = join_delayed_outcome(store, observation["observation_id"], "agent-run-outcome", {"accepted": True})
    assert outcome["schema"] == "agent-workflow-comparative-eval/comparison-outcome/v1"
    assert store.report()["schema"] == "agent-workflow-comparative-eval/comparison-report/v1"
    store.close()


def test_legacy_runtime_import_reexports_neutral_runtime() -> None:
    assert LegacyEvidenceStore is EvidenceStore


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
