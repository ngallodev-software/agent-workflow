"""Foreground aggregate inbox supervisor for orchestrator child journals."""

from __future__ import annotations

import fcntl
import json
import os
import signal
import threading
import time
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import WorkflowError
from .orchestrator_inbox import OrchestratorInboxError, orchestrator_dir, orchestrator_wakeup_channel, replay_registered
from .tmux import wait_for_wakeup
from .util import utc_now

LOCK_NAME = ".supervisor.lock"
EVENTS_NAME = "supervisor-events.jsonl"


def _record(directory: Path, reason: str, **metadata: Any) -> None:
    value = {"schema": "agent-workflow/orchestrator-supervisor-event/v1", "timestamp": utc_now(), "reason": reason, **metadata}
    descriptor = os.open(directory / EVENTS_NAME, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def watch(
    settings: Settings,
    orchestrator_id: str,
    *,
    interval_seconds: float | None = None,
    poll_seconds: float = 0.2,
    batch_size: int = 100,
    max_per_child: int = 25,
    max_cycles: int | None = None,
) -> dict[str, Any]:
    """Run one active writer that replays after every wake or timeout."""
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
                started = time.monotonic()
                woke = wait_for_wakeup(orchestrator_wakeup_channel(orchestrator_id), interval)
                elapsed = time.monotonic() - started
                _record(
                    directory,
                    "wake",
                    cycle=cycles,
                    wake_reason="signal" if woke else "timeout",
                )
                if not woke and elapsed < poll_seconds:
                    stop.wait(poll_seconds - elapsed)
            reason = "shutdown" if stop.is_set() else "completed"
            _record(directory, reason, cycles=cycles, advanced=total_advanced, imported=total_imported)
            return {"orchestrator_id": orchestrator_id, "state": reason, "cycles": cycles, "advanced": total_advanced, "imported": total_imported}
        finally:
            for name, handler in prior.items():
                signal.signal(name, handler)
    finally:
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()
