from dataclasses import replace

from agent_workflow.config import DecisionPolicyRule, defaults
from agent_workflow.decisions import validate_decision_configuration
from agent_workflow.plugin_api import (
    PluginDecisionEvidence,
    PluginDecisionMode,
    PluginDecisionProvider,
    PluginDescriptor,
)
from agent_workflow.plugins import PluginCandidate, _stage_registry
from agent_workflow.routing import advise_routing_with_policy


class _EP:
    def __init__(self, descriptor: PluginDescriptor, name: str = "semantic-test") -> None:
        self._descriptor = descriptor
        self.name = name
        self.value = "semantic_test:plugin"
        self.dist = None

    def load(self):
        return self._descriptor


def _evaluate(request, _context):
    result = {}
    for decision_id in request.decision_ids:
        if decision_id == "routing.task_class":
            result[decision_id] = PluginDecisionEvidence(
                decision_id, "success", "choice", "review", 0.95, None, {"review": 0.95}
            )
        elif decision_id == "routing.interaction_required":
            result[decision_id] = PluginDecisionEvidence(
                decision_id, "success", "noul", 0.9, None, 0.9
            )
        elif decision_id == "routing.semantic_risk":
            result[decision_id] = PluginDecisionEvidence(
                decision_id, "success", "score", 2, 0.9
            )
    return result


def _registry():
    descriptor = PluginDescriptor(
        name="semantic-test",
        version="1",
        decision_providers=(
            PluginDecisionProvider(
                "semantic-test",
                (
                    "routing.task_class",
                    "routing.interaction_required",
                    "routing.semantic_risk",
                ),
                _evaluate,
            ),
        ),
        decision_modes=(
            PluginDecisionMode(
                "semantic", "semantic automation under host policy", "semantic-test", "automated"
            ),
            PluginDecisionMode(
                "compare-semantic", "shadow semantic comparison", "semantic-test", "shadow"
            ),
        ),
    )
    ep = _EP(descriptor)
    return _stage_registry(
        (PluginCandidate("semantic-test", ep.value, None, None, ep),),
        ("semantic-test",),
    )


def test_plugin_discovered_automated_mode_composes_through_host_router():
    registry = _registry()
    settings = replace(defaults(), decision_mode="semantic")
    assert validate_decision_configuration(settings, registry)["provider"] == "semantic-test"
    result = advise_routing_with_policy(
        {"task": "review this change", "task_type": "implementation"},
        settings,
        plugin_registry=registry,
    )
    assert result["recommendation"]["agent_class"] == "review"
    assert result["recommendation"]["interactive"] is True
    assert result["decision_receipts"]["routing.semantic_risk"]["fallback"] == {
        "used": True,
        "reason": "policy_rejection",
    }


def test_plugin_discovered_shadow_mode_keeps_control_authoritative():
    registry = _registry()
    settings = replace(defaults(), decision_mode="compare-semantic")
    result = advise_routing_with_policy(
        {"task": "review this change", "task_type": "implementation"},
        settings,
        plugin_registry=registry,
    )
    assert result["recommendation"]["agent_class"] == "implementation"
    assert result["counterfactual_candidate"]["recommendation"]["agent_class"] == "review"
    assert result["decision_receipts"]["routing.task_class"]["candidate_result"] == "review"
    assert result["decision_receipts"]["routing.task_class"]["applied_result"] == "implementation"


def test_semantic_uncertainty_falls_back_to_deterministic_control():
    registry = _registry()
    settings = replace(
        defaults(),
        decision_mode="semantic",
        decision_profile="strict",
        decision_profiles={
            "strict": {
                "routing.task_class": DecisionPolicyRule("automated", 0.99),
            }
        },
    )
    result = advise_routing_with_policy(
        {"task": "review this", "task_type": "implementation"},
        settings,
        plugin_registry=registry,
    )
    receipt = result["decision_receipts"]["routing.task_class"]
    assert receipt["applied_result"] == "implementation"
    assert receipt["fallback"]["reason"] == "semantic_uncertainty"


def test_deterministic_mode_requires_no_plugin_registry():
    settings = defaults()
    result = advise_routing_with_policy(
        {"task": "review this", "task_type": "review"},
        settings,
        plugin_registry=None,
    )
    assert result["decision_mode"] == "deterministic"
    assert result["recommendation"]["agent_class"] == "review"
