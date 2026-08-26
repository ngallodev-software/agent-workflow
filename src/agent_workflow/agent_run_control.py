"""Durable messaging and process-owned lifecycle controls for Agent Runs."""

from __future__ import annotations

import os
import signal
import time
from typing import Any

from .config import Settings
from .errors import WorkflowError
from .messages import (
    append_message,
    bridge_available,
    bridge_required,
    replay_messages,
    wait_for_messages,
    write_control_intent,
)
from .state import TERMINAL_STATUSES, read_status, run_dir
from .run_lifecycle import authoritative_execution_status, synchronize_projection, transition_execution
from .steering import current_delivery, queue_request, record_acknowledgement
from .util import utc_now


def _active_run(settings: Settings, agent_run_id: str) -> dict[str, Any]:
    status = synchronize_projection(run_dir(settings, agent_run_id) / "status.json", source="control")
    if authoritative_execution_status(run_dir(settings, agent_run_id)) in TERMINAL_STATUSES:
        raise WorkflowError("cannot send a control message to a terminal Agent Run")
    return status


def _child_lifecycle_control(agent_run_id: str) -> dict[str, Any] | None:
    """Keep sandboxed children from mutating host-owned lifecycle state."""
    if bridge_available(agent_run_id) or bridge_required(agent_run_id):
        return {
            "outcome": "unavailable",
            "reason": "lifecycle controls are host-owned; exit the child normally",
        }
    return None


def _append_control_message(
    settings: Settings,
    agent_run_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Persist a workflow message before any optional live delivery."""
    return append_message(run_dir(settings, agent_run_id), agent_run_id=agent_run_id, **kwargs)


def steer(
    settings: Settings,
    agent_run_id: str,
    *,
    actor: str,
    content: str,
) -> dict[str, Any]:
    """Persist a parent steering request and queue bounded adapter delivery."""
    _active_run(settings, agent_run_id)
    message = _append_control_message(
        settings,
        agent_run_id,
        direction="parent_to_child",
        kind="steer",
        actor=actor,
        content=content,
    )
    delivery = queue_request(run_dir(settings, agent_run_id), message)
    return {
        **message,
        "delivery_outcome": delivery["outcome"],
        "delivery_event_id": delivery["event_id"],
    }


def progress(
    settings: Settings,
    agent_run_id: str,
    *,
    actor: str,
    content: str,
) -> dict[str, Any]:
    """Persist an explicit child progress update for its parent."""
    if bridge_available(agent_run_id):
        return write_control_intent(
            agent_run_id=agent_run_id, kind="progress", actor=actor, content=content
        )
    if bridge_required(agent_run_id):
        return {"outcome": "unavailable", "reason": "control bridge unavailable"}
    _active_run(settings, agent_run_id)
    return _append_control_message(
        settings,
        agent_run_id,
        direction="child_to_parent",
        kind="progress",
        actor=actor,
        content=content,
    )


def acknowledge(
    settings: Settings,
    agent_run_id: str,
    *,
    actor: str,
    content: str,
    correlation_id: str,
    outcome: str = "applied",
) -> dict[str, Any]:
    """Record a correlated applied or rejected steering acknowledgement."""
    if outcome not in {"applied", "rejected"}:
        raise WorkflowError("acknowledgement outcome must be applied or rejected")
    if bridge_available(agent_run_id):
        return write_control_intent(
            agent_run_id=agent_run_id,
            kind="ack",
            actor=actor,
            content=content,
            correlation_id=correlation_id,
            outcome=outcome,
        )
    if bridge_required(agent_run_id):
        return {"outcome": "unavailable", "reason": "control bridge unavailable"}
    _active_run(settings, agent_run_id)
    state_dir = run_dir(settings, agent_run_id)
    existing_delivery = current_delivery(state_dir, correlation_id)
    if existing_delivery is not None and existing_delivery["outcome"] in {
        "applied",
        "rejected",
        "expired",
    }:
        prior = str(existing_delivery["outcome"])
        if prior == "expired":
            raise WorkflowError("steering request already expired")
        if prior != outcome:
            raise WorkflowError(
                f"steering request already has terminal outcome {prior}"
            )
        existing_ack = next(
            (
                item
                for item in reversed(replay_messages(state_dir))
                if item.get("kind") == "ack"
                and item.get("correlation_id") == correlation_id
            ),
            None,
        )
        if existing_ack is None:
            raise WorkflowError(
                "terminal steering evidence has no correlated acknowledgement"
            )
        return {
            **existing_ack,
            "delivery_outcome": prior,
            "duplicate": True,
        }
    message = _append_control_message(
        settings,
        agent_run_id,
        direction="child_to_parent",
        kind="ack",
        actor=actor,
        content=content,
        correlation_id=correlation_id,
    )
    record_acknowledgement(
        state_dir,
        correlation_id=correlation_id,
        outcome=outcome,
        reason=content,
    )
    return {**message, "delivery_outcome": outcome}


def messages(
    settings: Settings,
    agent_run_id: str,
    *,
    after_sequence: int = 0,
) -> list[dict[str, Any]]:
    read_status(settings, agent_run_id)
    return replay_messages(run_dir(settings, agent_run_id), after_sequence=after_sequence)


def wait_for_message(
    settings: Settings,
    agent_run_id: str,
    *,
    after_sequence: int = 0,
    timeout_seconds: float | None = None,
) -> list[dict[str, Any]]:
    read_status(settings, agent_run_id)
    state_dir = run_dir(settings, agent_run_id)
    return wait_for_messages(
        state_dir,
        after_sequence=after_sequence,
        timeout_seconds=timeout_seconds,
    )


def _signal_owned_process(status: dict[str, Any], signum: int) -> bool:
    """Signal the AW-owned worker process group, if one is recorded."""
    pgid = status.get("worker_process_group_id")
    pid = status.get("worker_pid")
    target = pgid if isinstance(pgid, int) and pgid > 0 else pid
    if not isinstance(target, int) or target <= 0:
        return False
    try:
        if isinstance(pgid, int) and pgid > 0:
            os.killpg(pgid, signum)
        else:
            os.kill(target, signum)
    except ProcessLookupError:
        return False
    except PermissionError as exc:
        raise WorkflowError(f"cannot signal Agent Run worker {target}: {exc}") from exc
    return True


def interrupt(settings: Settings, agent_run_id: str) -> dict[str, Any]:
    child_control = _child_lifecycle_control(agent_run_id)
    if child_control is not None:
        return child_control
    prior = synchronize_projection(run_dir(settings, agent_run_id) / "status.json", source="control")
    if authoritative_execution_status(run_dir(settings, agent_run_id)) in TERMINAL_STATUSES:
        return prior
    if prior.get("worker_mode") != "headless":
        return {
            "agent_run_id": agent_run_id,
            "outcome": "unavailable",
            "reason": "external worker lifecycle control is not configured",
            "status": prior.get("status"),
        }
    _signal_owned_process(prior, signal.SIGINT)
    return transition_execution(
        settings,
        agent_run_id,
        "interruption_requested",
        actor="operator",
        reason="interrupt requested",
        projection_source="control",
        interruption_requested_at=utc_now(),
    )


def terminate(
    settings: Settings,
    agent_run_id: str,
    grace_seconds: int,
) -> dict[str, Any]:
    child_control = _child_lifecycle_control(agent_run_id)
    if child_control is not None:
        return child_control
    prior = synchronize_projection(run_dir(settings, agent_run_id) / "status.json", source="control")
    if authoritative_execution_status(run_dir(settings, agent_run_id)) in TERMINAL_STATUSES:
        return prior
    if prior.get("worker_mode") != "headless":
        return {
            "agent_run_id": agent_run_id,
            "outcome": "unavailable",
            "reason": "external worker lifecycle control is not configured",
            "status": prior.get("status"),
        }

    # Graceful escalation is process-owned: interrupt first, then terminate,
    # then force-kill only when the worker remains alive beyond the bounded grace.
    _signal_owned_process(prior, signal.SIGINT)
    pid = prior.get("worker_pid")
    deadline = time.time() + max(0, grace_seconds)

    def alive() -> bool:
        if not isinstance(pid, int) or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    while alive() and time.time() < deadline:
        time.sleep(0.1)
    if alive():
        _signal_owned_process(prior, signal.SIGTERM)
        term_deadline = time.time() + min(2.0, max(0.2, grace_seconds / 4 if grace_seconds else 0.2))
        while alive() and time.time() < term_deadline:
            time.sleep(0.1)
    if alive():
        _signal_owned_process(prior, signal.SIGKILL)

    return transition_execution(
        settings,
        agent_run_id,
        "terminated",
        actor="operator",
        reason="termination requested and worker stopped",
        projection_source="control",
        worker_alive=False,
        finished_at=utc_now(),
        terminated_by_operator=True,
    )
