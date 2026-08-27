"""Host-neutral external Worker binding authority.

External host identity is operational projection data only.  The append-only
binding journal is the durable authority for reconstructing the current
binding; no host observation can transition Agent Run lifecycle, review, or
acceptance state.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Mapping

from .agent_run_paths import AgentRunPaths
from .contracts import read_agent_run_contract
from .errors import WorkflowError
from .journal import JournalTransactionResult, read_jsonl, transact_jsonl
from .state import run_dir
from .steering import pending_external_deliveries, record_external_delivery
from .util import utc_now

SCHEMA = "agent-workflow/external-worker-binding/v1"
EVENT_SCHEMA = "agent-workflow/external-worker-binding-event/v1"
MAX_EVENTS = 4096
DELIVERY_SCHEMA = "agent-workflow/external-worker-pending-delivery/v1"
DELIVERY_RESULT_SCHEMA = "agent-workflow/external-worker-delivery-result/v1"
_ACTIONS = frozenset({"bound", "observed", "unbound"})


def _journal(settings: Any, agent_run_id: str) -> Path:
    return AgentRunPaths(run_dir(settings, agent_run_id)).root / "external-worker-bindings.jsonl"


def _require_external_run(settings: Any, agent_run_id: str) -> None:
    root = run_dir(settings, agent_run_id)
    contract = read_agent_run_contract(AgentRunPaths(root).contract)
    if contract["worker_plan"].get("mode") != "external":
        raise WorkflowError("external Worker bindings require worker_mode=external")


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"external Worker binding {field} must be a non-empty string")
    return value.strip()


def _validate_event(value: object, sequence: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise WorkflowError("external Worker binding event must be an object")
    item = dict(value)
    if item.get("schema") != EVENT_SCHEMA:
        raise WorkflowError("unsupported external Worker binding event schema")
    if item.get("sequence") != sequence:
        raise WorkflowError("external Worker binding event sequence mismatch")
    action = item.get("action")
    if action not in _ACTIONS:
        raise WorkflowError("invalid external Worker binding action")
    _text(item.get("agent_run_id"), "agent_run_id")
    _text(item.get("worker_id"), "worker_id")
    if not isinstance(item.get("generation"), int) or int(item["generation"]) < 1:
        raise WorkflowError("external Worker binding generation must be >= 1")
    _text(item.get("recorded_at"), "recorded_at")
    if action in {"bound", "observed"}:
        _text(item.get("external_runtime_type"), "external_runtime_type")
        _text(item.get("external_worker_id"), "external_worker_id")
    return item


def _project(events: list[dict[str, Any]], agent_run_id: str) -> dict[str, Any]:
    if not events:
        return {
            "schema": SCHEMA,
            "agent_run_id": agent_run_id,
            "bound": False,
            "worker_id": None,
            "external_runtime_type": None,
            "external_worker_id": None,
            "generation": 0,
            "bound_at": None,
            "last_observed_at": None,
        }
    current: dict[str, Any] | None = None
    for event in events:
        if event["agent_run_id"] != agent_run_id:
            raise WorkflowError("external Worker binding journal Agent Run mismatch")
        if event["action"] == "bound":
            current = {
                "schema": SCHEMA,
                "agent_run_id": agent_run_id,
                "bound": True,
                "worker_id": event["worker_id"],
                "external_runtime_type": event["external_runtime_type"],
                "external_worker_id": event["external_worker_id"],
                "generation": event["generation"],
                "bound_at": event["recorded_at"],
                "last_observed_at": event["recorded_at"],
            }
        elif event["action"] == "observed":
            if current is None or not current["bound"]:
                raise WorkflowError("external Worker observation has no active binding")
            if event["worker_id"] != current["worker_id"] or event["generation"] != current["generation"]:
                raise WorkflowError("external Worker observation generation mismatch")
            current["last_observed_at"] = event["recorded_at"]
        else:
            if current is None:
                raise WorkflowError("external Worker unbind has no prior binding")
            if event["worker_id"] != current["worker_id"] or event["generation"] != current["generation"]:
                raise WorkflowError("external Worker unbind generation mismatch")
            current = {
                **current,
                "bound": False,
                "external_runtime_type": None,
                "external_worker_id": None,
                "last_observed_at": event["recorded_at"],
            }
    assert current is not None
    return current


def status(settings: Any, agent_run_id: str) -> dict[str, Any]:
    """Rebuild and return the current host-neutral external binding projection."""
    _require_external_run(settings, agent_run_id)
    events = read_jsonl(
        _journal(settings, agent_run_id),
        validator=_validate_event,
        missing_ok=True,
        max_records=MAX_EVENTS,
        sequence_field="sequence",
    )
    return _project(events, agent_run_id)


def bind(
    settings: Any,
    agent_run_id: str,
    *,
    external_runtime_type: str,
    external_worker_id: str,
) -> dict[str, Any]:
    """Idempotently bind or rebind an external host Worker to an Agent Run."""
    _require_external_run(settings, agent_run_id)
    runtime_type = _text(external_runtime_type, "external_runtime_type")
    external_id = _text(external_worker_id, "external_worker_id")

    def decide(events: list[dict[str, Any]]) -> JournalTransactionResult[dict[str, Any]]:
        projection = _project(events, agent_run_id)
        if (
            projection["bound"]
            and projection["external_runtime_type"] == runtime_type
            and projection["external_worker_id"] == external_id
        ):
            return JournalTransactionResult(value=projection)
        worker_id = projection.get("worker_id") or f"worker-{uuid.uuid4().hex}"
        generation = int(projection.get("generation") or 0) + 1
        now = utc_now()
        record = {
            "schema": EVENT_SCHEMA,
            "sequence": len(events) + 1,
            "action": "bound",
            "agent_run_id": agent_run_id,
            "worker_id": worker_id,
            "external_runtime_type": runtime_type,
            "external_worker_id": external_id,
            "generation": generation,
            "recorded_at": now,
        }
        value = {
            "schema": SCHEMA,
            "agent_run_id": agent_run_id,
            "bound": True,
            "worker_id": worker_id,
            "external_runtime_type": runtime_type,
            "external_worker_id": external_id,
            "generation": generation,
            "bound_at": now,
            "last_observed_at": now,
        }
        return JournalTransactionResult(value=value, record=record)

    return transact_jsonl(
        _journal(settings, agent_run_id),
        validator=_validate_event,
        transaction=decide,
        max_records=MAX_EVENTS,
        sequence_field="sequence",
    )


def observe(settings: Any, agent_run_id: str) -> dict[str, Any]:
    """Record a host observation without changing Agent Run lifecycle authority."""
    _require_external_run(settings, agent_run_id)

    def decide(events: list[dict[str, Any]]) -> JournalTransactionResult[dict[str, Any]]:
        projection = _project(events, agent_run_id)
        if not projection["bound"]:
            raise WorkflowError("external Worker is not bound")
        now = utc_now()
        record = {
            "schema": EVENT_SCHEMA,
            "sequence": len(events) + 1,
            "action": "observed",
            "agent_run_id": agent_run_id,
            "worker_id": projection["worker_id"],
            "external_runtime_type": projection["external_runtime_type"],
            "external_worker_id": projection["external_worker_id"],
            "generation": projection["generation"],
            "recorded_at": now,
        }
        return JournalTransactionResult(
            value={**projection, "last_observed_at": now},
            record=record,
        )

    return transact_jsonl(
        _journal(settings, agent_run_id),
        validator=_validate_event,
        transaction=decide,
        max_records=MAX_EVENTS,
        sequence_field="sequence",
    )


def unbind(settings: Any, agent_run_id: str) -> dict[str, Any]:
    """Idempotently remove the current host binding while retaining its history."""
    _require_external_run(settings, agent_run_id)

    def decide(events: list[dict[str, Any]]) -> JournalTransactionResult[dict[str, Any]]:
        projection = _project(events, agent_run_id)
        if not projection["bound"]:
            return JournalTransactionResult(value=projection)
        now = utc_now()
        record = {
            "schema": EVENT_SCHEMA,
            "sequence": len(events) + 1,
            "action": "unbound",
            "agent_run_id": agent_run_id,
            "worker_id": projection["worker_id"],
            "generation": projection["generation"],
            "recorded_at": now,
        }
        value = {
            **projection,
            "bound": False,
            "external_runtime_type": None,
            "external_worker_id": None,
            "last_observed_at": now,
        }
        return JournalTransactionResult(value=value, record=record)

    return transact_jsonl(
        _journal(settings, agent_run_id),
        validator=_validate_event,
        transaction=decide,
        max_records=MAX_EVENTS,
        sequence_field="sequence",
    )


def _require_generation(settings: Any, agent_run_id: str, generation: int) -> dict[str, Any]:
    projection = status(settings, agent_run_id)
    if not projection["bound"]:
        raise WorkflowError("external Worker is not bound")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 1:
        raise WorkflowError("external Worker binding generation must be >= 1")
    if generation != projection["generation"]:
        raise WorkflowError("external Worker binding generation is stale")
    return projection


def pending_delivery(
    settings: Any, agent_run_id: str, *, generation: int
) -> dict[str, Any]:
    """Return messages pending host delivery for the active binding generation."""
    projection = _require_generation(settings, agent_run_id, generation)
    items = pending_external_deliveries(run_dir(settings, agent_run_id))
    return {
        "schema": DELIVERY_SCHEMA,
        "agent_run_id": agent_run_id,
        "worker_id": projection["worker_id"],
        "generation": projection["generation"],
        "messages": items,
    }


def report_delivery(
    settings: Any,
    agent_run_id: str,
    *,
    generation: int,
    correlation_id: str,
    outcome: str,
    attempt: int,
    reason: str,
) -> dict[str, Any]:
    """Record host transport evidence without recording acknowledgement."""
    projection = _require_generation(settings, agent_run_id, generation)
    event = record_external_delivery(
        run_dir(settings, agent_run_id),
        correlation_id=correlation_id,
        outcome=outcome,
        attempt=attempt,
        reason=reason,
    )
    return {
        "schema": DELIVERY_RESULT_SCHEMA,
        "agent_run_id": agent_run_id,
        "worker_id": projection["worker_id"],
        "generation": projection["generation"],
        "correlation_id": correlation_id,
        "delivery": event,
        "acknowledged": event["outcome"] in {"applied", "rejected"},
    }
