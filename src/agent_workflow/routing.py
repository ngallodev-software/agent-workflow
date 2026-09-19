from __future__ import annotations

import fnmatch
import time
from typing import Any, Mapping

from .config import Settings
from .errors import WorkflowError

ROUTING_ADVICE_SCHEMA = "agent-workflow/routing-advice/v1"


def _safe_model(settings: Settings, agent_class: str, executor: str) -> str:
    class_policy = settings.agent_classes.get(agent_class)
    if class_policy is None:
        raise WorkflowError(f"unknown routing agent class: {agent_class}")
    candidates = list(class_policy.allowed_models.get(executor, ()))
    if class_policy.default_executor == executor and class_policy.default_model in candidates:
        candidates.remove(class_policy.default_model)
        candidates.insert(0, class_policy.default_model)
    executor_policy = settings.executor_policies.get(executor)
    for model in candidates:
        if executor_policy and any(
            fnmatch.fnmatchcase(model, pattern)
            for pattern in executor_policy.no_go_models
        ):
            continue
        return model
    raise WorkflowError(
        f"routing policy has no non-no-go model for class {agent_class!r} "
        f"and executor {executor!r}"
    )


def advise_routing(
    metadata: Mapping[str, Any] | None,
    settings: Settings,
    *,
    enforced_selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return deterministic advice; configuration/Agent Run enforcement stays authoritative."""
    metadata = dict(metadata or {})
    task_type = str(metadata.get("task_type", "implementation")).strip().lower()
    risk = str(metadata.get("risk", "normal")).strip().lower()
    codes: list[str] = []
    if task_type in {"research", "discovery", "exploratory", "spike"}:
        agent_class = "exploratory"
        codes.append("TASK_EXPLORATORY")
    elif task_type in {"review", "audit", "security", "verification"}:
        agent_class = "review"
        codes.append("TASK_REVIEW")
    else:
        agent_class = "implementation"
        codes.append("TASK_IMPLEMENTATION")
    if risk in {"high", "critical"} and agent_class == "implementation":
        codes.append("RISK_HIGH_IMPLEMENTATION")
    class_policy = settings.agent_classes.get(agent_class)
    if class_policy is None:
        raise WorkflowError(f"routing class is not configured: {agent_class}")
    executor = class_policy.default_executor
    model = _safe_model(settings, agent_class, executor)
    interactive = class_policy.interactive
    if metadata.get("requires_interaction") is True:
        interactive = True
        codes.append("INTERACTION_REQUIRED")
    elif metadata.get("requires_interaction") is False:
        interactive = False
        codes.append("INTERACTION_NOT_REQUIRED")
    recommendation = {
        "agent_class": agent_class,
        "executor": executor,
        "model": model,
        "interactive": interactive,
    }
    enforced = dict(recommendation)
    for key in recommendation:
        if enforced_selection and enforced_selection.get(key) is not None:
            enforced[key] = enforced_selection[key]
    disagreements = sorted(
        key for key in recommendation if recommendation[key] != enforced[key]
    )
    if disagreements:
        codes.append("ENFORCED_SELECTION_DIFFERS")
    return {
        "schema": ROUTING_ADVICE_SCHEMA,
        "recommendation": recommendation,
        "explanation_codes": sorted(set(codes)),
        "enforced_selection": enforced,
        "policy_disagreements": disagreements,
    }


def advise_routing_with_policy(
    metadata: Mapping[str, Any] | None,
    settings: Settings,
    *,
    plugin_registry: object | None = None,
    enforced_selection: Mapping[str, Any] | None = None,
    task_text: str | None = None,
    source_ref: str | None = None,
) -> dict[str, Any]:
    """Compose deterministic routing with the configured plugin-discovered decision mode.

    TypeSafe or any future semantic plugin supplies evidence only. This function remains
    the application-owned policy boundary that recomputes the final route through the
    same deterministic router used by the control arm.
    """
    from .decisions import execute_decision_set

    source = dict(metadata or {})
    control_started=time.perf_counter()
    control = advise_routing(source, settings, enforced_selection=enforced_selection)
    control_elapsed=time.perf_counter()-control_started
    risk_text = str(source.get("risk", "normal")).strip().lower()
    control_risk = 2 if risk_text in {"high", "critical"} else 0 if risk_text in {"low", "minimal"} else 1
    state = {
        "task": task_text or str(source.get("task") or source.get("text") or "workflow task"),
        "metadata": source,
        "source_refs": [source_ref] if source_ref else [],
    }
    receipts = execute_decision_set(
        settings=settings,
        registry=plugin_registry,  # type: ignore[arg-type]
        decision_ids=("routing.task_class", "routing.interaction_required", "routing.semantic_risk"),
        state=state,
        control_values={
            "routing.task_class": control["recommendation"]["agent_class"],
            "routing.interaction_required": control["recommendation"]["interactive"],
            "routing.semantic_risk": control_risk,
        },
    )

    def compose(task_class: object | None, interaction: object | None) -> dict[str, Any]:
        composed = dict(source)
        if task_class is not None:
            composed["task_type"] = {
                "exploratory": "research",
                "review": "review",
                "implementation": "implementation",
            }.get(str(task_class), "implementation")
        if interaction is not None:
            composed["requires_interaction"] = bool(interaction)
        return advise_routing(composed, settings, enforced_selection=enforced_selection)

    applied_started=time.perf_counter()
    applied = compose(
        receipts["routing.task_class"]["applied_result"],
        receipts["routing.interaction_required"]["applied_result"],
    )
    applied_policy_elapsed=time.perf_counter()-applied_started
    applied["decision_mode"] = settings.decision_mode
    applied["decision_profile"] = settings.decision_profile
    applied["decision_receipts"] = receipts
    applied["deterministic_control"] = control
    provider_elapsed=next((r.get("provider",{}).get("elapsed_seconds") for r in receipts.values() if r.get("provider",{}).get("elapsed_seconds") is not None),None)
    applied["decision_timing"]={"control_seconds":control_elapsed,"applied_policy_seconds":applied_policy_elapsed,"provider_elapsed_seconds":provider_elapsed}
    if settings.decision_mode != "deterministic":
        candidate_started=time.perf_counter()
        applied["counterfactual_candidate"] = compose(
            receipts["routing.task_class"].get("candidate_result"),
            receipts["routing.interaction_required"].get("candidate_result"),
        )
        applied["decision_timing"]["candidate_policy_seconds"]=time.perf_counter()-candidate_started
    return applied
