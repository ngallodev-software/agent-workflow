from __future__ import annotations

import fnmatch
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
