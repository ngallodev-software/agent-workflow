from dataclasses import replace
import json
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
    assert state["observed"]["declared_metadata"]["api_key"] == "[redacted]"
    assert refs == ("T-1",)


def test_provider_normalizes_typed_answers_without_owning_policy():
    request = DecisionRequest(SUPPORTED_DECISIONS, {"task": "review", "source_refs": ["T-1"]}, {})
    evidence = evaluate(request, DecisionContext(defaults(), "0.11.0"), client=FakeClient())
    assert evidence["routing.task_class"].value == "review"
    assert evidence["routing.interaction_required"].probability == .1
    assert evidence["routing.semantic_risk"].value == 1.0



class FakeRequest:
    method = "POST"
    url = "https://api.typesafe.ai/v1/system-one"
    headers = {"Authorization": "Bearer should-not-leak", "Content-Type": "application/json"}
    content = json.dumps({
        "state": {"observed": {"request_text": "review"}},
        "model": "fake",
        "questions": {"task_class": {"type": "choice", "instructions": "classify", "criteria": {"review": None}}},
    }).encode()


class FakeRawResponse:
    request = FakeRequest()
    status_code = 200
    headers = {"x-typesafe-request-id": "req-123", "Set-Cookie": "should-not-leak"}
    content = json.dumps({
        "model": "fake",
        "usage": {"input_tokens": 12, "output_tokens": 4},
        "answers": {"task_class": {"type": "choice", "choice": "review", "confidence": .95, "probabilities": {"review": .95}}},
    }).encode()


class FakeAuditedResponse(SimpleNamespace):
    raw_http_response = FakeRawResponse()
    request_id = "req-123"


class FakeAuditedClient:
    def system_one(self, *, state, questions, model=None):
        return FakeAuditedResponse(model="fake", usage={"input_tokens": 12, "output_tokens": 4, "total_tokens": 16}, answers={
            "task_class": SimpleNamespace(choice="review", confidence=.95, probabilities={"review": .95, "other": .05}),
            "interaction_needed": SimpleNamespace(noul=.1, probabilities={}),
            "semantic_risk": SimpleNamespace(score=1.0, confidence=.8, probabilities={0: .1, 1: .8, 2: .1}),
        })


def test_api_call_log_captures_redacted_request_and_response(tmp_path):
    log = tmp_path / "typesafe-audit.jsonl"
    settings = replace(defaults(), typesafe_api_call_log=log)
    request = DecisionRequest(
        SUPPORTED_DECISIONS,
        {"task": "review", "metadata": {"api_key": "secret"}, "source_refs": ["T-1"]},
        {},
    )
    evidence = evaluate(request, DecisionContext(settings, "0.11.5"), client=FakeAuditedClient())
    assert evidence["routing.task_class"].value == "review"
    assert evidence["routing.task_class"].request_id == "req-123"
    assert evidence["routing.task_class"].projector_version == "routing-state/v2"
    assert evidence["routing.task_class"].usage["input_tokens"] == 12
    assert evidence["routing.task_class"].usage["provider_total_tokens"] == 16
    payload = json.loads(log.read_text(encoding="utf-8").strip())
    assert payload["schema"] == "agent-workflow/typesafe-api-call/v2"
    assert payload["request"]["logical_body"]["state"]["observed"]["declared_metadata"]["api_key"] == "[redacted]"
    assert payload["request"]["logical_body"]["questions"]["task_class"]["type"] == "choice"
    assert payload["request"]["http"]["headers"]["Authorization"] == "[redacted]"
    assert payload["request"]["http"]["body"]["model"] == "fake"
    assert payload["response"]["http"]["status_code"] == 200
    assert payload["response"]["http"]["headers"]["Set-Cookie"] == "[redacted]"
    assert payload["response"]["http"]["body"]["usage"]["input_tokens"] == 12
    assert payload["response"]["normalized"]["task_class"]["value"] == "review"
    assert payload["capture"]["raw_http_available"] is True
    assert "should-not-leak" not in log.read_text(encoding="utf-8")
