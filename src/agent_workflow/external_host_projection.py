"""Optional-host terminal projection reconciliation.

This module is deliberately host-local.  It consumes public Agent-Workflow
views and can close a host-owned projection, but it cannot mutate an Agent
Run, its evidence, or any review/acceptance state.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .errors import WorkflowError
from .journal import JournalTransactionResult, read_jsonl, transact_jsonl
from .util import utc_now

SCHEMA = "agent-workflow/external-host-projection/v1"
EVENT_SCHEMA = "agent-workflow/external-host-projection-event/v1"
TERMINAL_STATUSES = frozenset({"completed", "failed", "interrupted", "terminated", "retired"})
STATES = frozenset({"open", "unknown", "retirement_pending", "retired"})
MAX_EVENTS = 4096


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"host projection {field} must be a non-empty string")
    return value.strip()


def _tuple_fields(item: Mapping[str, Any]) -> tuple[str, str, int]:
    run_id = _text(item.get("agent_run_id"), "agent_run_id")
    worker_id = _text(item.get("worker_id"), "worker_id")
    generation = item.get("generation")
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise WorkflowError("host projection generation must be >= 1")
    return run_id, worker_id, generation


def _validate_event(value: object, sequence: int) -> dict[str, Any]:
    if not isinstance(value, Mapping) or value.get("schema") != EVENT_SCHEMA:
        raise WorkflowError("unsupported host projection event")
    item = dict(value)
    if item.get("sequence") != sequence:
        raise WorkflowError("host projection event sequence mismatch")
    action = item.get("action")
    if action not in {"opened", "retirement_intent", "retired"}:
        raise WorkflowError("invalid host projection event action")
    _tuple_fields(item)
    if not isinstance(item.get("handle"), Mapping):
        raise WorkflowError("host projection handle must be an object")
    if action == "retirement_intent":
        _text(item.get("execution_status"), "execution_status")
    _text(item.get("recorded_at"), "recorded_at")
    return item


def _project(events: list[dict[str, Any]]) -> dict[tuple[str, str, int], dict[str, Any]]:
    records: dict[tuple[str, str, int], dict[str, Any]] = {}
    for event in events:
        key = _tuple_fields(event)
        prior = records.get(key)
        state = {"schema": SCHEMA, **{k: event[k] for k in ("agent_run_id", "worker_id", "generation", "handle")}}
        if prior:
            if prior["handle"] != event["handle"]:
                raise WorkflowError("host projection handle changed for a binding generation")
            state.update(prior)
        state["state"] = {"opened": "open", "retirement_intent": "retirement_pending", "retired": "retired"}[event["action"]]
        state["updated_at"] = event["recorded_at"]
        if event["action"] == "retirement_intent":
            state["execution_status"] = event["execution_status"]
        records[key] = state
    return records


def _binding_key(binding: Mapping[str, Any]) -> tuple[str, str, int] | None:
    if not binding.get("bound"):
        return None
    return _tuple_fields(binding | {"worker_id": binding.get("worker_id")})


@dataclass(frozen=True)
class ProjectionResult:
    """A reconciliation result suitable for host display and logging."""

    projection: dict[str, Any] | None
    execution_status: str | None
    action: str
    reason: str | None = None


class ExternalHostProjection:
    """Reconcile one host's terminal projection from public read contracts.

    ``status_reader`` and ``binding_reader`` must return the JSON objects from
    ``agent-run status`` and ``agent-run external-binding``.  ``close`` is
    called only with the exact recorded opaque handle, never with a PID.
    """

    def __init__(
        self,
        journal_path: Path,
        *,
        status_reader: Callable[[str], Mapping[str, Any]],
        binding_reader: Callable[[str], Mapping[str, Any]],
        close: Callable[[Mapping[str, Any]], None],
    ) -> None:
        self.journal_path = Path(journal_path)
        self.status_reader = status_reader
        self.binding_reader = binding_reader
        self.close = close

    def _events(self) -> list[dict[str, Any]]:
        return read_jsonl(self.journal_path, validator=_validate_event, missing_ok=True, max_records=MAX_EVENTS, sequence_field="sequence")

    def _append(self, action: str, record: Mapping[str, Any]) -> None:
        def decide(events: list[dict[str, Any]]) -> JournalTransactionResult[None]:
            event = {"schema": EVENT_SCHEMA, "sequence": len(events) + 1, "action": action, **dict(record), "recorded_at": utc_now()}
            return JournalTransactionResult(value=None, record=event)
        transact_jsonl(self.journal_path, validator=_validate_event, transaction=decide, max_records=MAX_EVENTS, sequence_field="sequence")

    def register(self, agent_run_id: str, binding: Mapping[str, Any], handle: Mapping[str, Any]) -> dict[str, Any]:
        key = _binding_key(binding)
        if key is None or key[0] != agent_run_id:
            raise WorkflowError("cannot register an unbound or mismatched external Worker")
        if not isinstance(handle, Mapping) or not handle:
            raise WorkflowError("host projection handle must be a non-empty object")
        current = _project(self._events()).get(key)
        if current:
            if dict(current["handle"]) != dict(handle):
                raise WorkflowError("host projection handle does not match its binding generation")
            return current
        self._append("opened", {"agent_run_id": key[0], "worker_id": key[1], "generation": key[2], "handle": dict(handle)})
        return _project(self._events())[key]

    def reconcile(self, agent_run_id: str, *, handle: Mapping[str, Any] | None = None) -> ProjectionResult:
        try:
            binding = self.binding_reader(agent_run_id)
            key = _binding_key(binding)
            view = self.status_reader(agent_run_id)
            status = view.get("status") if isinstance(view, Mapping) else None
        except (Exception,):
            return ProjectionResult(None, None, "unknown", "public status or binding unavailable")
        if key is None or key[0] != agent_run_id or not isinstance(status, str) or bool(view.get("stale")):
            return ProjectionResult(None, status if isinstance(status, str) else None, "unknown", "public view is missing or malformed")
        records = _project(self._events())
        projection = records.get(key)
        if projection is None:
            return ProjectionResult(None, status, "unknown", "projection handle is not registered")
        if status not in TERMINAL_STATUSES:
            if projection["state"] == "unknown":
                return ProjectionResult(projection, status, "open")
            return ProjectionResult(projection, status, "open" if projection["state"] == "open" else projection["state"])
        if projection["state"] == "retired":
            return ProjectionResult(projection, status, "noop")
        if projection["state"] != "retirement_pending":
            self._append("retirement_intent", {**{k: projection[k] for k in ("agent_run_id", "worker_id", "generation", "handle")}, "execution_status": status})
            projection = _project(self._events())[key]
        if handle is not None and dict(handle) != dict(projection["handle"]):
            return ProjectionResult(projection, status, "unknown", "host handle identity no longer matches")
        try:
            self.close(projection["handle"])
        except Exception as exc:
            return ProjectionResult(projection, status, "retirement_pending", str(exc))
        self._append("retired", {k: projection[k] for k in ("agent_run_id", "worker_id", "generation", "handle")})
        return ProjectionResult(_project(self._events())[key], status, "retired")

    def records(self) -> list[dict[str, Any]]:
        return list(_project(self._events()).values())


def status_presentation(*, worker: Mapping[str, Any], execution: Mapping[str, Any], review: Mapping[str, Any], acceptance: Mapping[str, Any], projection: Mapping[str, Any]) -> dict[str, Any]:
    """Build a display-only view with lifecycle authorities kept separate."""
    return {
        "schema": "agent-workflow/external-host-status-presentation/v1",
        "worker": dict(worker),
        "execution": dict(execution),
        "review": dict(review),
        "acceptance": dict(acceptance),
        "projection": dict(projection),
    }
