"""Durable logical assignment state for reusable interactive agents."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import tmux
from .config import Settings
from .errors import WorkflowError
from .events import append_lifecycle_event
from .messages import append_message, bridge_available, bridge_required, write_control_intent
from .state import list_statuses, read_status, run_dir
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


def _append_event(state_dir: Path, event: dict[str, Any]) -> dict[str, Any]:
    path = state_dir / LEDGER_NAME
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        stream.seek(0)
        sequence = 1 + sum(1 for line in stream if line.strip())
        record = {
            "schema": ASSIGNMENT_SCHEMA,
            "sequence": sequence,
            "timestamp": utc_now(),
            **event,
        }
        stream.seek(0, os.SEEK_END)
        stream.write(json.dumps(record, sort_keys=True, separators=(",", ":")).encode() + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    return record


def initialize(
    state_dir: Path,
    *,
    session_id: str,
    status: dict[str, Any],
    command: dict[str, Any],
) -> dict[str, Any]:
    assignment_id = str(uuid.uuid4())
    now = utc_now()
    assignment = {
        "assignment_id": assignment_id,
        "ticket_id": status.get("ticket_id"),
        "pack_id": status.get("pack_id"),
        "retry_of": status.get("retry_of"),
        "prompt_path": status.get("prompt_path"),
        "prompt_sha256": status.get("prompt_sha256"),
        "started_at": now,
    }
    context = {
        "schema": CONTEXT_SCHEMA,
        "session_id": session_id,
        "agent_name": status.get("agent_name"),
        "agent_class": status.get("agent_class"),
        "executor": status.get("executor"),
        "model": command.get("model"),
        "interactive": bool(command.get("interactive")),
        "provider_session_id": None,
        "repository_root": status.get("repository_root"),
        "worktree": str(Path(str(status["workdir"])).resolve()),
        "source_revision": status.get("source_revision"),
        "state": "busy",
        "current_assignment": assignment,
        "completed_assignments": [],
        "reuse_count": 0,
        "created_at": now,
        "updated_at": now,
    }
    _append_event(state_dir, {
        "event": "assigned",
        "session_id": session_id,
        "assignment_id": assignment_id,
        "actor": "agent-workflow",
        "ticket_id": status.get("ticket_id"),
        "pack_id": status.get("pack_id"),
        "correlation_id": None,
    })
    atomic_write_json(state_dir / CONTEXT_NAME, context)
    return context


def read(settings: Settings, session_id: str) -> dict[str, Any]:
    validate_id(session_id, "session ID")
    return _read_json(run_dir(settings, session_id) / CONTEXT_NAME)


def _items(values: list[str] | None, label: str) -> list[str]:
    result = values or []
    if len(result) > MAX_ITEMS or not all(isinstance(item, str) and item.strip() for item in result):
        raise WorkflowError(f"{label} must contain at most {MAX_ITEMS} non-empty strings")
    return sorted(set(item.strip() for item in result))


def complete_task(
    settings: Settings,
    session_id: str,
    *,
    actor: str,
    summary: str,
    tags: list[str] | None = None,
    files: list[str] | None = None,
    terminal: bool = True,
) -> dict[str, Any]:
    if bridge_available(session_id):
        return write_control_intent(
            session_id=session_id, kind="task_complete", actor=actor, content=summary,
            terminal=terminal,
        )
    if bridge_required(session_id):
        return {"outcome": "unavailable", "reason": "control bridge unavailable"}
    validate_id(actor, "actor ID")
    summary = summary.strip()
    if not summary or len(summary) > MAX_SUMMARY_CHARS:
        raise WorkflowError(f"summary must be 1-{MAX_SUMMARY_CHARS} characters")
    context = read(settings, session_id)
    status = read_status(settings, session_id)
    if status.get("status") not in {"prepared", "launched", "running", "interruption_requested"}:
        raise WorkflowError("task completion requires a live execution")
    host = str(status.get("tmux_session", session_id))
    try:
        pane = tmux.resolve_status_pane(status) if tmux.session_exists(host) else None
        alive = pane is not None and not pane.dead
    except WorkflowError:
        alive = False
    if not alive:
        raise WorkflowError("task completion requires a live agent pane")
    if not context.get("interactive"):
        raise WorkflowError("only interactive agents can complete assignments")
    if context.get("state") != "busy":
        raise WorkflowError(f"agent is not busy: {context.get('state')}")
    # A task-complete transition is an authority boundary.  Validate and
    # collect the sidecar before making the agent reusable so a malformed
    # human-readable report cannot later become a sealed invalid completion.
    from .runner import _collect_completion

    receipt = _collect_completion(
        state_dir := run_dir(settings, session_id),
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
        "session_id": session_id,
        "assignment_id": completed["assignment_id"],
        "actor": actor,
        "ticket_id": completed.get("ticket_id"),
        "pack_id": completed.get("pack_id"),
        "correlation_id": None,
        "summary": summary,
        "tags": completed["tags"],
        "files": completed["files"],
    })
    context["completed_assignments"] = [*context["completed_assignments"], completed]
    context["current_assignment"] = None
    next_state = "closed" if terminal else "idle_reusable"
    context["state"] = next_state
    context["updated_at"] = event["timestamp"]
    atomic_write_json(state_dir / CONTEXT_NAME, context)
    append_lifecycle_event(
        state_dir, dimension="assignment", prior="busy", new=next_state,
        actor=actor, reason=(
            "child emitted terminal structured task completion"
            if terminal else "child emitted reusable structured task completion"
        ),
        receipt_refs=[LEDGER_NAME, CONTEXT_NAME],
    )
    append_message(
        state_dir, session_id=session_id, direction="child_to_parent",
        kind="task_complete", actor=actor, content=summary,
    )
    return context


def apply_bridged_completion(
    state_dir: Path,
    session_id: str,
    *,
    actor: str,
    summary: str,
    terminal: bool = True,
) -> dict[str, Any]:
    """Apply a validated child completion using host-owned assignment state."""
    validate_id(session_id, "session ID")
    validate_id(actor, "actor ID")
    summary = summary.strip()
    if not summary or len(summary) > MAX_SUMMARY_CHARS:
        raise WorkflowError(f"summary must be 1-{MAX_SUMMARY_CHARS} characters")
    context = _read_json(state_dir / CONTEXT_NAME)
    if context.get("session_id") != session_id:
        raise WorkflowError("bridged completion session identity mismatch")
    if not context.get("interactive"):
        raise WorkflowError("only interactive agents can complete assignments")
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
        "session_id": session_id,
        "assignment_id": completed["assignment_id"],
        "actor": actor,
        "ticket_id": completed.get("ticket_id"),
        "pack_id": completed.get("pack_id"),
        "correlation_id": None,
        "summary": summary,
        "tags": [],
        "files": [],
    })
    context["completed_assignments"] = [*context["completed_assignments"], completed]
    context["current_assignment"] = None
    next_state = "closed" if terminal else "idle_reusable"
    context["state"] = next_state
    context["updated_at"] = event["timestamp"]
    atomic_write_json(state_dir / CONTEXT_NAME, context)
    append_lifecycle_event(
        state_dir, dimension="assignment", prior="busy", new=next_state,
        actor=actor, reason=(
            "host applied terminal bridged task completion"
            if terminal else "host applied reusable bridged task completion"
        ),
        receipt_refs=[LEDGER_NAME, CONTEXT_NAME],
    )
    return context


def _same_path(left: object, right: Path) -> bool:
    return isinstance(left, str) and Path(left).resolve() == right.resolve()


def _is_stale(value: str, minutes: int) -> bool:
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        return True
    return (datetime.now(timezone.utc) - when).total_seconds() >= minutes * 60


def candidates(
    settings: Settings,
    *,
    workdir: Path,
    ticket_id: str | None = None,
    pack_id: str | None = None,
    retry_of: str | None = None,
    agent_class: str | None = None,
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    workdir = expand_path(workdir).resolve()
    wanted_tags = set(_items(tags, "tags"))
    rows: list[dict[str, Any]] = []
    for status in list_statuses(settings):
        session_id = str(status.get("session_id", ""))
        path = run_dir(settings, session_id) / CONTEXT_NAME
        if not path.is_file():
            continue
        try:
            context = _read_json(path)
        except WorkflowError:
            continue
        reasons: list[str] = []
        eligible = True
        if context.get("state") != "idle_reusable":
            eligible = False
            reasons.append(f"state={context.get('state')}")
        if not _same_path(context.get("worktree"), workdir):
            eligible = False
            reasons.append("different_worktree")
        host = str(status.get("tmux_session", session_id))
        try:
            pane = tmux.resolve_status_pane(status) if tmux.session_exists(host) else None
            alive = pane is not None and not pane.dead
        except WorkflowError:
            alive = False
        if not alive:
            eligible = False
            reasons.append("pane_not_alive")
        if agent_class and context.get("agent_class") != agent_class:
            eligible = False
            reasons.append("incompatible_agent_class")
        completed = context.get("completed_assignments") or []
        last = completed[-1] if completed else {}
        if _is_stale(str(last.get("completed_at", "")), settings.reuse_stale_minutes):
            eligible = False
            reasons.append("idle_stale")
        same_ticket = bool(ticket_id and last.get("ticket_id") == ticket_id)
        same_pack = bool(pack_id and last.get("pack_id") == pack_id)
        retry_lineage = bool(retry_of and retry_of in {session_id, last.get("assignment_id"), last.get("ticket_id")})
        exact_lineage = same_ticket or retry_lineage
        overlap = len(wanted_tags.intersection(last.get("tags") or []))
        score = (100 if exact_lineage else 0) + (20 if same_pack else 0) + min(20, overlap * 5)
        if same_ticket:
            reasons.append("same_ticket")
        if retry_lineage:
            reasons.append("retry_lineage")
        if same_pack:
            reasons.append("same_pack")
        if overlap:
            reasons.append(f"tag_overlap={overlap}")
        rows.append({
            "session_id": session_id,
            "agent_name": context.get("agent_name"),
            "agent_class": context.get("agent_class"),
            "score": score,
            "eligible": eligible,
            "auto_reuse_eligible": eligible and exact_lineage,
            "reasons": reasons,
            "last_summary": last.get("summary"),
            "updated_at": context.get("updated_at"),
        })
    return sorted(rows, key=lambda row: (not row["eligible"], -row["score"], str(row["updated_at"])), reverse=False)


def idle_interactive_sessions(
    settings: Settings, *, window_target: str
) -> list[dict[str, Any]]:
    """Return live, explicitly idle panes in one tmux window, oldest first."""
    rows: list[dict[str, Any]] = []
    for status in list_statuses(settings):
        session_id = str(status.get("session_id", ""))
        target = str(status.get("tmux_target", ""))
        status_window = status.get("tmux_window_target")
        if status_window != window_target and not (
            status_window is None and target.startswith(f"{window_target}.")
        ):
            continue
        path = run_dir(settings, session_id) / CONTEXT_NAME
        if not path.is_file():
            continue
        try:
            context = _read_json(path)
            pane = tmux.resolve_status_pane(status)
        except WorkflowError:
            continue
        if (
            context.get("interactive")
            and context.get("state") in {"idle_reusable", "idle_stale"}
            and pane is not None
            and not pane.dead
        ):
            rows.append(
                {
                    "session_id": session_id,
                    "agent_name": context.get("agent_name"),
                    "state": context.get("state"),
                    "tmux_target": target,
                    "tmux_pane_id": pane.pane_id,
                    "updated_at": context.get("updated_at"),
                }
            )
    return sorted(
        rows,
        key=lambda row: (
            row["state"] != "idle_stale",
            str(row.get("updated_at", "")),
            row["session_id"],
        ),
    )


def request_reuse(
    settings: Settings,
    session_id: str,
    *,
    prompt_path: Path,
    actor: str,
    ticket_id: str | None = None,
    pack_id: str | None = None,
    retry_of: str | None = None,
    tags: list[str] | None = None,
    automatic: bool = False,
) -> dict[str, Any]:
    validate_id(actor, "actor ID")
    context = read(settings, session_id)
    if context.get("state") != "idle_reusable":
        raise WorkflowError(f"agent is not idle_reusable: {context.get('state')}")
    prompt_path = expand_path(prompt_path)
    if not prompt_path.is_file():
        raise WorkflowError(f"prompt not found: {prompt_path}")
    rows = candidates(
        settings, workdir=Path(str(context["worktree"])), ticket_id=ticket_id,
        pack_id=pack_id, retry_of=retry_of, agent_class=str(context["agent_class"]), tags=tags,
    )
    match = next((row for row in rows if row["session_id"] == session_id), None)
    if not match or not match["eligible"]:
        raise WorkflowError("agent is not an eligible same-worktree reuse candidate")
    if automatic and not match["auto_reuse_eligible"]:
        raise WorkflowError("automatic reuse requires exact ticket or retry lineage")
    assignment_id = str(uuid.uuid4())
    state_dir = run_dir(settings, session_id)
    assignment_dir = state_dir / "assignments" / assignment_id
    assignment_dir.mkdir(parents=True)
    prompt_copy = assignment_dir / "prompt.md"
    shutil.copy2(prompt_path, prompt_copy)
    content = (
        f"New durable assignment {assignment_id}. Read {prompt_copy}. "
        f"Acknowledge this message before starting; on completion run agent-workflow agent task-complete."
    )
    message = append_message(
        state_dir, session_id=session_id, direction="parent_to_child", kind="steer",
        actor=actor, content=content,
    )
    assignment = {
        "assignment_id": assignment_id,
        "ticket_id": ticket_id,
        "pack_id": pack_id,
        "retry_of": retry_of,
        "prompt_path": str(prompt_copy),
        "prompt_sha256": sha256_file(prompt_copy),
        "requested_at": utc_now(),
        "tags": _items(tags, "tags"),
        "correlation_id": message["message_id"],
    }
    event = _append_event(state_dir, {
        "event": "assignment_requested", "session_id": session_id,
        "assignment_id": assignment_id, "actor": actor,
        "ticket_id": ticket_id, "pack_id": pack_id,
        "correlation_id": message["message_id"], "automatic": automatic,
    })
    context["state"] = "reuse_pending"
    context["current_assignment"] = assignment
    context["updated_at"] = event["timestamp"]
    atomic_write_json(state_dir / CONTEXT_NAME, context)
    append_lifecycle_event(
        state_dir, dimension="assignment", prior="idle_reusable", new="reuse_pending",
        actor=actor, reason="reuse assignment awaits correlated child acknowledgement",
        receipt_refs=[LEDGER_NAME, CONTEXT_NAME, "messages.jsonl"],
    )
    return {"context": context, "message": message, "candidate": match}


def acknowledge_reuse(settings: Settings, session_id: str, correlation_id: str, actor: str) -> None:
    if not (run_dir(settings, session_id) / CONTEXT_NAME).is_file():
        return
    context = read(settings, session_id)
    current = context.get("current_assignment") or {}
    if context.get("state") != "reuse_pending" or current.get("correlation_id") != correlation_id:
        return
    state_dir = run_dir(settings, session_id)
    current["started_at"] = utc_now()
    event = _append_event(state_dir, {
        "event": "assignment_started", "session_id": session_id,
        "assignment_id": current["assignment_id"], "actor": actor,
        "ticket_id": current.get("ticket_id"), "pack_id": current.get("pack_id"),
        "correlation_id": correlation_id,
    })
    context["state"] = "busy"
    context["reuse_count"] = int(context.get("reuse_count", 0)) + 1
    context["updated_at"] = event["timestamp"]
    atomic_write_json(state_dir / CONTEXT_NAME, context)
    append_lifecycle_event(
        state_dir, dimension="assignment", prior="reuse_pending", new="busy",
        actor=actor, reason="child acknowledged reuse assignment",
        receipt_refs=[LEDGER_NAME, CONTEXT_NAME, "messages.jsonl"],
    )


def auto_reuse(
    settings: Settings, *, workdir: Path, prompt_path: Path, actor: str,
    ticket_id: str | None, pack_id: str | None, retry_of: str | None,
    agent_class: str | None, tags: list[str] | None,
) -> dict[str, Any]:
    rows = candidates(
        settings, workdir=workdir, ticket_id=ticket_id, pack_id=pack_id,
        retry_of=retry_of, agent_class=agent_class, tags=tags,
    )
    match = next((row for row in rows if row["auto_reuse_eligible"]), None)
    if match is None:
        return {"action": "launch", "reason": "no exact-lineage reusable agent", "candidates": rows}
    result = request_reuse(
        settings, match["session_id"], prompt_path=prompt_path, actor=actor,
        ticket_id=ticket_id, pack_id=pack_id, retry_of=retry_of, tags=tags,
        automatic=True,
    )
    return {"action": "reuse_pending", **result}
