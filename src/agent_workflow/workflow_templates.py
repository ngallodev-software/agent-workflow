from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .errors import WorkflowError
from .cli_contract import AUTHORIZED_WORKFLOW_TEMPLATES
from .workflow import normalize_snapshot

AUTHORIZED_TEMPLATES = AUTHORIZED_WORKFLOW_TEMPLATES


def _task(value: Any, *, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkflowError(f"{label} must be a task node mapping")
    result = deepcopy(dict(value))
    result.pop("dependencies", None)
    result.pop("kind", None)
    result["kind"] = "task"
    return result


def expand_workflow_template(
    template: str,
    *,
    workflow_id: str,
    pack_id: str,
    pack_manifest_sha256: str,
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    """Expand one of the three authorized graph shapes deterministically."""
    if template not in AUTHORIZED_TEMPLATES:
        raise WorkflowError(
            "unsupported workflow template; choose: " + ", ".join(AUTHORIZED_TEMPLATES)
        )
    if not isinstance(parameters, Mapping):
        raise WorkflowError("workflow template parameters must be a mapping")
    nodes: list[dict[str, Any]]
    if template == "pipeline":
        raw_steps = parameters.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise WorkflowError("pipeline template requires a non-empty steps list")
        nodes = []
        previous: str | None = None
        for index, raw in enumerate(raw_steps):
            node = _task(raw, label=f"steps[{index}]")
            node["dependencies"] = [] if previous is None else [previous]
            previous = str(node.get("node_id", ""))
            nodes.append(node)
    elif template == "parallel-review-fan-in":
        subject = _task(parameters.get("subject"), label="subject")
        raw_reviews = parameters.get("reviews")
        if not isinstance(raw_reviews, list) or len(raw_reviews) < 2:
            raise WorkflowError("parallel-review-fan-in requires at least two reviews")
        reviews = [
            _task(raw, label=f"reviews[{index}]")
            for index, raw in enumerate(raw_reviews)
        ]
        fan_in = _task(parameters.get("fan_in"), label="fan_in")
        subject["dependencies"] = []
        subject_id = str(subject.get("node_id", ""))
        for review in reviews:
            review["dependencies"] = [subject_id]
        fan_in["dependencies"] = sorted(str(review.get("node_id", "")) for review in reviews)
        nodes = [subject, *reviews, fan_in]
    else:
        implementation = _task(parameters.get("implementation"), label="implementation")
        review = _task(parameters.get("review"), label="review")
        implementation["dependencies"] = []
        review["dependencies"] = [str(implementation.get("node_id", ""))]
        nodes = [implementation, review]
    return normalize_snapshot(
        {
            "workflow_id": workflow_id,
            "pack_id": pack_id,
            "pack_manifest_sha256": pack_manifest_sha256,
            "nodes": nodes,
        }
    )
