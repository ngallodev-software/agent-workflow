from dataclasses import replace

import pytest

from agent_workflow.config import DecisionPolicyRule, defaults
from agent_workflow.decisions import require_decision_runtime_ready, validate_decision_configuration
from agent_workflow.errors import WorkflowError
from agent_workflow.plugin_api import DecisionEvidence
from agent_workflow.routing import advise_routing_with_policy


def _evaluate(request, _context):
    result = {}
    for decision_id in request.decision_ids:
        if decision_id == "routing.task_class":
            result[decision_id] = DecisionEvidence(decision_id, "success", "choice", "review", 0.95, None, {"review": 0.95})
        elif decision_id == "routing.interaction_required":
            result[decision_id] = DecisionEvidence(decision_id, "success", "noul", 0.9, None, 0.9)
        else:
            result[decision_id] = DecisionEvidence(decision_id, "success", "score", 2, 0.9)
    return result


def test_builtin_typesafe_mode_composes_through_host_router(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr("agent_workflow.semantic.typesafe.evaluate", _evaluate)
    settings = replace(defaults(), decision_mode="typesafe")
    assert validate_decision_configuration(settings)["provider"] == "typesafe"
    result = advise_routing_with_policy({"task": "review this change", "task_type": "implementation"}, settings)
    assert result["recommendation"]["agent_class"] == "review"
    assert result["recommendation"]["interactive"] is True
    assert result["decision_receipts"]["routing.semantic_risk"]["fallback"] == {"used": True, "reason": "policy_rejection"}


def test_builtin_comparative_mode_keeps_control_authoritative(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr("agent_workflow.semantic.typesafe.evaluate", _evaluate)
    settings = replace(defaults(), decision_mode="comparative")
    result = advise_routing_with_policy({"task": "review this change", "task_type": "implementation"}, settings)
    assert result["recommendation"]["agent_class"] == "implementation"
    assert result["counterfactual_candidate"]["recommendation"]["agent_class"] == "review"
    assert result["decision_receipts"]["routing.task_class"]["applied_result"] == "implementation"


def test_semantic_uncertainty_falls_back_to_control(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    monkeypatch.setattr("agent_workflow.semantic.typesafe.evaluate", _evaluate)
    settings = replace(defaults(), decision_mode="typesafe", decision_profile="strict", decision_profiles={"strict": {"routing.task_class": DecisionPolicyRule("automated", 0.99)}})
    result = advise_routing_with_policy({"task": "review this", "task_type": "implementation"}, settings)
    receipt = result["decision_receipts"]["routing.task_class"]
    assert receipt["evidence_result"] == "review"
    assert receipt["policy_candidate_result"] is None
    assert receipt["applied_result"] == "implementation"
    assert receipt["fallback"]["reason"] == "semantic_uncertainty"


def test_deterministic_mode_requires_no_semantic_provider():
    result = advise_routing_with_policy({"task": "review this", "task_type": "review"}, defaults())
    assert result["decision_mode"] == "deterministic"
    assert result["recommendation"]["agent_class"] == "review"


def test_typesafe_mode_requires_api_key_at_execution(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    settings = replace(defaults(), decision_mode="typesafe")
    with pytest.raises(WorkflowError, match="requires TYPESAFE_API_KEY"):
        advise_routing_with_policy(
            {"task": "review this", "task_type": "implementation"},
            settings,
        )


def test_comparative_mode_requires_api_key_at_execution(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    settings = replace(defaults(), decision_mode="comparative")
    with pytest.raises(WorkflowError, match="requires TYPESAFE_API_KEY"):
        advise_routing_with_policy(
            {"task": "review this", "task_type": "implementation"},
            settings,
        )


def test_decision_runtime_ready_deterministic_requires_no_semantic_runtime():
    result = require_decision_runtime_ready(defaults())
    assert result["ready"] is True
    assert result["mode"] == "deterministic"


def test_decision_runtime_ready_requires_typesafe_sdk(monkeypatch):
    monkeypatch.setattr(
        "agent_workflow.semantic.typesafe.capability",
        lambda settings: {
            "typesafe_sdk_installed": False,
            "api_key_configured": True,
        },
    )
    settings = replace(defaults(), decision_mode="typesafe")
    with pytest.raises(WorkflowError, match="requires the TypeSafe SDK"):
        require_decision_runtime_ready(settings)


def test_decision_runtime_ready_requires_api_key(monkeypatch):
    monkeypatch.setattr(
        "agent_workflow.semantic.typesafe.capability",
        lambda settings: {
            "typesafe_sdk_installed": True,
            "api_key_configured": False,
        },
    )
    settings = replace(defaults(), decision_mode="typesafe")
    with pytest.raises(WorkflowError, match="requires TYPESAFE_API_KEY"):
        require_decision_runtime_ready(settings)


def test_comparative_runtime_ready_requires_shared_library(monkeypatch):
    monkeypatch.setattr(
        "agent_workflow.semantic.typesafe.capability",
        lambda settings: {
            "typesafe_sdk_installed": True,
            "api_key_configured": True,
        },
    )
    monkeypatch.setattr(
        "agent_workflow.comparative_eval.shared_library_status",
        lambda: {
            "installed": False,
            "compatible": False,
            "version": None,
            "distribution": "agent-workflow-comparative-eval",
        },
    )
    settings = replace(defaults(), decision_mode="comparative")
    with pytest.raises(WorkflowError, match="agent-workflow-comparative-eval==0.2.0"):
        require_decision_runtime_ready(settings)


def test_comparative_runtime_ready_accepts_key_and_library(monkeypatch):
    monkeypatch.setattr(
        "agent_workflow.semantic.typesafe.capability",
        lambda settings: {
            "typesafe_sdk_installed": True,
            "api_key_configured": True,
        },
    )
    monkeypatch.setattr(
        "agent_workflow.comparative_eval.shared_library_status",
        lambda: {
            "installed": True,
            "compatible": True,
            "version": "0.2.0",
            "distribution": "agent-workflow-comparative-eval",
        },
    )
    settings = replace(defaults(), decision_mode="comparative")
    result = require_decision_runtime_ready(settings)
    assert result["ready"] is True
    assert result["mode"] == "comparative"
    assert result["typesafe"]["api_key_configured"] is True
    assert result["comparative_eval"]["compatible"] is True
