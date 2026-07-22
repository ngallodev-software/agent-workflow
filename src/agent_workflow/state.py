from __future__ import annotations
from typing import Any
from .config import Settings
from .errors import WorkflowError
from .events import append_lifecycle_event
from .migrations import migrate_contract
from .util import atomic_write_json, read_json, validate_id

TERMINAL_STATUSES = {
    "completed",
    "failed",
    "interrupted",
    "killed",
}

STATUS_SCHEMA = "agent-workflow/session-status/v2"


def _current(data: dict[str, Any]) -> dict[str, Any]:
    if "schema" not in data:
        data = {"schema": "agent-workflow/session-status/v1", **data}
    return migrate_contract(data, STATUS_SCHEMA)


def runs_root(settings: Settings):
    root = settings.state_root / "runs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def run_dir(settings: Settings, session_id: str):
    validate_id(session_id, "session ID")
    return runs_root(settings) / session_id


def status_path(settings: Settings, session_id: str):
    return run_dir(settings, session_id) / "status.json"


def read_status(settings: Settings, session_id: str):
    return _current(read_json(status_path(settings, session_id)))


def write_status(settings: Settings, session_id: str, data: dict[str, Any]):
    current = _current(data)
    append_lifecycle_event(
        run_dir(settings, session_id),
        dimension="execution",
        prior=None,
        new=current.get("status"),
        actor="agent-workflow",
        reason="status initialized",
    )
    atomic_write_json(status_path(settings, session_id), current)


def update_status(settings: Settings, session_id: str, **changes: Any):
    path = status_path(settings, session_id)
    if not path.exists():
        raise WorkflowError(f"unknown session: {session_id}")
    data = _current(read_json(path))
    actor = str(changes.pop("_actor", "agent-workflow"))
    reason = str(changes.pop("_reason", "status updated"))
    receipt_refs = changes.pop("_receipt_refs", ())
    if "status" in changes and changes["status"] != data.get("status"):
        append_lifecycle_event(
            path.parent,
            dimension="execution",
            prior=data.get("status"),
            new=changes["status"],
            actor=actor,
            reason=reason,
            receipt_refs=receipt_refs,
        )
    if "disposition" in changes and changes["disposition"] != data.get("disposition"):
        append_lifecycle_event(
            path.parent,
            dimension="review",
            prior=data.get("disposition"),
            new=changes["disposition"],
            actor=actor,
            reason=reason,
            receipt_refs=receipt_refs,
        )
    data.update(changes)
    atomic_write_json(path, data)
    return data


def list_statuses(settings: Settings):
    items = []
    for path in sorted(runs_root(settings).glob("*/status.json")):
        try:
            items.append(_current(read_json(path)))
        except WorkflowError as exc:
            items.append(
                {
                    "schema": STATUS_SCHEMA,
                    "session_id": path.parent.name,
                    "status": "failed",
                    "failure_category": "corrupt_status",
                    "error": str(exc),
                    "status_path": str(path),
                }
            )
    return items
