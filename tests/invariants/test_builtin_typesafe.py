from dataclasses import replace
from types import SimpleNamespace

from agent_workflow.config import defaults
from agent_workflow.decisions import MODES
from agent_workflow.plugin_api import DecisionContext, DecisionRequest
from agent_workflow.semantic.typesafe import SUPPORTED_DECISIONS, evaluate, project_routing


class FakeClient:
    def system_one(self, *, state, questions, model=None):
        assert set(questions) == {"task_class", "interaction_needed", "semantic_risk"}
        return SimpleNamespace(model="fake", answers={
            "task_class": SimpleNamespace(choice="review", confidence=.95, probabilities={"review": .95, "other": .05}),
            "interaction_needed": SimpleNamespace(noul=.1, probabilities={}),
            "semantic_risk": SimpleNamespace(score=1.0, confidence=.8, probabilities={0: .1, 1: .8, 2: .1}),
        })


def test_modes_are_builtin_and_typesafe_support_is_routing_only():
    assert set(MODES) == {"deterministic", "typesafe", "comparative"}
    assert set(SUPPORTED_DECISIONS) == {"routing.task_class", "routing.interaction_required", "routing.semantic_risk"}


def test_projection_redacts_secret_keys():
    state, refs = project_routing({"task": "review", "metadata": {"api_key": "secret"}, "source_refs": ["T-1"]})
    assert state["declared_metadata"]["api_key"] == "[redacted]"
    assert refs == ("T-1",)


def test_provider_normalizes_typed_answers_without_owning_policy():
    request = DecisionRequest(SUPPORTED_DECISIONS, {"task": "review", "source_refs": ["T-1"]}, {})
    evidence = evaluate(request, DecisionContext(defaults(), "0.11.0"), client=FakeClient())
    assert evidence["routing.task_class"].value == "review"
    assert evidence["routing.interaction_required"].probability == .1
    assert evidence["routing.semantic_risk"].value == 1.0
