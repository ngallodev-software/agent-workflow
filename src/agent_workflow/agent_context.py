"""Durable assignment identity for an Agent Run worker."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Settings
from .contracts import validate_instance
from .errors import WorkflowError
from .journal import JournalTransactionResult, transact_jsonl
from .events import append_lifecycle_event
from .messages import append_message, bridge_available, bridge_required, write_control_intent
from .state import list_statuses, read_status, run_dir
from .run_lifecycle import authoritative_execution_status
from .util import atomic_write_json, expand_path, sha256_file, utc_now, validate_id

CONTEXT_SCHEMA = "agent-workflow/agent-context/v1"
ASSIGNMENT_SCHEMA = "agent-workflow/assignment-event/v1"
CONTEXT_NAME = "agent-context.json"
LEDGER_NAME = "assignments.jsonl"
MAX_SUMMARY_CHARS = 4096
MAX_ITEMS = 64


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot read agent context {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != CONTEXT_SCHEMA:
        raise WorkflowError(f"invalid agent context: {path}")
    return value


def _validate_assignment_record(value: object, line_number: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError("assignment event must be a JSON object")
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
    command: dict[str, Any],
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
        "executor": status.get("executor"),
        "model": command.get("model"),
        "interactive": bool(command.get("interactive")),
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
    return _read_json(run_dir(settings, agent_run_id) / CONTEXT_NAME)


def _items(values: list[str] | None, label: str) -> list[str]:
    result = values or []
    if len(result) > MAX_ITEMS or not all(isinstance(item, str) and item.strip() for item in result):
        raise WorkflowError(f"{label} must contain at most {MAX_ITEMS} non-empty strings")
    return sorted(set(item.strip() for item in result))


def complete_task(
    settings: Settings,
    agent_run_id: str,
    *,
    actor: str,
    summary: str,
    tags: list[str] | None = None,
    files: list[str] | None = None,
    terminal: bool = True,
) -> dict[str, Any]:
    if bridge_available(agent_run_id):
        return write_control_intent(
            agent_run_id=agent_run_id, kind="task_complete", actor=actor, content=summary,
            terminal=terminal,
        )
    if bridge_required(agent_run_id):
        return {"outcome": "unavailable", "reason": "control bridge unavailable"}
    validate_id(actor, "actor ID")
    summary = summary.strip()
    if not summary or len(summary) > MAX_SUMMARY_CHARS:
        raise WorkflowError(f"summary must be 1-{MAX_SUMMARY_CHARS} characters")
    context = read(settings, agent_run_id)
    status = read_status(settings, agent_run_id)
    execution_status = authoritative_execution_status(run_dir(settings, agent_run_id))
    if execution_status not in {"prepared", "running", "interruption_requested"}:
        raise WorkflowError("task completion requires a live execution")
    if execution_status not in {"running", "interruption_requested"}:
        raise WorkflowError("task completion requires a running Agent Run")
    if context.get("worker_mode") != "external" or not context.get("interactive"):
        raise WorkflowError("task-complete is only available to an interactive external worker")
    if context.get("state") != "busy":
        raise WorkflowError(f"agent is not busy: {context.get('state')}")
    # A task-complete transition is an authority boundary.  Validate and
    # collect the sidecar before making the agent reusable so a malformed
    # human-readable report cannot later become a sealed invalid completion.
    from .run_collections import collect_completion

    receipt = collect_completion(
        state_dir := run_dir(settings, agent_run_id),
        Path(str(status["workdir"])),
    )
    if receipt["validation_status"] != "valid":
        details = "; ".join(receipt.get("validation_errors", []))
        raise WorkflowError(f"task completion handoff is invalid: {details}")
    completed = {
        **dict(context["current_assignment"]),
        "completed_at": utc_now(),
        "summary": summary,
        "tags": _items(tags, "tags"),
        "files": _items(files, "files"),
    }
    event = _append_event(state_dir, {
        "event": "task_completed",
        "agent_run_id": agent_run_id,
        "assignment_id": completed["assignment_id"],
        "actor": actor,
        "ticket_id": completed.get("ticket_id"),
        "pack_id": completed.get("pack_id"),
        "correlation_id": None,
        "summary": summary,
        "tags": completed["tags"],
        "files": completed["files"],
    })
    context["completed_assignment"] = completed
    context["current_assignment"] = None
    next_state = "closed"
    context["state"] = next_state
    context["updated_at"] = event["timestamp"]
    atomic_write_json(state_dir / CONTEXT_NAME, context)
    append_lifecycle_event(
        state_dir, dimension="assignment", prior="busy", new=next_state,
        actor=actor, reason=(
            "child emitted structured task completion"
        ),
        receipt_refs=[LEDGER_NAME, CONTEXT_NAME],
    )
    append_message(
        state_dir, agent_run_id=agent_run_id, direction="child_to_parent",
        kind="task_complete", actor=actor, content=summary,
    )
    return context


def apply_bridged_completion(
    state_dir: Path,
    agent_run_id: str,
    *,
    actor: str,
    summary: str,
    terminal: bool = True,
) -> dict[str, Any]:
    """Apply a validated child completion using host-owned assignment state."""
    validate_id(agent_run_id, "agent run ID")
    validate_id(actor, "actor ID")
    summary = summary.strip()
    if not summary or len(summary) > MAX_SUMMARY_CHARS:
        raise WorkflowError(f"summary must be 1-{MAX_SUMMARY_CHARS} characters")
    context = _read_json(state_dir / CONTEXT_NAME)
    if context.get("agent_run_id") != agent_run_id:
        raise WorkflowError("bridged completion Agent Run identity mismatch")
    if context.get("worker_mode") != "external" or not context.get("interactive"):
        raise WorkflowError("task-complete is only available to an interactive external worker")
    if context.get("state") != "busy" or not isinstance(context.get("current_assignment"), dict):
        raise WorkflowError("agent is not busy")
    completed = {
        **dict(context["current_assignment"]),
        "completed_at": utc_now(),
        "summary": summary,
        "tags": [],
        "files": [],
    }
    event = _append_event(state_dir, {
        "event": "task_completed",
        "agent_run_id": agent_run_id,
        "assignment_id": completed["assignment_id"],
        "actor": actor,
        "ticket_id": completed.get("ticket_id"),
        "pack_id": completed.get("pack_id"),
        "correlation_id": None,
        "summary": summary,
        "tags": [],
        "files": [],
    })
    context["completed_assignment"] = completed
    context["current_assignment"] = None
    next_state = "closed"
    context["state"] = next_state
    context["updated_at"] = event["timestamp"]
    atomic_write_json(state_dir / CONTEXT_NAME, context)
    append_lifecycle_event(
        state_dir, dimension="assignment", prior="busy", new=next_state,
        actor=actor, reason=(
            "host applied bridged task completion"
        ),
        receipt_refs=[LEDGER_NAME, CONTEXT_NAME],
    )
    return context


