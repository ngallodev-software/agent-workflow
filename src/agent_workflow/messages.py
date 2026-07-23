"""Durable, ordered message exchange logs for a single workflow run."""

from __future__ import annotations

import fcntl
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .util import utc_now, validate_id


MESSAGE_SCHEMA = "agent-workflow/session-message/v1"
MESSAGE_LOG_NAME = "messages.jsonl"
MAX_CONTENT_CHARS = 16_384
_DIRECTIONS = frozenset({"parent_to_child", "child_to_parent"})
_KINDS = frozenset({"steer", "progress", "ack", "error"})
_REQUIRED_FIELDS = frozenset(
    {
        "schema",
        "sequence",
        "message_id",
        "session_id",
        "timestamp",
        "direction",
        "kind",
        "actor",
        "content",
    }
)
_OPTIONAL_FIELDS = frozenset({"correlation_id"})


def message_log_path(run_dir: Path) -> Path:
    """Return the fixed append-only message-log path for *run_dir*."""
    return run_dir / MESSAGE_LOG_NAME


def _uuid(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise WorkflowError(f"{label} must be a UUID string")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise WorkflowError(f"{label} must be a UUID string") from exc
    if str(parsed) != value.lower():
        raise WorkflowError(f"{label} must be a canonical UUID string")
    return value


def validate_message(value: object, *, expected_sequence: int | None = None) -> dict[str, Any]:
    """Validate one persisted message record and return it unchanged."""
    if not isinstance(value, dict):
        raise WorkflowError("session message must be a JSON object")
    unknown = set(value) - _REQUIRED_FIELDS - _OPTIONAL_FIELDS
    missing = _REQUIRED_FIELDS - set(value)
    if missing or unknown:
        raise WorkflowError(
            "invalid session message fields: "
            f"missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    if value["schema"] != MESSAGE_SCHEMA:
        raise WorkflowError(f"unsupported session message schema: {value['schema']!r}")
    sequence = value["sequence"]
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise WorkflowError("session message sequence must be a positive integer")
    if expected_sequence is not None and sequence != expected_sequence:
        raise WorkflowError(
            f"session message sequence mismatch: expected {expected_sequence}, got {sequence}"
        )
    _uuid(value["message_id"], "message_id")
    session_id = value["session_id"]
    actor = value["actor"]
    if not isinstance(session_id, str):
        raise WorkflowError("session_id must be a string")
    if not isinstance(actor, str):
        raise WorkflowError("actor must be a string")
    validate_id(session_id, "session ID")
    validate_id(actor, "actor ID")
    timestamp = value["timestamp"]
    if not isinstance(timestamp, str) or not timestamp:
        raise WorkflowError("session message timestamp must be non-empty")
    if value["direction"] not in _DIRECTIONS:
        raise WorkflowError("invalid session message direction")
    if value["kind"] not in _KINDS:
        raise WorkflowError("invalid session message kind")
    content = value["content"]
    if not isinstance(content, str) or not content:
        raise WorkflowError("session message content must be non-empty")
    if len(content) > MAX_CONTENT_CHARS:
        raise WorkflowError(f"session message content exceeds {MAX_CONTENT_CHARS} characters")
    if "correlation_id" in value and value["correlation_id"] is not None:
        _uuid(value["correlation_id"], "correlation_id")
    return value


def _read_locked(stream: Any) -> list[dict[str, Any]]:
    stream.seek(0)
    messages: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(stream, start=1):
        if not raw_line.strip():
            raise WorkflowError(f"blank session message record at line {line_number}")
        try:
            value = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"invalid session message JSON at line {line_number}: {exc}") from exc
        messages.append(validate_message(value, expected_sequence=line_number))
    return messages


def append_message(
    run_dir: Path,
    *,
    session_id: str,
    direction: str,
    kind: str,
    actor: str,
    content: str,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Append and fsync a message, allocating its sequence under an exclusive lock."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = message_log_path(run_dir)
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            sequence = len(_read_locked(stream)) + 1
            message: dict[str, Any] = {
                "schema": MESSAGE_SCHEMA,
                "sequence": sequence,
                "message_id": str(uuid.uuid4()),
                "session_id": session_id,
                "timestamp": utc_now(),
                "direction": direction,
                "kind": kind,
                "actor": actor,
                "content": content,
            }
            if correlation_id is not None:
                message["correlation_id"] = correlation_id
            validate_message(message, expected_sequence=sequence)
            stream.seek(0, os.SEEK_END)
            stream.write(json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    return message


def replay_messages(run_dir: Path, *, after_sequence: int = 0) -> list[dict[str, Any]]:
    """Validate and replay all messages with a sequence greater than *after_sequence*."""
    if not isinstance(after_sequence, int) or isinstance(after_sequence, bool) or after_sequence < 0:
        raise WorkflowError("after_sequence must be a non-negative integer")
    path = message_log_path(run_dir)
    try:
        with path.open("rb") as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
            try:
                messages = _read_locked(stream)
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    except FileNotFoundError:
        return []
    except OSError as exc:
        raise WorkflowError(f"cannot read session messages {path}: {exc}") from exc
    return [message for message in messages if message["sequence"] > after_sequence]


def wait_for_messages(
    run_dir: Path,
    *,
    after_sequence: int = 0,
    timeout_seconds: float | None = None,
    poll_seconds: float = 0.2,
) -> list[dict[str, Any]]:
    """Block until durable records appear, then replay them in sequence order.

    The caller blocks rather than repeatedly issuing status commands. Replay is
    authoritative because a future wakeup accelerator may lose signals.
    """
    if timeout_seconds is not None and timeout_seconds < 0:
        raise WorkflowError("timeout_seconds must be non-negative")
    if poll_seconds <= 0:
        raise WorkflowError("poll_seconds must be positive")
    deadline = time.monotonic() + timeout_seconds if timeout_seconds is not None else None
    while True:
        messages = replay_messages(run_dir, after_sequence=after_sequence)
        if messages:
            return messages
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return []
            time.sleep(min(poll_seconds, remaining))
        else:
            time.sleep(poll_seconds)
