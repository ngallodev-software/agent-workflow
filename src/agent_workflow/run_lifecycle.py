"""Authoritative execution lifecycle transitions for Agent Runs.

The append-only lifecycle journal is authoritative while a run is active. Once
sealed, the immutable final receipt/final-status pair is authoritative for the
terminal execution outcome. ``status.json`` is only a rebuildable projection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .config import Settings
from .errors import WorkflowError
from .events import append_lifecycle_event, reconstruct_lifecycle
from .state import (
    STATUS_SCHEMA,
    read_status_path,
    status_path,
    _update_projection_path_unchecked,
    write_projection_path,
)

EXECUTION_STATUSES = {
    "prepared",
    "running",
    "interruption_requested",
    "completed",
    "failed",
    "interrupted",
    "terminated",
    "retired",
}

_ALLOWED_TRANSITIONS: dict[str | None, set[str]] = {
    None: {"prepared", "failed"},
    "prepared": {"running", "interruption_requested", "terminated", "retired", "failed"},
    "running": {"interruption_requested", "completed", "failed", "interrupted", "terminated"},
    "interruption_requested": {"completed", "failed", "interrupted", "terminated"},
    "completed": set(),
    "failed": set(),
    "interrupted": set(),
    "terminated": set(),
}


def execution_state(run: Path) -> str | None:
    path = run / "events.jsonl"
    if not path.is_file():
        return None
    value = reconstruct_lifecycle(path).get("state", {}).get("execution")
    if value is None:
        return None
    if value not in EXECUTION_STATUSES:
        raise WorkflowError(f"invalid execution lifecycle state: {value!r}")
    return str(value)


def _validate_transition(prior: str | None, new: str) -> None:
    if new not in EXECUTION_STATUSES:
        raise WorkflowError(f"invalid Agent Run execution status: {new!r}")
    if new == prior:
        return
    allowed = _ALLOWED_TRANSITIONS.get(prior)
    if allowed is None or new not in allowed:
        raise WorkflowError(f"invalid Agent Run lifecycle transition: {prior!r} -> {new!r}")


def initialize_execution_path(
    path: Path,
    data: dict[str, Any],
    *,
    actor: str = "agent-workflow",
    reason: str = "Agent Run initialized",
    receipt_refs: Iterable[str] = (),
    projection_source: str = "initialization",
) -> dict[str, Any]:
    if data.get("schema") != STATUS_SCHEMA:
        raise WorkflowError("Agent Run lifecycle initialization requires current status schema")
    initial = str(data.get("status"))
    current = execution_state(path.parent)
    if current is not None:
        raise WorkflowError(f"Agent Run lifecycle is already initialized: {current}")
    _validate_transition(None, initial)
    append_lifecycle_event(
        path.parent,
        dimension="execution",
        prior=None,
        new=initial,
        actor=actor,
        reason=reason,
        receipt_refs=tuple(receipt_refs),
    )
    return write_projection_path(path, data, projection_source=projection_source)


def initialize_execution(
    settings: Settings,
    agent_run_id: str,
    data: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    return initialize_execution_path(status_path(settings, agent_run_id), data, **kwargs)


def transition_execution_path(
    path: Path,
    new_status: str,
    *,
    actor: str,
    reason: str,
    receipt_refs: Iterable[str] = (),
    projection_source: str = "lifecycle",
    projection_freshness: str = "snapshot",
    **projection_updates: Any,
) -> dict[str, Any]:
    run = path.parent
    # Once immutable terminal evidence exists, execution lifecycle is sealed.
    # Callers may refresh the mutable projection only when they agree with the
    # sealed terminal outcome; no post-seal execution event is appended.
    if (run / "final-receipt.json").is_file():
        sealed = authoritative_execution_status(run)
        if new_status != sealed:
            raise WorkflowError(
                f"sealed Agent Run execution state is immutable: {sealed!r} -> {new_status!r}"
            )
        return _update_projection_path_unchecked(
            path,
            projection_source=projection_source,
            projection_freshness=projection_freshness,
            status=sealed,
            **projection_updates,
        )

    prior = execution_state(run)
    if prior is None:
        raise WorkflowError("Agent Run execution lifecycle is not initialized")
    _validate_transition(prior, new_status)
    if new_status != prior:
        append_lifecycle_event(
            run,
            dimension="execution",
            prior=prior,
            new=new_status,
            actor=actor,
            reason=reason,
            receipt_refs=tuple(receipt_refs),
        )
    return _update_projection_path_unchecked(
        path,
        projection_source=projection_source,
        projection_freshness=projection_freshness,
        status=new_status,
        **projection_updates,
    )


def transition_execution(
    settings: Settings,
    agent_run_id: str,
    new_status: str,
    **kwargs: Any,
) -> dict[str, Any]:
    return transition_execution_path(status_path(settings, agent_run_id), new_status, **kwargs)


def authoritative_execution_status(run: Path) -> str:
    """Return immutable terminal authority when sealed, otherwise event authority."""
    receipt_path = run / "final-receipt.json"
    if receipt_path.is_file():
        from .receipts import read_sealed_contract, verify_seal_details

        receipt, _ = verify_seal_details(run)
        final, _ = read_sealed_contract(
            run, receipt, "final-status.json", "agent-workflow/agent-run-status/v1"
        )
        status = final.get("status")
        if status not in EXECUTION_STATUSES:
            raise WorkflowError("sealed final status has invalid execution state")
        return str(status)
    current = execution_state(run)
    if current is None:
        raise WorkflowError("Agent Run execution lifecycle is not initialized")
    return current


def synchronize_projection(
    path: Path,
    *,
    source: str = "lifecycle-rebuild",
    freshness: str = "snapshot",
    **projection_updates: Any,
) -> dict[str, Any]:
    """Refresh mutable execution projection from authoritative run evidence."""
    current = authoritative_execution_status(path.parent)
    projected = read_status_path(path)
    if projected.get("status") == current and not projection_updates:
        return projected
    return _update_projection_path_unchecked(
        path,
        projection_source=source,
        projection_freshness=freshness,
        status=current,
        **projection_updates,
    )
