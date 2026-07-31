from __future__ import annotations

from collections.abc import Sequence
from typing import Any


_FAILURE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("command_not_found", ("command not found", "executable not found", "no such file or directory")),
    ("permission_wait", ("permission required", "approval required", "requires approval", "waiting for approval", "allow this command", "do you want to proceed")),
    ("permission_denied", ("permission denied", "operation not permitted", "sandbox denied", "access denied")),
    ("authentication_missing", ("unauthorized", "authentication", "api key", "credential", "login required")),
    ("rate_limited", ("rate limit", "too many requests", "http 429", "retry-after")),
    ("network_unavailable", ("network is unreachable", "temporary failure in name resolution", "connection refused", "connection timed out", "dns")),
    ("dependency_unavailable", ("no matching distribution found", "could not find a version", "module not found", "modulenotfounderror", "package is not available")),
    ("disk_exhausted", ("no space left on device", "disk quota exceeded")),
    ("memory_exhausted", ("out of memory", "oom-kill", "cannot allocate memory")),
    ("output_capture_exhausted", ("capture limit exceeded", "output truncated", "stream drain deadline exceeded")),
    ("executor_protocol_error", ("invalid event", "protocol error", "unsupported stream format")),
    ("completion_invalid", ("completion:", "completion handoff", "substantive completion")),
    ("contract_invalid", ("invalid json", "schema", "contract", "digest mismatch")),
)


def classify_failure(
    *, exit_code: int | None, stderr: str = "", errors: Sequence[str] = ()
) -> str | None:
    if exit_code in (None, 0) and not errors:
        return None
    text = (stderr + "\n" + "\n".join(errors)).lower()
    for category, needles in _FAILURE_RULES:
        if any(needle in text for needle in needles):
            return category
    if exit_code == 124:
        return "timeout"
    if exit_code in {130, 143}:
        return "interrupted"
    return "unclassified"


def diagnose_observation(observation: dict[str, Any]) -> tuple[str | None, str, str]:
    """Return ``(category, severity, summary)`` for a live observation."""
    observed = str(observation.get("observed_state", "unknown"))
    permission_state = observation.get("permission_state")
    process = observation.get("latest_health", {}).get("executor", {})
    host = observation.get("latest_health", {}).get("host", {})

    if permission_state == "pending":
        return "permission_wait", "high", "executor is waiting for an authority decision"
    if observed == "possibly_stalled":
        return "process_alive_no_progress", "high", "executor is alive but semantic progress is stale"
    if observed == "orphaned":
        return "process_missing", "high", "durable run is active but its tmux/process presentation is gone"
    if observed == "terminal_unavailable":
        return "terminal_unavailable", "medium", "tmux state could not be inspected"
    if process.get("alive") is False and observed in {"running", "blocked_permission"}:
        return "process_missing", "high", "executor process is no longer alive"
    disk_free = host.get("disk_free_bytes")
    if isinstance(disk_free, int) and disk_free < 512 * 1024 * 1024:
        return "resource_pressure", "high", "less than 512 MiB remains on the run filesystem"
    available = host.get("available_memory_bytes")
    if isinstance(available, int) and available < 256 * 1024 * 1024:
        return "resource_pressure", "medium", "less than 256 MiB of host memory is available"
    if observation.get("output_capture_exhausted"):
        return "output_capture_exhausted", "high", "executor output exceeded the durable capture bound"
    return None, "info", "no actionable incident detected"
