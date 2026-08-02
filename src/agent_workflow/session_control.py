"""Durable operator messaging and lifecycle controls for delegated sessions."""

from __future__ import annotations

import time
from typing import Any

from . import tmux
from .agent_context import acknowledge_reuse
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
from .state import TERMINAL_STATUSES, read_status, run_dir, update_status
from .steering import current_delivery, queue_request, record_acknowledgement
from .util import utc_now


def _active_run(settings: Settings, session_id: str) -> dict[str, Any]:
    status = read_status(settings, session_id)
    if str(status.get("status")) in TERMINAL_STATUSES:
        raise WorkflowError("cannot send a control message to a terminal session")
    return status


def _child_lifecycle_control(session_id: str) -> dict[str, Any] | None:
    """Keep sandboxed children from mutating host-owned lifecycle state."""
    if bridge_available(session_id) or bridge_required(session_id):
        return {
            "outcome": "unavailable",
            "reason": "lifecycle controls are host-owned; exit the child normally",
        }
    return None


def _append_control_message(
    settings: Settings,
    session_id: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Persist first, then issue a best-effort tmux wake hint."""
    state_dir = run_dir(settings, session_id)
    channel = tmux.wakeup_channel(state_dir)
    return append_message(
        state_dir,
        session_id=session_id,
        after_commit=lambda _message: tmux.signal_waiters(channel),
        **kwargs,
    )


def steer(
    settings: Settings,
    session_id: str,
    *,
    actor: str,
    content: str,
) -> dict[str, Any]:
    """Persist a parent steering request and queue bounded adapter delivery."""
    _active_run(settings, session_id)
    message = _append_control_message(
        settings,
        session_id,
        direction="parent_to_child",
        kind="steer",
        actor=actor,
        content=content,
    )
    delivery = queue_request(run_dir(settings, session_id), message)
    return {
        **message,
        "delivery_outcome": delivery["outcome"],
        "delivery_event_id": delivery["event_id"],
    }


def progress(
    settings: Settings,
    session_id: str,
    *,
    actor: str,
    content: str,
) -> dict[str, Any]:
    """Persist an explicit child progress update for its parent."""
    if bridge_available(session_id):
        return write_control_intent(
            session_id=session_id, kind="progress", actor=actor, content=content
        )
    if bridge_required(session_id):
        return {"outcome": "unavailable", "reason": "control bridge unavailable"}
    _active_run(settings, session_id)
    return _append_control_message(
        settings,
        session_id,
        direction="child_to_parent",
        kind="progress",
        actor=actor,
        content=content,
    )


def acknowledge(
    settings: Settings,
    session_id: str,
    *,
    actor: str,
    content: str,
    correlation_id: str,
    outcome: str = "applied",
) -> dict[str, Any]:
    """Record a correlated applied or rejected steering acknowledgement."""
    if outcome not in {"applied", "rejected"}:
        raise WorkflowError("acknowledgement outcome must be applied or rejected")
    if bridge_available(session_id):
        return write_control_intent(
            session_id=session_id,
            kind="ack",
            actor=actor,
            content=content,
            correlation_id=correlation_id,
            outcome=outcome,
        )
    if bridge_required(session_id):
        return {"outcome": "unavailable", "reason": "control bridge unavailable"}
    _active_run(settings, session_id)
    state_dir = run_dir(settings, session_id)
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
        session_id,
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
    acknowledge_reuse(settings, session_id, correlation_id, actor)
    return {**message, "delivery_outcome": outcome}


def messages(
    settings: Settings,
    session_id: str,
    *,
    after_sequence: int = 0,
) -> list[dict[str, Any]]:
    read_status(settings, session_id)
    return replay_messages(run_dir(settings, session_id), after_sequence=after_sequence)


def wait_for_message(
    settings: Settings,
    session_id: str,
    *,
    after_sequence: int = 0,
    timeout_seconds: float | None = None,
) -> list[dict[str, Any]]:
    read_status(settings, session_id)
    state_dir = run_dir(settings, session_id)
    return wait_for_messages(
        state_dir,
        after_sequence=after_sequence,
        timeout_seconds=timeout_seconds,
        wakeup_channel=tmux.wakeup_channel(state_dir),
        wait_for_wakeup=tmux.wait_for_wakeup,
    )


def interrupt(settings: Settings, session_id: str) -> dict[str, Any]:
    child_control = _child_lifecycle_control(session_id)
    if child_control is not None:
        return child_control
    prior = read_status(settings, session_id)
    host_session = str(prior.get("tmux_session", session_id))
    if not tmux.session_exists(host_session):
        raise WorkflowError(f"session is not running: {session_id}")
    pane = tmux.resolve_status_pane(prior)
    if pane is None or pane.pane_id is None:
        raise WorkflowError(
            f"agent pane is unavailable or not bound to session: {session_id}"
        )
    tmux.interrupt(pane.pane_id)
    return update_status(
        settings,
        session_id,
        status="interruption_requested",
        prior_status=prior.get("status"),
        interruption_requested_at=utc_now(),
    )


def terminate(
    settings: Settings,
    session_id: str,
    grace_seconds: int,
) -> dict[str, Any]:
    child_control = _child_lifecycle_control(session_id)
    if child_control is not None:
        return child_control
    prior = read_status(settings, session_id)
    host_session = str(prior.get("tmux_session", session_id))
    if tmux.session_exists(host_session):
        pane = tmux.resolve_status_pane(prior)
        if pane is not None and pane.pane_id is not None:
            tmux.interrupt(pane.pane_id)
        deadline = time.time() + max(0, grace_seconds)
        while time.time() < deadline and tmux.resolve_status_pane(prior) is not None:
            time.sleep(0.25)
        if tmux.resolve_status_pane(prior) is not None:
            if prior.get("tmux_mode") == "shared_window":
                pane = tmux.resolve_status_pane(prior)
                if pane is not None and pane.pane_id is not None:
                    tmux.kill_pane(pane.pane_id)
            else:
                tmux.kill(session_id)
    current = read_status(settings, session_id)
    if str(current.get("status")) not in TERMINAL_STATUSES:
        current = update_status(
            settings,
            session_id,
            status="interrupted",
            finished_at=utc_now(),
            terminated_by_operator=True,
        )
    return current


def kill(settings: Settings, session_id: str) -> dict[str, Any]:
    child_control = _child_lifecycle_control(session_id)
    if child_control is not None:
        return child_control
    prior = read_status(settings, session_id)
    host_session = str(prior.get("tmux_session", session_id))
    if tmux.session_exists(host_session):
        if prior.get("tmux_mode") == "shared_window":
            pane = tmux.resolve_status_pane(prior)
            if pane is not None and pane.pane_id is not None:
                tmux.kill_pane(pane.pane_id)
        else:
            tmux.kill(session_id)
    current = read_status(settings, session_id)
    if str(current.get("status")) in TERMINAL_STATUSES:
        return current
    return update_status(
        settings,
        session_id,
        status="killed",
        finished_at=utc_now(),
        killed_by_operator=True,
    )
