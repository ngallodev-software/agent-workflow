"""Application-owned policy over deterministic control and bounded semantic evidence."""
from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Any, Mapping

from . import __version__
from .config import DecisionPolicyRule, Settings
from .errors import WorkflowError
from .plugin_api import DecisionContext, DecisionEvidence, DecisionRequest

DECISION_RECEIPT_SCHEMA = "agent-workflow/decision-execution-receipt/v2"


@dataclass(frozen=True)
class DecisionDefinition:
    decision_id: str
    semantic_type: str
    classification: str
    consequence: str
    automatable: bool


@dataclass(frozen=True)
class DecisionMode:
    name: str
    provider: str | None
    disposition: str
    capture_comparison: bool
    summary: str


DECISIONS: dict[str, DecisionDefinition] = {
    "routing.task_class": DecisionDefinition("routing.task_class", "choice", "SEMANTIC_BOUNDED", "medium", True),
    "routing.interaction_required": DecisionDefinition("routing.interaction_required", "noul", "SEMANTIC_BOUNDED", "medium", True),
    "routing.semantic_risk": DecisionDefinition("routing.semantic_risk", "score", "SEMANTIC_BOUNDED", "high", False),
}

MODES: dict[str, DecisionMode] = {
    "deterministic": DecisionMode("deterministic", None, "deterministic", False, "built-in deterministic authority only"),
    "typesafe": DecisionMode("typesafe", "typesafe", "automated", False, "TypeSafe semantic evidence consumed by Agent-Workflow policy"),
    "comparative": DecisionMode("comparative", "typesafe", "shadow", True, "TypeSafe semantic evidence shadowed against deterministic control"),
}


def mode_inventory(_registry: object | None = None) -> list[dict[str, object]]:
    return [
        {"name": mode.name, "plugin": None, "provider": mode.provider, "disposition": mode.disposition,
         "capture_comparison": mode.capture_comparison, "summary": mode.summary}
        for mode in MODES.values()
    ]


def provider_inventory(_registry: object | None = None, settings: Settings | None = None) -> list[dict[str, object]]:
    from .semantic.typesafe import SUPPORTED_DECISIONS, capability
    row: dict[str, object] = {"name": "typesafe", "plugin": None, "decisions": list(SUPPORTED_DECISIONS)}
    if settings is not None:
        row["capability"] = capability(settings)
    return [row]


def _profile_rule(settings: Settings, decision_id: str, default_disposition: str) -> DecisionPolicyRule:
    rules = settings.decision_profiles.get(settings.decision_profile, {})
    rule = rules.get(decision_id)
    return rule if rule is not None else DecisionPolicyRule(default_disposition, 0.8)


def decision_mode(name: str) -> DecisionMode:
    try:
        return MODES[name]
    except KeyError as exc:
        raise WorkflowError(f"unknown decision mode: {name}") from exc


def require_decision_runtime_ready(settings: Settings) -> dict[str, object]:
    """Require the configured semantic decision runtime before an Agent Run starts."""
    mode = decision_mode(settings.decision_mode)
    result: dict[str, object] = {
        "mode": mode.name,
        "provider": mode.provider,
        "capture_comparison": mode.capture_comparison,
        "ready": True,
    }
    if mode.provider != "typesafe":
        return result

    from .semantic.typesafe import capability

    cap = capability(settings)
    result["typesafe"] = cap
    if not cap.get("typesafe_sdk_installed"):
        raise WorkflowError(
            f"decision mode {mode.name!r} requires the TypeSafe SDK in the runtime environment"
        )
    if not cap.get("api_key_configured"):
        raise WorkflowError(
            f"decision mode {mode.name!r} requires TYPESAFE_API_KEY in the runtime environment"
        )

    if mode.capture_comparison:
        from .comparative_eval import shared_library_status

        shared = shared_library_status()
        result["comparative_eval"] = shared
        if not shared.get("installed") or not shared.get("compatible"):
            raise WorkflowError(
                "comparative decision mode requires "
                "agent-workflow-comparative-eval==0.2.0 in the runtime environment"
            )
    return result


def validate_decision_configuration(settings: Settings, _registry: object | None = None) -> dict[str, object]:
    mode = decision_mode(settings.decision_mode)
    configured_ids = set(settings.decision_profiles.get(settings.decision_profile, {}))
    unknown = sorted(configured_ids - set(DECISIONS))
    if unknown:
        raise WorkflowError("decision profile contains unknown decision IDs: " + ", ".join(unknown))
    if mode.provider == "typesafe":
        from .semantic.typesafe import SUPPORTED_DECISIONS
        unsupported = sorted(configured_ids - set(SUPPORTED_DECISIONS))
        if unsupported:
            raise WorkflowError("TypeSafe provider does not support configured profile decisions: " + ", ".join(unsupported))
    result: dict[str, object] = {
        "mode": mode.name, "profile": settings.decision_profile, "plugin": None,
        "provider": mode.provider, "disposition": mode.disposition,
        "capture_comparison": mode.capture_comparison, "valid": True,
    }
    if mode.provider == "typesafe":
        from .semantic.typesafe import capability
        result["capability"] = capability(settings)
    if mode.capture_comparison:
        from .comparative_eval import require_shared_library
        require_shared_library()
    return result


def _policy_candidate(defn: DecisionDefinition, evidence: DecisionEvidence, threshold: float) -> tuple[object | None, str | None]:
    if evidence.status != "success":
        return None, evidence.status
    if defn.semantic_type == "noul":
        p = evidence.probability if evidence.probability is not None else (float(evidence.value) if isinstance(evidence.value, (int, float)) and not isinstance(evidence.value, bool) else None)
        if p is None:
            return None, "invalid_contract"
        if p >= threshold:
            return True, None
        if p <= 1.0 - threshold:
            return False, None
        return None, "semantic_uncertainty"
    if evidence.confidence is not None and evidence.confidence < threshold:
        return None, "semantic_uncertainty"
    value = evidence.value
    if defn.decision_id == "routing.task_class":
        mapping = {"implementation": "implementation", "review": "review", "diagnosis": "exploratory", "exploratory": "exploratory", "research": "exploratory", "documentation": "implementation"}
        value = mapping.get(str(value))
        if value is None:
            return None, "no_match"
    return value, None


def execute_decision_set(*, settings: Settings, registry: object | None, decision_ids: tuple[str, ...], state: Mapping[str, object], control_values: Mapping[str, object]) -> dict[str, dict[str, Any]]:
    for decision_id in decision_ids:
        if decision_id not in DECISIONS:
            raise WorkflowError(f"unknown decision ID: {decision_id}")
        if decision_id not in control_values:
            raise WorkflowError(f"missing deterministic control value for {decision_id}")
    mode = decision_mode(settings.decision_mode)
    if mode.name == "deterministic":
        return {decision_id: _receipt(settings, decision_id, control_values[decision_id], None, None, "deterministic", control_values[decision_id], None) for decision_id in decision_ids}
    if mode.provider != "typesafe":
        raise WorkflowError(f"unsupported semantic provider: {mode.provider}")
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise WorkflowError(
            f"decision mode {mode.name!r} requires TYPESAFE_API_KEY in the runtime environment"
        )
    from .semantic.typesafe import evaluate
    request = DecisionRequest(decision_ids, dict(state), dict(control_values))
    started = time.perf_counter()
    try:
        evidence_map = evaluate(request, DecisionContext(settings, __version__))
    except Exception as exc:
        evidence_map = {decision_id: DecisionEvidence(decision_id, "service_failure", DECISIONS[decision_id].semantic_type, error_class=type(exc).__name__) for decision_id in decision_ids}
    provider_elapsed = time.perf_counter() - started
    receipts: dict[str, dict[str, Any]] = {}
    for decision_id in decision_ids:
        evidence = evidence_map.get(decision_id)
        if not isinstance(evidence, DecisionEvidence):
            evidence = DecisionEvidence(decision_id, "invalid_contract", DECISIONS[decision_id].semantic_type, error_class="missing_evidence")
        rule = _profile_rule(settings, decision_id, mode.disposition)
        disposition = rule.disposition or mode.disposition
        policy_candidate, fallback = _policy_candidate(DECISIONS[decision_id], evidence, rule.minimum_confidence)
        evidence_result = evidence.value if evidence.status in {"success", "no_match"} else None
        applied = control_values[decision_id]
        if fallback is None and disposition == "automated":
            if DECISIONS[decision_id].automatable:
                applied = policy_candidate
            else:
                fallback = "policy_rejection"
        receipts[decision_id] = _receipt(settings, decision_id, control_values[decision_id], evidence_result, policy_candidate, disposition, applied, fallback, evidence=evidence, provider=mode.provider, provider_elapsed_seconds=provider_elapsed)
    return receipts


def _receipt(settings: Settings, decision_id: str, control: object, evidence_result: object | None, policy_candidate: object | None, disposition: str, applied: object, fallback: str | None, *, evidence: DecisionEvidence | None = None, provider: str | None = None, provider_elapsed_seconds: float | None = None) -> dict[str, Any]:
    return {
        "schema": DECISION_RECEIPT_SCHEMA, "decision_id": decision_id, "decision_version": 1,
        "classification": DECISIONS[decision_id].classification, "consequence": DECISIONS[decision_id].consequence,
        "mode": settings.decision_mode, "profile": settings.decision_profile, "control_result": control,
        "evidence_result": evidence_result, "policy_candidate_result": policy_candidate, "disposition": disposition, "applied_result": applied,
        "fallback": {"used": fallback is not None, "reason": fallback},
        "provider": {"name": provider, "elapsed_seconds": provider_elapsed_seconds},
        "semantic": None if evidence is None else {
            "status": evidence.status, "semantic_type": evidence.semantic_type, "confidence": evidence.confidence,
            "probability": evidence.probability, "distribution": dict(evidence.distribution), "model": evidence.model,
            "question_set_version": evidence.question_set_version, "projector_version": evidence.projector_version,
            "request_sha256": evidence.request_sha256, "request_id": evidence.request_id,
            "usage": dict(evidence.usage),
            "source_refs": list(evidence.source_refs), "error_class": evidence.error_class,
        },
    }
