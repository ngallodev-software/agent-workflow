"""Optional TypeSafe provider for Agent-Workflow bounded routing judgments.

The provider is deliberately thin: deterministic projection and versioned question
specifications live here, the official SDK supplies Choice/Noul/Score transport, and
Agent-Workflow's decision policy remains authoritative over every result.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any, Protocol

from ..plugin_api import DecisionContext, DecisionEvidence, DecisionRequest

QUESTION_SET_VERSION = "routing/v1alpha1"
SUPPORTED_DECISIONS = (
    "routing.task_class",
    "routing.interaction_required",
    "routing.semantic_risk",
)
_SECRET_MARKERS = ("api_key", "apikey", "authorization", "password", "secret", "token")
_MAX_TEXT = 8_000
_MAX_ITEMS = 100
_MAX_DEPTH = 8

# Application-owned, SDK-independent specifications. The adapter below lowers these
# definitions to the official SDK primitives only when a live TypeSafe call is made.
QUESTION_SPECS: dict[str, dict[str, object]] = {
    "routing.task_class": {
        "primitive": "choice",
        "answer_key": "task_class",
        "instructions": "Classify this task by its primary requested work. Choose other when no listed class fits.",
        "criteria": {
            "implementation": "Change product code or configuration.",
            "diagnosis": "Investigate a failure without changing product behavior.",
            "review": "Assess existing evidence or changes.",
            "documentation": "Create or revise explanatory material.",
            "other": "No listed task class applies.",
        },
    },
    "routing.interaction_required": {
        "primitive": "noul",
        "answer_key": "interaction_needed",
        "instructions": "Would completing this task require a material user decision or authorization not present in the supplied task?",
    },
    "routing.semantic_risk": {
        "primitive": "score",
        "answer_key": "semantic_risk",
        "instructions": "Assess the semantic consequence of misunderstanding this task, using the ordered rubric.",
        "criteria": [
            "Low consequence; easily reversible.",
            "Moderate consequence; requires careful verification.",
            "High consequence; could affect authority, security, or irreversible state.",
        ],
    },
}


class TypeSafeClientLike(Protocol):
    def system_one(self, *, state: Mapping[str, object], questions: Mapping[str, object], model: str | None = None) -> Any: ...


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _safe(value: Any, *, key: str = "", depth: int = 0) -> Any:
    normalized = key.lower().replace("-", "_")
    if any(marker in normalized for marker in _SECRET_MARKERS):
        return "[redacted]"
    if depth >= _MAX_DEPTH:
        return "[depth_limit]"
    if isinstance(value, str):
        return value[:_MAX_TEXT]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Mapping):
        return {str(k)[:200]: _safe(v, key=str(k), depth=depth + 1) for k, v in list(value.items())[:_MAX_ITEMS]}
    if isinstance(value, (list, tuple)):
        return [_safe(v, depth=depth + 1) for v in value[:_MAX_ITEMS]]
    return f"[unsupported:{type(value).__name__}]"


def project_routing(source: Mapping[str, object]) -> tuple[dict[str, object], tuple[str, ...]]:
    text = source.get("task") or source.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("routing semantic input requires non-empty task or text")
    refs = source.get("source_refs", [])
    if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
        raise ValueError("source_refs must be a list of stable strings")
    return {"task": _safe(text), "declared_metadata": _safe(source.get("metadata", {}))}, tuple(refs)


def _request_hash(state: Mapping[str, object], decision_ids: tuple[str, ...], model: str | None) -> str:
    specs = {decision_id: QUESTION_SPECS[decision_id] for decision_id in decision_ids}
    payload = {"state": state, "questions": specs, "question_set_version": QUESTION_SET_VERSION, "requested_model": model}
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def question_specs(decision_ids: tuple[str, ...]) -> dict[str, dict[str, object]]:
    """Return SDK-independent, versioned question definitions for hashing/tests."""
    return {decision_id: dict(QUESTION_SPECS[decision_id]) for decision_id in decision_ids}


def _sdk_questions(decision_ids: tuple[str, ...]) -> dict[str, object]:
    try:
        from typesafe_sdk import Choice, Noul, Score
    except ImportError as exc:
        raise RuntimeError("typesafe_sdk_unavailable") from exc
    result: dict[str, object] = {}
    for decision_id in decision_ids:
        spec = QUESTION_SPECS[decision_id]
        key = str(spec["answer_key"])
        primitive = spec["primitive"]
        if primitive == "choice":
            result[key] = Choice(instructions=str(spec["instructions"]), criteria=dict(spec["criteria"]))
        elif primitive == "noul":
            result[key] = Noul(instructions=str(spec["instructions"]))
        elif primitive == "score":
            result[key] = Score(instructions=str(spec["instructions"]), criteria=list(spec["criteria"]))
        else:  # guarded by the static registry above
            raise ValueError(f"unsupported TypeSafe primitive: {primitive}")
    return result


def _client() -> TypeSafeClientLike:
    try:
        from typesafe_sdk import TypeSafeClient
    except ImportError as exc:
        raise RuntimeError("typesafe_sdk_unavailable") from exc
    return TypeSafeClient()


def _answers(response: Any) -> Mapping[str, object]:
    answers = getattr(response, "answers", None)
    if isinstance(answers, Mapping):
        return answers
    # SDK 0.6 exposes typed collections as well; accept those without leaking
    # vendor response objects past this adapter.
    merged: dict[str, object] = {}
    for name in ("choices", "nouls", "scores"):
        values = getattr(response, name, None)
        if isinstance(values, Mapping):
            merged.update(values)
    if not merged:
        raise ValueError("TypeSafe response has no typed answer mapping")
    return merged


def _record_call(settings: Any, *, request_sha256: str, state: object, decision_ids: tuple[str, ...], status: str,
                 requested_model: str | None, resolved_model: str | None = None, outputs: object | None = None,
                 error_class: str | None = None, duration_ms: float | None = None) -> None:
    path = getattr(settings, "typesafe_api_call_log", None)
    if path is None:
        return
    try:
        payload: dict[str, Any] = {
            "schema": "agent-workflow/typesafe-api-call/v1",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_sha256": request_sha256,
            "question_set_version": QUESTION_SET_VERSION,
            "requested_model": requested_model,
            "resolved_model": resolved_model,
            "input": {"state": _safe(state), "decision_ids": list(decision_ids)},
            "output": _safe(outputs),
            "status": status,
        }
        if error_class:
            payload["error_class"] = error_class
        if duration_ms is not None:
            payload["duration_ms"] = round(max(0.0, duration_ms), 3)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    except (OSError, TypeError, ValueError):
        return


def evaluate(request: DecisionRequest, context: DecisionContext, *, client: TypeSafeClientLike | None = None) -> dict[str, DecisionEvidence]:
    decision_ids = tuple(request.decision_ids)
    unsupported = sorted(set(decision_ids) - set(SUPPORTED_DECISIONS))
    if unsupported:
        raise ValueError("TypeSafe provider does not support: " + ", ".join(unsupported))
    try:
        state, source_refs = project_routing(request.state)
    except ValueError as exc:
        return {decision_id: DecisionEvidence(decision_id, "invalid_input", str(QUESTION_SPECS[decision_id]["primitive"]), error_class=type(exc).__name__) for decision_id in decision_ids}
    model = getattr(context.settings, "typesafe_model", None)
    digest = _request_hash(state, decision_ids, model)
    if client is None and not os.environ.get("TYPESAFE_API_KEY"):
        return {decision_id: DecisionEvidence(decision_id, "service_failure", str(QUESTION_SPECS[decision_id]["primitive"]), question_set_version=QUESTION_SET_VERSION, request_sha256=digest, source_refs=source_refs, error_class="typesafe_api_key_unavailable") for decision_id in decision_ids}
    started = monotonic()
    try:
        sdk_questions = _sdk_questions(decision_ids) if client is None else {str(QUESTION_SPECS[d]["answer_key"]): QUESTION_SPECS[d] for d in decision_ids}
        response = (client or _client()).system_one(state=state, questions=sdk_questions, model=model)
        answers = _answers(response)
        resolved_model = getattr(response, "model", None)
    except Exception as exc:
        _record_call(context.settings, request_sha256=digest, state=state, decision_ids=decision_ids, status="service_failure", requested_model=model, error_class=type(exc).__name__, duration_ms=(monotonic() - started) * 1000)
        return {decision_id: DecisionEvidence(decision_id, "service_failure", str(QUESTION_SPECS[decision_id]["primitive"]), question_set_version=QUESTION_SET_VERSION, request_sha256=digest, source_refs=source_refs, error_class=type(exc).__name__) for decision_id in decision_ids}

    result: dict[str, DecisionEvidence] = {}
    normalized_outputs: dict[str, object] = {}
    for decision_id in decision_ids:
        spec = QUESTION_SPECS[decision_id]
        semantic_type = str(spec["primitive"])
        answer = answers.get(str(spec["answer_key"]))
        if answer is None:
            result[decision_id] = DecisionEvidence(decision_id, "invalid_contract", semantic_type, model=resolved_model if isinstance(resolved_model, str) else None, question_set_version=QUESTION_SET_VERSION, request_sha256=digest, source_refs=source_refs, error_class="missing_answer")
            continue
        value = confidence = probability = None
        distribution: dict[str, float] = {}
        status = "success"
        if semantic_type == "choice":
            value = getattr(answer, "choice", None)
            confidence = getattr(answer, "confidence", None)
            probs = getattr(answer, "probabilities", {})
            if value == "other":
                status = "no_match"
        elif semantic_type == "noul":
            probability = getattr(answer, "noul", None)
            value = probability
            probs = getattr(answer, "probabilities", {})
        else:
            value = getattr(answer, "score", None)
            confidence = getattr(answer, "confidence", None)
            probs = getattr(answer, "probabilities", {})
        if isinstance(probs, Mapping):
            distribution = {str(k): float(v) for k, v in probs.items() if isinstance(v, (int, float))}
        normalized_outputs[str(spec["answer_key"])] = {"type": semantic_type, "value": value, "confidence": confidence, "probability": probability, "probabilities": distribution}
        result[decision_id] = DecisionEvidence(
            decision_id, status, semantic_type, value=value,
            confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
            probability=float(probability) if isinstance(probability, (int, float)) else None,
            distribution=distribution,
            model=resolved_model if isinstance(resolved_model, str) else None,
            question_set_version=QUESTION_SET_VERSION, request_sha256=digest, source_refs=source_refs,
        )
    _record_call(context.settings, request_sha256=digest, state=state, decision_ids=decision_ids, status="success", requested_model=model, resolved_model=resolved_model if isinstance(resolved_model, str) else None, outputs=normalized_outputs, duration_ms=(monotonic() - started) * 1000)
    return result


def capability(settings: Any) -> dict[str, object]:
    import importlib.util
    return {
        "provider": "typesafe",
        "typesafe_sdk_installed": importlib.util.find_spec("typesafe_sdk") is not None,
        "api_key_configured": bool(os.environ.get("TYPESAFE_API_KEY")),
        "model": getattr(settings, "typesafe_model", None),
        "question_set_version": QUESTION_SET_VERSION,
        "decisions": list(SUPPORTED_DECISIONS),
    }
