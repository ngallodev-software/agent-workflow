"""Foreground aggregate inbox supervisor for orchestrator child journals."""

from __future__ import annotations

import fcntl
import os
import signal
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from .config import Settings
from .errors import WorkflowError
from .journal import append_jsonl
from .orchestrator_inbox import OrchestratorInboxError, orchestrator_dir, replay_registered
from .util import utc_now

LOCK_NAME = ".supervisor.lock"
EVENTS_NAME = "supervisor-events.jsonl"
MAX_NOTIFY_SUMMARY_CHARS = 512

# IFACE-001: hosts may provide a callable without making the host runtime a
# dependency of the workflow core.  The callable receives only NOTIFY-001.
NotificationAdapter = Callable[[Mapping[str, Any]], object]


def _notification(event: Mapping[str, Any], orchestrator_id: str) -> dict[str, Any]:
    """Project an inbox event into the bounded NOTIFY-001 host contract."""
    summary = f"{event['kind']} event imported"
    return {
        "event_id": event["event_id"],
        "orchestrator_id": orchestrator_id,
        "sender_agent_run_id": event["sender_agent_run_id"],
        "kind": event["kind"],
        "summary": summary[:MAX_NOTIFY_SUMMARY_CHARS],
    }


def _validate_supervisor_event(value: object, _line_number: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError("orchestrator supervisor event must be a JSON object")
    if value.get("schema") != "agent-workflow/orchestrator-supervisor-event/v1":
        raise WorkflowError("invalid orchestrator supervisor event schema")
    if not isinstance(value.get("timestamp"), str) or not isinstance(value.get("reason"), str):
        raise WorkflowError("invalid orchestrator supervisor event")
    return value


def _record(directory: Path, reason: str, **metadata: Any) -> None:
    value = {
        "schema": "agent-workflow/orchestrator-supervisor-event/v1",
        "timestamp": utc_now(),
        "reason": reason,
        **metadata,
    }
    append_jsonl(
        directory / EVENTS_NAME,
        value,
        validator=_validate_supervisor_event,
    )


def watch(
    settings: Settings,
    orchestrator_id: str,
    *,
    interval_seconds: float | None = None,
    poll_seconds: float = 0.2,
    batch_size: int = 100,
    max_per_child: int = 25,
    max_cycles: int | None = None,
    notification_adapter: NotificationAdapter | None = None,
) -> dict[str, Any]:
    """Run one active writer that replays durable child journals on a bounded interval."""
    if poll_seconds <= 0 or batch_size < 1 or max_per_child < 1:
        raise WorkflowError("watch bounds must be positive")
    if max_cycles is not None and max_cycles < 1:
        raise WorkflowError("max_cycles must be positive")
    interval = float(settings.supervisor_interval_seconds if interval_seconds is None else interval_seconds)
    if interval <= 0:
        raise WorkflowError("watch interval must be positive")
    directory = orchestrator_dir(settings, orchestrator_id)
    descriptor = os.open(directory / LOCK_NAME, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    stream = os.fdopen(descriptor, "a+b")
    try:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkflowError("orchestrator supervisor already active") from exc
        stop = threading.Event()
        prior = {name: signal.getsignal(name) for name in (signal.SIGTERM, signal.SIGINT)}
        for name in prior:
            signal.signal(name, lambda _signum, _frame: stop.set())
        cycles = 0
        failures = 0
        total_advanced = 0
        total_imported = 0
        _record(directory, "startup", orchestrator_id=orchestrator_id)
        try:
            while not stop.is_set() and (max_cycles is None or cycles < max_cycles):
                try:
                    report = replay_registered(settings, orchestrator_id, batch_size=batch_size, max_per_child=max_per_child)
                    failures = 0
                    cycles += 1
                    total_advanced += report["advanced"]
                    total_imported += report["count"]
                    _record(directory, "replay", cycle=cycles, advanced=report["advanced"], imported=report["count"], children=report["children"])
                    if notification_adapter is not None:
                        for event in report["imported"]:
                            try:
                                notification_adapter(_notification(event, orchestrator_id))
                            except Exception as exc:
                                # Delivery is advisory.  The durable inbox and
                                # source cursor are already authoritative.
                                _record(
                                    directory,
                                    "notification-error",
                                    cycle=cycles,
                                    error_type=type(exc).__name__,
                                )
                except (OrchestratorInboxError, OSError, WorkflowError) as exc:
                    failures += 1
                    cycles += 1
                    _record(directory, "error", cycle=cycles, error_type=type(exc).__name__)
                    if max_cycles is not None and cycles >= max_cycles:
                        break
                    stop.wait(min(interval * (2 ** min(failures - 1, 4)), 60.0))
                    continue
                if max_cycles is not None and cycles >= max_cycles:
                    break
                stop.wait(interval)
                _record(directory, "poll", cycle=cycles, interval_seconds=interval)
            reason = "shutdown" if stop.is_set() else "completed"
            _record(directory, reason, cycles=cycles, advanced=total_advanced, imported=total_imported)
            return {"orchestrator_id": orchestrator_id, "state": reason, "cycles": cycles, "advanced": total_advanced, "imported": total_imported}
        finally:
            for name, handler in prior.items():
                signal.signal(name, handler)
    finally:
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()
