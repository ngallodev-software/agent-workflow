"""Foreground aggregate inbox supervisor for orchestrator child journals."""

from __future__ import annotations

import fcntl
import hashlib
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
from .util import atomic_write_json, fsync_directory, utc_now

LOCK_NAME = ".supervisor.lock"
EVENTS_NAME = "supervisor-events.jsonl"
STATUS_NAME = "supervisor-status.json"
STATUS_QUARANTINE_NAME = "supervisor-status-quarantine"
MAX_REPLAY_INTERVAL_SECONDS = 2.0
MAX_STATUS_REPLAY_BYTES = 64 * 1024
LOCK_METADATA_SCHEMA = "agent-workflow/orchestrator-supervisor-lock/v1"
STATUS_SCHEMA = "agent-workflow/orchestrator-supervisor-status/v1"
EVENT_SCHEMA = "agent-workflow/orchestrator-supervisor-event/v1"


def _record(directory: Path, reason: str, **metadata: Any) -> None:
    value = {"schema": "agent-workflow/orchestrator-supervisor-event/v1", "timestamp": utc_now(), "reason": reason, **metadata}
    descriptor = os.open(directory / EVENTS_NAME, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _proc_identity(pid: int) -> tuple[str, str] | None:
    """Return Linux process start evidence; PID alone is never sufficient."""
    if pid < 1:
        return None
    try:
        tail = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(")", 1)[1].split()
        start_ticks = tail[19]
        boot_id = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError, IndexError):
        return None
    return boot_id, start_ticks


def _current_identity() -> dict[str, Any]:
    identity = _proc_identity(os.getpid())
    if identity is None:
        raise WorkflowError("cannot establish supervisor process start evidence")
    return {"pid": os.getpid(), "boot_id": identity[0], "proc_start_ticks": identity[1]}


def _read_lock_metadata(path: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    if not raw:
        return {"invalid": "metadata is empty"}
    if len(raw) > 4096:
        return {"invalid": "metadata exceeds bounded size"}
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"invalid": "metadata is not valid JSON"}
    return value if isinstance(value, dict) else {"invalid": "metadata is not an object"}


def _prior_owner_state(metadata: dict[str, Any] | None) -> str:
    if metadata is None:
        return "none"
    if "invalid" in metadata:
        return "unknown"
    try:
        pid = metadata["pid"]
        boot_id = metadata["boot_id"]
        start_ticks = metadata["proc_start_ticks"]
        if not isinstance(pid, int) or not isinstance(boot_id, str) or not isinstance(start_ticks, str):
            return "unknown"
    except KeyError:
        return "unknown"
    identity = _proc_identity(pid)
    if identity is None:
        return "dead"
    return "alive" if identity == (boot_id, start_ticks) else "stale"


def _write_lock_metadata(stream: Any, metadata: dict[str, Any]) -> None:
    encoded = (json.dumps(metadata, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    stream.seek(0)
    stream.truncate()
    stream.write(encoded)
    stream.flush()
    os.fsync(stream.fileno())


def _write_status(directory: Path, value: dict[str, Any]) -> None:
    atomic_write_json(directory / STATUS_NAME, value, mode=0o600)
    fsync_directory(directory)


def _read_bounded(path: Path, limit: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        return stream.read(limit + 1)


def _read_event_tail(path: Path, limit: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        size = os.fstat(descriptor).st_size
        os.lseek(descriptor, max(0, size - limit), os.SEEK_SET)
        return os.read(descriptor, limit)
    finally:
        os.close(descriptor)


def _status_events(directory: Path) -> list[dict[str, Any]]:
    try:
        raw = _read_event_tail(directory / EVENTS_NAME, MAX_STATUS_REPLAY_BYTES)
    except OSError:
        return []
    events: list[dict[str, Any]] = []
    for line in raw.decode("utf-8", errors="replace").splitlines()[-128:]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict) and item.get("schema") == EVENT_SCHEMA:
            events.append(item)
    return events


def _status_expectations(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return {}
    startup_index = max(
        (index for index, item in enumerate(events) if item.get("reason") == "startup"),
        default=-1,
    )
    current = events[startup_index + 1 :]
    replay = [item for item in current if item.get("reason") == "replay"]
    terminal = next(
        (item for item in reversed(current) if item.get("reason") in {"completed", "shutdown"}),
        None,
    )
    expectations: dict[str, Any] = {
        "state": terminal.get("reason") if terminal else "running",
    }
    if terminal is not None:
        for status_key, event_key in (
            ("cycle", "cycles"),
            ("advanced", "advanced"),
            ("imported", "imported"),
        ):
            value = terminal.get(event_key)
            if isinstance(value, int) and value >= 0:
                expectations[status_key] = value
    elif replay:
        latest = replay[-1]
        cycle = latest.get("cycle")
        if isinstance(cycle, int) and cycle >= 0:
            expectations["cycle"] = cycle
        for status_key, event_key in (("advanced", "advanced"), ("imported", "imported")):
            values = [item.get(event_key) for item in replay]
            if all(isinstance(value, int) and value >= 0 for value in values):
                expectations[status_key] = sum(values)
        for status_key, event_key in (
            ("pending_acknowledgements_count", "pending_acknowledgements_count"),
            ("pending_actions_count", "pending_actions_count"),
        ):
            value = latest.get(event_key)
            if isinstance(value, int) and value >= 0:
                expectations[status_key] = value
        for key in (
            "pending_acknowledgements",
            "pending_acknowledgement_digests",
            "pending_actions",
            "pending_action_digests",
        ):
            if key in latest:
                expectations[key] = latest[key]
    if terminal is not None:
        for key in (
            "pending_acknowledgements",
            "pending_acknowledgement_digests",
            "pending_actions",
            "pending_action_digests",
        ):
            if key in terminal:
                expectations[key] = terminal[key]
    return expectations


def _status_mismatch(value: dict[str, Any], expectations: dict[str, Any]) -> str | None:
    if value.get("schema_version") != 1:
        return "status projection schema version is inconsistent"
    if not isinstance(value.get("reconstructed"), bool):
        return "status projection reconstructed flag is inconsistent"
    for key in ("state", "cycle", "advanced", "imported"):
        if key in expectations and value.get(key) != expectations[key]:
            return f"status projection field is inconsistent: {key}"
    for key, count_key in (
        ("pending_acknowledgements", "pending_acknowledgements_count"),
        ("pending_actions", "pending_actions_count"),
    ):
        expected = expectations.get(key)
        if expected is not None:
            if value.get(key) != expected:
                return f"status projection field is inconsistent: {key}"
        elif count_key in expectations:
            pending = value.get(key)
            if not isinstance(pending, list) or len(pending) != expectations[count_key]:
                return f"status projection field is inconsistent: {key}"
    for key in ("pending_acknowledgement_digests", "pending_action_digests"):
        if key in expectations and value.get(key) != expectations[key]:
            return f"status projection field is inconsistent: {key}"
    return None


def _quarantine_status(path: Path, reason: str, raw: bytes | None) -> None:
    bounded = (raw if raw is not None else b"")[:MAX_STATUS_REPLAY_BYTES]
    try:
        size = path.stat().st_size
    except OSError:
        size = None
    digest = hashlib.sha256(bounded).hexdigest()
    metadata = {
        "schema": "agent-workflow/orchestrator-supervisor-status-quarantine/v1",
        "reason": reason[:256],
        "size_bytes": size,
        "captured_bytes": len(bounded),
        "truncated": size is not None and size > len(bounded),
        "sha256": digest,
        "content_redacted": True,
        "quarantined_at": utc_now(),
    }
    quarantine = path.parent / STATUS_QUARANTINE_NAME
    target = quarantine / f"{hashlib.sha256((path.name + digest).encode('utf-8')).hexdigest()}.json"
    atomic_write_json(target, metadata, mode=0o600)
    fsync_directory(quarantine)


def _status_from_events(directory: Path) -> tuple[dict[str, Any], bool]:
    path = directory / STATUS_NAME
    raw_status: bytes | None = None
    try:
        raw_status = _read_bounded(path, MAX_STATUS_REPLAY_BYTES)
        if len(raw_status) > MAX_STATUS_REPLAY_BYTES:
            raise ValueError("status projection exceeds bounded size")
        value = json.loads(raw_status.decode("utf-8"))
        if not isinstance(value, dict) or value.get("schema") != STATUS_SCHEMA:
            raise ValueError("status projection schema is invalid")
        mismatch = _status_mismatch(value, _status_expectations(_status_events(directory)))
        if mismatch is not None:
            raise ValueError(mismatch)
        return value, False
    except FileNotFoundError:
        pass
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        try:
            _quarantine_status(path, str(exc), raw_status)
        except OSError:
            pass
    expectations = _status_expectations(_status_events(directory))
    status = {
        "schema": STATUS_SCHEMA,
        "schema_version": 1,
        "state": expectations.get("state", "reconstructed"),
        "reconstructed": True,
        "updated_at": utc_now(),
    }
    for key in ("cycle", "advanced", "imported"):
        if key in expectations:
            status[key] = expectations[key]
    return status, True


def _notify_orchestrator(report: dict[str, Any]) -> dict[str, Any]:
    """Build the fixed opaque notification receipt after durable import.

    The notification contains no child-controlled content.  It is only an
    advisory receipt; inbox records and acknowledgement/action journals remain
    the authority if this process exits immediately afterward.
    """
    imported = report.get("imported", [])
    return {
        "notification_attempted": True,
        "notification_event_ids": [item["event_id"] for item in imported],
        "notification_event_digests": [item["event_digest"] for item in imported],
    }


def watch(
    settings: Settings,
    orchestrator_id: str,
    *,
    interval_seconds: float | None = None,
    poll_seconds: float = 0.2,
    batch_size: int = 100,
    max_per_child: int = 25,
    max_cycles: int | None = None,
    operator_override: bool = False,
) -> dict[str, Any]:
    """Run one active writer that replays after every wake or timeout."""
    if poll_seconds <= 0 or batch_size < 1 or max_per_child < 1:
        raise WorkflowError("watch bounds must be positive")
    if max_cycles is not None and max_cycles < 1:
        raise WorkflowError("max_cycles must be positive")
    interval = min(float(settings.supervisor_interval_seconds), MAX_REPLAY_INTERVAL_SECONDS) if interval_seconds is None else float(interval_seconds)
    if interval <= 0 or interval > MAX_REPLAY_INTERVAL_SECONDS:
        raise WorkflowError("watch interval must be between 0 and 2 seconds")
    directory = orchestrator_dir(settings, orchestrator_id)
    lock_path = directory / LOCK_NAME
    prior = _read_lock_metadata(lock_path)
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    stream = os.fdopen(descriptor, "a+b")
    try:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WorkflowError("orchestrator supervisor already active") from exc
        prior_state = _prior_owner_state(prior)
        if prior_state == "unknown" and not operator_override:
            raise WorkflowError("cannot establish stale supervisor ownership; use --operator-override")
        owner = _current_identity()
        _write_lock_metadata(
            stream,
            {
                "schema": LOCK_METADATA_SCHEMA,
                "schema_version": 1,
                **owner,
                "acquired_at": utc_now(),
                "recovered_from": prior_state if prior_state != "none" else None,
            },
        )
        stop = threading.Event()
        prior = {name: signal.getsignal(name) for name in (signal.SIGTERM, signal.SIGINT)}
        for name in prior:
            signal.signal(name, lambda _signum, _frame: stop.set())
        cycles = 0
        failures = 0
        total_advanced = 0
        total_imported = 0
        status, status_reconstructed = _status_from_events(directory)
        _record(
            directory,
            "startup",
            orchestrator_id=orchestrator_id,
            lock_recovered=prior_state not in {"none", "alive"},
            prior_owner_state=prior_state,
            status_reconstructed=status_reconstructed,
        )
        status.update({"state": "running", "updated_at": utc_now(), "reconstructed": status_reconstructed})
        _write_status(directory, status)
        last_report: dict[str, Any] = {}
        try:
            while not stop.is_set() and (max_cycles is None or cycles < max_cycles):
                try:
                    report = replay_registered(settings, orchestrator_id, batch_size=batch_size, max_per_child=max_per_child)
                    failures = 0
                    cycles += 1
                    total_advanced += report["advanced"]
                    total_imported += report["count"]
                    last_report = report
                    notification = _notify_orchestrator(report)
                    _record(
                        directory,
                        "replay",
                        cycle=cycles,
                        advanced=report["advanced"],
                        imported=report["count"],
                        children=report["children"],
                        pending_acknowledgements_count=len(report["pending_acknowledgements"]),
                        pending_actions_count=len(report["pending_actions"]),
                        pending_acknowledgements=report["pending_acknowledgements"],
                        pending_acknowledgement_digests=report["pending_acknowledgement_digests"],
                        pending_actions=report["pending_actions"],
                        pending_action_digests=report["pending_action_digests"],
                        **notification,
                    )
                    status.update({
                        "state": "running",
                        "cycle": cycles,
                        "advanced": total_advanced,
                        "imported": total_imported,
                        "pending_acknowledgements": report["pending_acknowledgements"],
                        "pending_acknowledgement_digests": report["pending_acknowledgement_digests"],
                        "pending_actions": report["pending_actions"],
                        "pending_action_digests": report["pending_action_digests"],
                        "updated_at": utc_now(),
                    })
                    _write_status(directory, status)
                except (OrchestratorInboxError, OSError, WorkflowError) as exc:
                    failures += 1
                    cycles += 1
                    _record(directory, "error", cycle=cycles, error_type=type(exc).__name__)
                    if max_cycles is not None and cycles >= max_cycles:
                        break
                    stop.wait(min(interval * (2 ** min(failures - 1, 4)), MAX_REPLAY_INTERVAL_SECONDS))
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
            _record(
                directory,
                reason,
                cycles=cycles,
                advanced=total_advanced,
                imported=total_imported,
                pending_acknowledgements=last_report.get("pending_acknowledgements", []),
                pending_acknowledgement_digests=last_report.get("pending_acknowledgement_digests", {}),
                pending_actions=last_report.get("pending_actions", []),
                pending_action_digests=last_report.get("pending_action_digests", {}),
            )
            status.update({"state": reason, "updated_at": utc_now()})
            _write_status(directory, status)
            return {
                "orchestrator_id": orchestrator_id,
                "state": reason,
                "cycles": cycles,
                "advanced": total_advanced,
                "imported": total_imported,
                "reconstructed": bool(last_report.get("reconstructed", False)),
                "pending_acknowledgements": last_report.get("pending_acknowledgements", []),
                "pending_acknowledgement_digests": last_report.get("pending_acknowledgement_digests", {}),
                "pending_actions": last_report.get("pending_actions", []),
                "pending_action_digests": last_report.get("pending_action_digests", {}),
            }
        finally:
            for name, handler in prior.items():
                signal.signal(name, handler)
    finally:
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()
