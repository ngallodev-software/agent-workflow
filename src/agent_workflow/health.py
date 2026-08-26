"""Durable run-health, incident, permission, and remediation evidence.

The module deliberately keeps collection local and dependency-free. Linux
``/proc`` fields are collected when available; unsupported values remain
``None`` so callers never invent portability evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Iterable

from .contracts import validate_instance
from .errors import WorkflowError
from .journal import JournalCapacityError, append_jsonl, read_jsonl
from .process import redact_text
from .util import atomic_write_json, utc_now

RUN_HEALTH_SCHEMA = "agent-workflow/run-health-sample/v2"
INCIDENT_SCHEMA = "agent-workflow/incident-event/v1"
PERMISSION_SCHEMA = "agent-workflow/permission-event/v1"
REMEDIATION_SCHEMA = "agent-workflow/remediation-event/v1"
PROCESS_RESULT_SCHEMA = "agent-workflow/process-result/v1"

MAX_HEALTH_JOURNAL_BYTES = 8 * 1024 * 1024
MAX_CONTROL_JOURNAL_BYTES = 8 * 1024 * 1024

_PERMISSION_PENDING = (
    "permission required",
    "approval required",
    "requires approval",
    "allow this command",
    "allow this action",
    "do you want to proceed",
    "would you like to proceed",
    "press enter to continue",
    "waiting for approval",
    "permission mode",
)
_PERMISSION_DENIED = (
    "permission denied",
    "operation not permitted",
    "sandbox denied",
    "access denied",
    "not authorized",
    "unauthorized",
)


def _validate_health_record(value: object, line_number: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError(f"JSONL record must be an object at line {line_number}")
    schema_id = value.get("schema")
    if not isinstance(schema_id, str):
        raise WorkflowError(f"JSONL record has no schema at line {line_number}")
    validate_instance(value, schema_id, artifact=f"durable journal:{line_number}")
    return value


def _safe_append_jsonl(path: Path, value: dict[str, Any], *, max_bytes: int) -> bool:
    """Append one validated record; return False only when the bounded journal is full."""
    try:
        append_jsonl(
            path,
            value,
            validator=_validate_health_record,
            max_bytes=max_bytes,
        )
    except JournalCapacityError:
        return False
    return True



def write_process_result(path: Path, value: dict[str, Any]) -> dict[str, Any]:
    """Validate and atomically install one process result contract."""
    validate_instance(value, PROCESS_RESULT_SCHEMA, artifact=str(path))
    atomic_write_json(path, value)
    return value

def read_events(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    values = read_jsonl(path, validator=_validate_health_record, missing_ok=True)
    if limit is not None:
        return values[-max(0, limit) :] if limit > 0 else []
    return values


def last_event(path: Path) -> dict[str, Any] | None:
    values = read_events(path, limit=1)
    return values[-1] if values else None


def _file_size(path: Path) -> int | None:
    try:
        return path.stat().st_size if path.is_file() else None
    except OSError:
        return None


def _file_mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime if path.is_file() else None
    except OSError:
        return None


def _iso_from_epoch(value: float | None) -> str | None:
    if value is None:
        return None
    from datetime import datetime, timezone

    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def semantic_progress(run_dir: Path) -> dict[str, Any]:
    candidates = {
        "output": run_dir / "output.log",
        "stderr": run_dir / "executor-stderr.log",
        "executor_event": run_dir / "executor-events.jsonl",
        "message": run_dir / "messages.jsonl",
        "control_intent": run_dir / "control-intents.jsonl",
        "steering_delivery": run_dir / "steering-delivery.jsonl",
        "completion": run_dir / "completion.json",
    }
    activity = {name: _file_mtime(path) for name, path in candidates.items()}
    present = {name: value for name, value in activity.items() if value is not None}
    latest_name = max(present, key=present.get) if present else None
    latest_epoch = present.get(latest_name) if latest_name else None
    return {
        "last_semantic_progress_at": _iso_from_epoch(latest_epoch),
        "seconds_since_semantic_progress": (
            round(max(0.0, time.time() - latest_epoch), 3)
            if latest_epoch is not None
            else None
        ),
        "last_semantic_progress_source": latest_name,
    }


def _read_proc_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def process_sample(pid: int | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "pid": pid,
        "alive": None,
        "state": None,
        "parent_pid": None,
        "process_start_ticks": None,
        "cpu_user_seconds": None,
        "cpu_system_seconds": None,
        "rss_bytes": None,
        "peak_rss_bytes": None,
        "threads": None,
        "read_bytes": None,
        "write_bytes": None,
        "open_fd_count": None,
        "child_process_count": None,
        "collector": "portable",
    }
    if not isinstance(pid, int) or pid <= 0:
        return result
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        result["alive"] = False
        return result
    except PermissionError:
        result["alive"] = True
    else:
        result["alive"] = True

    proc = Path("/proc") / str(pid)
    stat_text = _read_proc_text(proc / "stat")
    if stat_text is None:
        return result
    result["collector"] = "linux-procfs"
    try:
        close = stat_text.rfind(")")
        fields = stat_text[close + 2 :].split()
        result["state"] = fields[0]
        result["parent_pid"] = int(fields[1])
        ticks = float(os.sysconf(os.sysconf_names["SC_CLK_TCK"]))
        page_size = int(os.sysconf("SC_PAGE_SIZE"))
        result["cpu_user_seconds"] = round(int(fields[11]) / ticks, 6)
        result["cpu_system_seconds"] = round(int(fields[12]) / ticks, 6)
        result["process_start_ticks"] = int(fields[19])
        result["rss_bytes"] = int(fields[21]) * page_size
    except (ValueError, IndexError, OSError, KeyError):
        pass

    status_text = _read_proc_text(proc / "status") or ""
    for line in status_text.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        parts = value.strip().split()
        if not parts:
            continue
        try:
            if key == "VmRSS":
                result["rss_bytes"] = int(parts[0]) * 1024
            elif key == "VmHWM":
                result["peak_rss_bytes"] = int(parts[0]) * 1024
            elif key == "Threads":
                result["threads"] = int(parts[0])
        except ValueError:
            continue

    io_text = _read_proc_text(proc / "io") or ""
    for line in io_text.splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            continue
        try:
            if key == "read_bytes":
                result["read_bytes"] = int(value.strip())
            elif key == "write_bytes":
                result["write_bytes"] = int(value.strip())
        except ValueError:
            continue
    try:
        result["open_fd_count"] = len(list((proc / "fd").iterdir()))
    except OSError:
        pass
    children = _read_proc_text(proc / "task" / str(pid) / "children")
    if children is not None:
        result["child_process_count"] = len(children.split())
    return result


def host_sample(run_dir: Path) -> dict[str, Any]:
    load: list[float | None] = [None, None, None]
    try:
        load = [round(value, 4) for value in os.getloadavg()]
    except (AttributeError, OSError):
        pass
    available_memory: int | None = None
    meminfo = _read_proc_text(Path("/proc/meminfo")) or ""
    for line in meminfo.splitlines():
        if line.startswith("MemAvailable:"):
            try:
                available_memory = int(line.split()[1]) * 1024
            except (ValueError, IndexError):
                pass
            break
    disk_free: int | None = None
    disk_total: int | None = None
    try:
        usage = shutil.disk_usage(run_dir)
        disk_free = usage.free
        disk_total = usage.total
    except OSError:
        pass
    return {
        "load_1m": load[0],
        "load_5m": load[1],
        "load_15m": load[2],
        "available_memory_bytes": available_memory,
        "disk_free_bytes": disk_free,
        "disk_total_bytes": disk_total,
    }


def record_health_sample(
    run_dir: Path,
    *,
    agent_run_id: str,
    runner_pid: int | None,
    executor_pid: int | None,
) -> dict[str, Any]:
    progress = semantic_progress(run_dir)
    sample = {
        "schema": RUN_HEALTH_SCHEMA,
        "agent_run_id": agent_run_id,
        "recorded_at": utc_now(),
        "runner": process_sample(runner_pid),
        "executor": process_sample(executor_pid),
        "host": host_sample(run_dir),
        "output_bytes": _file_size(run_dir / "output.log"),
        "stderr_bytes": _file_size(run_dir / "executor-stderr.log"),
        "executor_event_bytes": _file_size(run_dir / "executor-events.jsonl"),
        **progress,
    }
    stored = _safe_append_jsonl(
        run_dir / "run-health-samples.jsonl",
        sample,
        max_bytes=MAX_HEALTH_JOURNAL_BYTES,
    )
    sample["stored"] = stored
    return sample


def permission_signal(value: str) -> str | None:
    lowered = value.lower()
    if any(needle in lowered for needle in _PERMISSION_DENIED):
        return "denied"
    if any(needle in lowered for needle in _PERMISSION_PENDING):
        return "pending"
    return None


def record_permission_event(
    run_dir: Path,
    *,
    agent_run_id: str,
    state: str,
    source: str,
    evidence_sha256: str,
    policy_rule_id: str | None = None,
) -> dict[str, Any] | None:
    path = run_dir / "permission-events.jsonl"
    prior = last_event(path)
    if prior and prior.get("state") == state and prior.get("evidence_sha256") == evidence_sha256:
        return None
    event = {
        "schema": PERMISSION_SCHEMA,
        "event_id": hashlib.sha256(
            f"{agent_run_id}:{state}:{source}:{evidence_sha256}".encode()
        ).hexdigest()[:24],
        "agent_run_id": agent_run_id,
        "recorded_at": utc_now(),
        "principal": None,
        "operation": "executor_interaction",
        "resource_class": "unknown",
        "target": None,
        "requested_access": None,
        "state": state,
        "source": source,
        "policy_rule_id": policy_rule_id,
        "evidence_sha256": evidence_sha256,
        "remediation_class": "human_authority_required" if state == "pending" else "diagnose_policy",
    }
    _safe_append_jsonl(path, event, max_bytes=MAX_CONTROL_JOURNAL_BYTES)
    return event


def record_incident(
    run_dir: Path,
    *,
    agent_run_id: str,
    category: str,
    severity: str,
    summary: str,
    evidence: dict[str, Any],
) -> dict[str, Any] | None:
    fingerprint = hashlib.sha256(
        json.dumps(
            {"category": category, "evidence": evidence},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    path = run_dir / "incident-events.jsonl"
    prior = last_event(path)
    if prior and prior.get("fingerprint") == fingerprint:
        return None
    event = {
        "schema": INCIDENT_SCHEMA,
        "incident_id": fingerprint[:24],
        "agent_run_id": agent_run_id,
        "recorded_at": utc_now(),
        "category": category,
        "severity": severity,
        "summary": summary,
        "fingerprint": fingerprint,
        "evidence": evidence,
        "state": "open",
    }
    _safe_append_jsonl(path, event, max_bytes=MAX_CONTROL_JOURNAL_BYTES)
    return event


def record_remediation(
    run_dir: Path,
    *,
    agent_run_id: str,
    incident_id: str | None,
    rule_id: str,
    action: str,
    outcome: str,
    reason: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "schema": REMEDIATION_SCHEMA,
        "event_id": hashlib.sha256(
            f"{agent_run_id}:{incident_id}:{rule_id}:{action}:{outcome}:{reason}:{utc_now()}".encode()
        ).hexdigest()[:24],
        "agent_run_id": agent_run_id,
        "incident_id": incident_id,
        "recorded_at": utc_now(),
        "rule_id": rule_id,
        "action": action,
        "outcome": outcome,
        "reason": reason,
        "details": details or {},
    }
    _safe_append_jsonl(
        run_dir / "remediation-events.jsonl",
        event,
        max_bytes=MAX_CONTROL_JOURNAL_BYTES,
    )
    return event


def remediation_count(run_dir: Path, rule_id: str) -> int:
    return sum(
        1
        for event in read_events(run_dir / "remediation-events.jsonl")
        if event.get("rule_id") == rule_id
    )
