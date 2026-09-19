"""Application-owned decision policy over deterministic control and plugin semantic evidence."""
from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Mapping

from . import __version__
from .config import DecisionPolicyRule, Settings
from .errors import WorkflowError
from .plugin_api import PluginDecisionContext, PluginDecisionEvidence, PluginDecisionRequest
from .plugins import EMPTY_PLUGIN_REGISTRY, PluginRegistry

DECISION_RECEIPT_SCHEMA = "agent-workflow/decision-execution-receipt/v1"

@dataclass(frozen=True)
class DecisionDefinition:
    decision_id: str
    semantic_type: str
    classification: str
    consequence: str
    automatable: bool

DECISIONS: dict[str, DecisionDefinition] = {
    "routing.task_class": DecisionDefinition("routing.task_class", "choice", "SEMANTIC_BOUNDED", "medium", True),
    "routing.interaction_required": DecisionDefinition("routing.interaction_required", "noul", "SEMANTIC_BOUNDED", "medium", True),
    "routing.semantic_risk": DecisionDefinition("routing.semantic_risk", "score", "SEMANTIC_BOUNDED", "high", False),
    "skill.behavior_satisfied": DecisionDefinition("skill.behavior_satisfied", "noul", "SEMANTIC_BOUNDED", "medium", False),
    "skill.completeness": DecisionDefinition("skill.completeness", "score", "SEMANTIC_BOUNDED", "low", False),
    "skill.actionability": DecisionDefinition("skill.actionability", "score", "SEMANTIC_BOUNDED", "low", False),
}

def mode_inventory(registry: PluginRegistry | None) -> list[dict[str, object]]:
    rows=[{"name":"deterministic","plugin":None,"provider":None,"disposition":"deterministic","summary":"built-in deterministic authority only"}]
    for plugin, mode in (registry or EMPTY_PLUGIN_REGISTRY).decision_modes:
        rows.append({"name":mode.name,"plugin":plugin.descriptor.name,"provider":mode.provider,"disposition":mode.disposition,"capture_comparison":mode.capture_comparison,"summary":mode.summary})
    return sorted(rows,key=lambda x:str(x["name"]))

def provider_inventory(registry: PluginRegistry | None) -> list[dict[str, object]]:
    return [{"name":provider.name,"plugin":plugin.descriptor.name,"decisions":list(provider.decisions)} for plugin,provider in (registry or EMPTY_PLUGIN_REGISTRY).decision_providers]

def _profile_rule(settings: Settings, decision_id: str, default_disposition: str) -> DecisionPolicyRule:
    rules=settings.decision_profiles.get(settings.decision_profile,{})
    rule=rules.get(decision_id)
    return rule if rule is not None else DecisionPolicyRule(default_disposition,0.8)

def validate_decision_configuration(settings: Settings, registry: PluginRegistry | None) -> dict[str, object]:
    if settings.decision_mode == "deterministic":
        return {"mode":"deterministic","profile":settings.decision_profile,"plugin":None,"provider":None,"valid":True}
    registry=registry or EMPTY_PLUGIN_REGISTRY
    try:
        plugin, mode=registry.decision_mode(settings.decision_mode)
        provider_plugin, provider=registry.decision_provider(mode.provider)
    except WorkflowError as exc:
        raise WorkflowError(f"decision mode {settings.decision_mode!r} is unavailable from enabled plugins: {exc}") from exc
    if provider_plugin.descriptor.name != plugin.descriptor.name:
        raise WorkflowError("decision mode may only reference a provider owned by the same plugin")
    configured_ids=set(settings.decision_profiles.get(settings.decision_profile,{}))
    unknown=sorted(configured_ids-set(DECISIONS))
    if unknown:
        raise WorkflowError("decision profile contains unknown decision IDs: "+", ".join(unknown))
    unsupported=sorted(configured_ids-set(provider.decisions))
    if unsupported:
        raise WorkflowError(f"decision provider {provider.name!r} does not support configured profile decisions: {', '.join(unsupported)}")
    result={"mode":mode.name,"profile":settings.decision_profile,"plugin":plugin.descriptor.name,"provider":provider.name,"disposition":mode.disposition,"capture_comparison":mode.capture_comparison,"valid":True}
    if mode.capture_comparison:
        from .comparative_eval import require_shared_library
        require_shared_library()
    return result

def _normalize_candidate(defn: DecisionDefinition, evidence: PluginDecisionEvidence, threshold: float) -> tuple[object|None,str|None]:
    if evidence.status != "success":
        return None,evidence.status
    if defn.semantic_type == "noul":
        p=evidence.probability if evidence.probability is not None else (float(evidence.value) if isinstance(evidence.value,(int,float)) and not isinstance(evidence.value,bool) else None)
        if p is None: return None,"invalid_contract"
        if p >= threshold: return True,None
        if p <= 1.0-threshold: return False,None
        return None,"semantic_uncertainty"
    if evidence.confidence is not None and evidence.confidence < threshold:
        return None,"semantic_uncertainty"
    value=evidence.value
    if defn.decision_id == "routing.task_class":
        mapping={"implementation":"implementation","review":"review","diagnosis":"exploratory","exploratory":"exploratory","research":"exploratory","documentation":"implementation"}
        value=mapping.get(str(value))
        if value is None: return None,"no_match"
    return value,None

def execute_decision_set(*, settings: Settings, registry: PluginRegistry | None, decision_ids: tuple[str,...], state: Mapping[str,object], control_values: Mapping[str,object]) -> dict[str,dict[str,Any]]:
    for decision_id in decision_ids:
        if decision_id not in DECISIONS: raise WorkflowError(f"unknown decision ID: {decision_id}")
        if decision_id not in control_values: raise WorkflowError(f"missing deterministic control value for {decision_id}")
    if settings.decision_mode == "deterministic":
        return {decision_id:_receipt(settings,decision_id,control_values[decision_id],None,"deterministic",control_values[decision_id],None) for decision_id in decision_ids}
    registry=registry or EMPTY_PLUGIN_REGISTRY
    plugin, mode=registry.decision_mode(settings.decision_mode)
    _provider_plugin, provider=registry.decision_provider(mode.provider)
    unsupported=sorted(set(decision_ids)-set(provider.decisions))
    if unsupported: raise WorkflowError(f"decision provider {provider.name!r} does not support: {', '.join(unsupported)}")
    request=PluginDecisionRequest(decision_ids,dict(state),dict(control_values))
    started=time.perf_counter()
    try:
        evidence_map=provider.evaluate(request,PluginDecisionContext(settings,__version__))
    except Exception as exc:
        evidence_map={decision_id:PluginDecisionEvidence(decision_id,"service_failure",DECISIONS[decision_id].semantic_type,error_class=type(exc).__name__) for decision_id in decision_ids}
    provider_elapsed=time.perf_counter()-started
    receipts={}
    for decision_id in decision_ids:
        evidence=evidence_map.get(decision_id)
        if not isinstance(evidence,PluginDecisionEvidence):
            evidence=PluginDecisionEvidence(decision_id,"invalid_contract",DECISIONS[decision_id].semantic_type,error_class="missing_evidence")
        rule=_profile_rule(settings,decision_id,mode.disposition)
        disposition=rule.disposition or mode.disposition
        candidate,fallback=_normalize_candidate(DECISIONS[decision_id],evidence,rule.minimum_confidence)
        applied=control_values[decision_id]
        if fallback is None and disposition == "automated":
            if DECISIONS[decision_id].automatable:
                applied=candidate
            else:
                fallback="policy_rejection"
        receipts[decision_id]=_receipt(settings,decision_id,control_values[decision_id],candidate,disposition,applied,fallback,evidence=evidence,plugin=plugin.descriptor.name,provider=provider.name,provider_elapsed_seconds=provider_elapsed)
    return receipts

def _receipt(settings: Settings, decision_id: str, control: object, candidate: object|None, disposition: str, applied: object, fallback: str|None, *, evidence: PluginDecisionEvidence|None=None, plugin: str|None=None, provider: str|None=None, provider_elapsed_seconds: float|None=None) -> dict[str,Any]:
    return {
        "schema":DECISION_RECEIPT_SCHEMA,"decision_id":decision_id,"decision_version":1,"classification":DECISIONS[decision_id].classification,"consequence":DECISIONS[decision_id].consequence,
        "mode":settings.decision_mode,"profile":settings.decision_profile,"control_result":control,"candidate_result":candidate,"disposition":disposition,"applied_result":applied,
        "fallback":{"used":fallback is not None,"reason":fallback},"provider":{"plugin":plugin,"name":provider,"elapsed_seconds":provider_elapsed_seconds},
        "semantic":None if evidence is None else {"status":evidence.status,"semantic_type":evidence.semantic_type,"confidence":evidence.confidence,"probability":evidence.probability,"distribution":dict(evidence.distribution),"model":evidence.model,"question_set_version":evidence.question_set_version,"request_sha256":evidence.request_sha256,"source_refs":list(evidence.source_refs),"error_class":evidence.error_class},
    }
