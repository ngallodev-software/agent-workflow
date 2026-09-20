from dataclasses import replace

from agent_workflow.config import DecisionPolicyRule, defaults
from agent_workflow.decisions import validate_decision_configuration
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
    monkeypatch.setattr("agent_workflow.semantic.typesafe.evaluate", _evaluate)
    settings = replace(defaults(), decision_mode="typesafe")
    assert validate_decision_configuration(settings)["provider"] == "typesafe"
    result = advise_routing_with_policy({"task": "review this change", "task_type": "implementation"}, settings)
    assert result["recommendation"]["agent_class"] == "review"
    assert result["recommendation"]["interactive"] is True
    assert result["decision_receipts"]["routing.semantic_risk"]["fallback"] == {"used": True, "reason": "policy_rejection"}


def test_builtin_comparative_mode_keeps_control_authoritative(monkeypatch):
    monkeypatch.setattr("agent_workflow.semantic.typesafe.evaluate", _evaluate)
    settings = replace(defaults(), decision_mode="comparative")
    result = advise_routing_with_policy({"task": "review this change", "task_type": "implementation"}, settings)
    assert result["recommendation"]["agent_class"] == "implementation"
    assert result["counterfactual_candidate"]["recommendation"]["agent_class"] == "review"
    assert result["decision_receipts"]["routing.task_class"]["applied_result"] == "implementation"


def test_semantic_uncertainty_falls_back_to_control(monkeypatch):
    monkeypatch.setattr("agent_workflow.semantic.typesafe.evaluate", _evaluate)
    settings = replace(defaults(), decision_mode="typesafe", decision_profile="strict", decision_profiles={"strict": {"routing.task_class": DecisionPolicyRule("automated", 0.99)}})
    result = advise_routing_with_policy({"task": "review this", "task_type": "implementation"}, settings)
    receipt = result["decision_receipts"]["routing.task_class"]
    assert receipt["applied_result"] == "implementation"
    assert receipt["fallback"]["reason"] == "semantic_uncertainty"


def test_deterministic_mode_requires_no_semantic_provider():
    result = advise_routing_with_policy({"task": "review this", "task_type": "review"}, defaults())
    assert result["decision_mode"] == "deterministic"
    assert result["recommendation"]["agent_class"] == "review"
