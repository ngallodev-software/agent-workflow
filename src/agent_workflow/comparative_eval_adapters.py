"""Agent-Workflow control/candidate adapters for feature-level comparison.

These functions contain host policy composition only. They do not import the
TypeSafe plugin or SDK; callers pass the plugin's public candidate telemetry as
plain mappings.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .config import Settings
from .errors import WorkflowError
from .routing import advise_routing


class CandidateUnavailable(WorkflowError):
    """The advisory candidate did not produce a semantic decision."""


def _oracle_projection(case: Mapping[str, Any], values: Mapping[str, Any]) -> dict[str, Any]:
    oracle = case.get("oracle")
    if isinstance(oracle, Mapping) and oracle:
        return {str(key): values.get(key) for key in oracle if key in values}
    return dict(values)


def _metadata_from_case(case: Mapping[str, Any]) -> dict[str, Any]:
    metadata = case.get("metadata")
    result = dict(metadata) if isinstance(metadata, Mapping) else {}
    for key in ("task_type", "risk", "requires_interaction"):
        if key in case and key not in result:
            result[key] = case[key]
    return result


def _control_task_class(agent_class: str) -> str:
    return {
        "implementation": "implementation",
        "review": "review",
        "exploratory": "diagnosis",
    }.get(agent_class, "other")


def _route_values(advice: Mapping[str, Any]) -> dict[str, Any]:
    recommendation = advice.get("recommendation")
    if not isinstance(recommendation, Mapping):
        raise WorkflowError("routing advice has no recommendation")
    return {
        "task_class": _control_task_class(str(recommendation.get("agent_class", ""))),
        "interaction_needed": bool(recommendation.get("interactive", False)),
        "final_route": dict(recommendation),
    }


def routing_control(case: Mapping[str, Any], settings: Settings) -> dict[str, Any]:
    """Project the current deterministic routing behavior onto oracle dimensions."""
    advice = advise_routing(_metadata_from_case(case), settings)
    return _oracle_projection(case, _route_values(advice))


def _receipt_from_telemetry(telemetry: Mapping[str, Any]) -> Mapping[str, Any]:
    receipt = telemetry.get("receipt")
    if not isinstance(receipt, Mapping):
        raise CandidateUnavailable("candidate telemetry has no semantic receipt")
    status = receipt.get("status")
    if status not in {"advisory", "no_match"}:
        raise CandidateUnavailable(f"semantic candidate unavailable: {status}")
    answers = receipt.get("answers")
    if not isinstance(answers, Mapping):
        raise CandidateUnavailable("semantic candidate has no answer mapping")
    return receipt


def _noul_decision(answer: object) -> bool | None:
    if not isinstance(answer, Mapping):
        return None
    value = answer.get("probability")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) >= 0.5
    value = answer.get("noul")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) >= 0.5
    return None


def routing_candidate(
    case: Mapping[str, Any],
    telemetry: Mapping[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    """Compose TypeSafe semantic advice through the same deterministic host policy.

    The semantic class is preserved as an evaluation dimension. The final route
    is a counterfactual produced by feeding only bounded semantic metadata into
    ``advise_routing``; model/executor allowlists therefore remain host-owned.
    """
    receipt = _receipt_from_telemetry(telemetry)
    answers = receipt["answers"]
    task_answer = answers.get("task_class")
    choice = task_answer.get("choice") if isinstance(task_answer, Mapping) else None
    if not isinstance(choice, str):
        raise CandidateUnavailable("semantic candidate has no task class")

    metadata = _metadata_from_case(case)
    task_type_map = {
        "implementation": "implementation",
        "diagnosis": "research",
        "review": "review",
        "documentation": "documentation",
    }
    if choice in task_type_map:
        metadata["task_type"] = task_type_map[choice]
    interaction = _noul_decision(answers.get("interaction_needed"))
    if interaction is not None:
        metadata["requires_interaction"] = interaction

    # ``other`` deliberately leaves host task metadata unchanged. It is a
    # semantic no-match, not authority to invent a route.
    advice = advise_routing(metadata, settings)
    values = _route_values(advice)
    values["task_class"] = choice
    if interaction is not None:
        values["interaction_needed"] = interaction
    return _oracle_projection(case, values)


def skill_behavior_control(case: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate a supplied original regex contract against a frozen skill case.

    The attached 0.10.1 sdist does not contain the repository skill corpus and
    the current shared TypeSafe skill dataset does not carry original regexes.
    Therefore a case must supply ``control_patterns`` (or ``skill_patterns``).
    This fails closed rather than inventing an original control behavior.
    """
    text = case.get("skill_text")
    patterns = case.get("control_patterns", case.get("skill_patterns"))
    if not isinstance(text, str):
        raise WorkflowError("skill comparison case has no skill_text")
    if not isinstance(patterns, Sequence) or isinstance(patterns, (str, bytes)) or not patterns:
        raise WorkflowError(
            "skill comparison case requires original control_patterns; "
            "the supplied source distribution does not contain the canonical skill corpus"
        )
    matched = True
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern:
            raise WorkflowError("skill control pattern must be a non-empty string")
        try:
            if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) is None:
                matched = False
        except re.error as exc:
            raise WorkflowError(f"invalid skill control regex {pattern!r}: {exc}") from exc
    return _oracle_projection(case, {"behavior_satisfied": matched})


def skill_behavior_candidate(
    case: Mapping[str, Any], telemetry: Mapping[str, Any]
) -> dict[str, Any]:
    receipt = _receipt_from_telemetry(telemetry)
    answers = receipt["answers"]
    supported = _noul_decision(answers.get("behavior_supported"))
    if supported is None:
        raise CandidateUnavailable("semantic candidate has no behavior_supported probability")
    return _oracle_projection(case, {"behavior_satisfied": supported})
