"""Durable assignment identity for an Agent Run worker."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import WorkflowError
from .journal import JournalTransactionResult, transact_jsonl
from .events import append_lifecycle_event
from .messages import append_message
from .path import read_regular_file
from .state import list_statuses, run_dir
from .protocol_values import ASSIGNMENT_EVENTS, ASSIGNMENT_STATES
from .util import atomic_write_json, expand_path, sha256_file, utc_now, validate_id

CONTEXT_SCHEMA = "agent-workflow/agent-context/v1"
ASSIGNMENT_SCHEMA = "agent-workflow/assignment-event/v1"
CONTEXT_NAME = "agent-context.json"
LEDGER_NAME = "assignments.jsonl"
MAX_SUMMARY_CHARS = 4096
MAX_ITEMS = 64

_ASSIGNMENT_TRANSITIONS: dict[tuple[str, str], str] = {
    ("busy", "task_completed"): "closed",
}


def _assignment_next_state(current: str, event: str) -> str:
    if current not in ASSIGNMENT_STATES:
        raise WorkflowError(f"unsupported assignment state: {current!r}")
    if event not in ASSIGNMENT_EVENTS:
        raise WorkflowError(f"unsupported assignment event: {event!r}")
    try:
        return _ASSIGNMENT_TRANSITIONS[(current, event)]
    except KeyError as exc:
        raise WorkflowError(
            f"assignment event {event!r} is not allowed from state {current!r}"
        ) from exc


def _close_assignment(
    state_dir: Path,
    context: dict[str, Any],
    *,
    agent_run_id: str,
    actor: str,
    summary: str,
    tags: list[str],
    files: list[str],
    lifecycle_reason: str,
    emit_message: bool,
) -> dict[str, Any]:
    """Execute the fixed busy -> closed assignment transition sequence."""
    current_state = str(context.get("state"))
    next_state = _assignment_next_state(current_state, "task_completed")
    assignment = context.get("current_assignment")
    if not isinstance(assignment, dict):
        raise WorkflowError("agent has no current assignment")
    completed = {
        **dict(assignment),
        "completed_at": utc_now(),
        "summary": summary,
        "tags": tags,
        "files": files,
    }
    event = _append_event(
        state_dir,
        {
            "event": "task_completed",
            "agent_run_id": agent_run_id,
            "assignment_id": completed["assignment_id"],
            "actor": actor,
            "ticket_id": completed.get("ticket_id"),
            "pack_id": completed.get("pack_id"),
            "correlation_id": None,
            "summary": summary,
            "tags": tags,
            "files": files,
        },
    )
    context["completed_assignment"] = completed
    context["current_assignment"] = None
    context["state"] = next_state
    context["updated_at"] = event["timestamp"]
    atomic_write_json(state_dir / CONTEXT_NAME, context)
    append_lifecycle_event(
        state_dir,
        dimension="assignment",
        prior=current_state,
        new=next_state,
        actor=actor,
        reason=lifecycle_reason,
        receipt_refs=[LEDGER_NAME, CONTEXT_NAME],
    )
    if emit_message:
        append_message(
            state_dir,
            agent_run_id=agent_run_id,
            direction="child_to_parent",
            kind="task_complete",
            actor=actor,
            content=summary,
        )
    return context


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(read_regular_file(path, max_bytes=1024 * 1024).data.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
        raise WorkflowError(f"cannot read agent context {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != CONTEXT_SCHEMA:
        raise WorkflowError(f"invalid agent context: {path}")
    return value


def _validate_assignment_record(value: object, line_number: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError("assignment event must be a JSON object")
    # Assignment writes/replays retain full schema validation, but the normal
    # read-only `agent context` path does not need to import JSON Schema machinery.
    from .contracts import validate_instance

    validate_instance(value, ASSIGNMENT_SCHEMA, artifact=f"assignment event:{line_number}")
    if value.get("sequence") != line_number:
        raise WorkflowError(
            f"assignment event sequence mismatch: expected {line_number}, got {value.get('sequence')!r}"
        )
    return value


def _append_event(state_dir: Path, event: dict[str, Any]) -> dict[str, Any]:
    path = state_dir / LEDGER_NAME

    def decide(existing: list[dict[str, Any]]) -> JournalTransactionResult[dict[str, Any]]:
        record = {
            "schema": ASSIGNMENT_SCHEMA,
            "sequence": len(existing) + 1,
            "timestamp": utc_now(),
            **event,
        }
        record = _validate_assignment_record(record, len(existing) + 1)
        return JournalTransactionResult(value=record, record=record)

    return transact_jsonl(
        path,
        validator=_validate_assignment_record,
        transaction=decide,
        sequence_field="sequence",
    )


def initialize(
    state_dir: Path,
    *,
    agent_run_id: str,
    status: dict[str, Any],
) -> dict[str, Any]:
    assignment_id = str(uuid.uuid4())
    now = utc_now()
    assignment = {
        "assignment_id": assignment_id,
        "ticket_id": status.get("ticket_id"),
        "pack_id": status.get("pack_id"),
        "retry_of_agent_run_id": status.get("retry_of_agent_run_id"),
        "prompt_path": status.get("prompt_path"),
        "prompt_sha256": status.get("prompt_sha256"),
        "started_at": now,
    }
    context = {
        "schema": CONTEXT_SCHEMA,
        "agent_run_id": agent_run_id,
        "agent_name": status.get("agent_name"),
        "agent_class": status.get("agent_class"),
        "role": status.get("role"),
        "role_digest": status.get("role_digest"),
        "interactive": bool(status.get("worker_mode") == "external"),
        "worker_mode": status.get("worker_mode"),
        "provider_agent_run_id": None,
        "repository_root": status.get("repository_root"),
        "worktree": str(Path(str(status["workdir"])).resolve()),
        "source_revision": status.get("source_revision"),
        "state": "busy",
        "current_assignment": assignment,
        "completed_assignment": None,
        "created_at": now,
        "updated_at": now,
    }
    _append_event(state_dir, {
        "event": "assigned",
        "agent_run_id": agent_run_id,
        "assignment_id": assignment_id,
        "actor": "agent-workflow",
        "ticket_id": status.get("ticket_id"),
        "pack_id": status.get("pack_id"),
        "correlation_id": None,
    })
    atomic_write_json(state_dir / CONTEXT_NAME, context)
    return context


def read(settings: Settings, agent_run_id: str) -> dict[str, Any]:
    validate_id(agent_run_id, "agent run ID")
    value = _read_json(run_dir(settings, agent_run_id) / CONTEXT_NAME)
    if value.get("agent_run_id") != agent_run_id:
        raise WorkflowError("agent context Agent Run identity does not match requested run")
    return value


def _items(values: list[str] | None, label: str) -> list[str]:
    result = values or []
    if len(result) > MAX_ITEMS or not all(isinstance(item, str) and item.strip() for item in result):
        raise WorkflowError(f"{label} must contain at most {MAX_ITEMS} non-empty strings")
    return sorted(set(item.strip() for item in result))



def close_terminal_assignment(
    state_dir: Path,
    agent_run_id: str,
    *,
    actor: str = "agent-workflow",
    summary: str = "terminal completion evidence collected",
) -> dict[str, Any]:
    """Close assignment state after canonical completion evidence is collected.

    This is host-owned administrative state. Workers do not emit a separate
    task-complete intent in the 0.11 protocol. The operation is idempotent so
    normal and recovery finalization share the same sequence safely.
    """
    validate_id(agent_run_id, "agent run ID")
    context = _read_json(state_dir / CONTEXT_NAME)
    if context.get("agent_run_id") != agent_run_id:
        raise WorkflowError("terminal assignment Agent Run identity mismatch")
    if context.get("state") == "closed":
        return context
    if context.get("state") != "busy" or not isinstance(context.get("current_assignment"), dict):
        raise WorkflowError("terminal assignment is not busy")
    return _close_assignment(
        state_dir,
        context,
        agent_run_id=agent_run_id,
        actor=actor,
        summary=summary,
        tags=[],
        files=[],
        lifecycle_reason="canonical completion evidence collected",
        emit_message=True,
    )
