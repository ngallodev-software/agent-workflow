"""Durable, ordered message exchange logs for a single workflow run."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import time
import uuid
from pathlib import Path
from typing import Any, Callable

from .errors import WorkflowError
from .util import atomic_write_json, utc_now, validate_id


MESSAGE_SCHEMA = "agent-workflow/session-message/v1"
MESSAGE_LOG_NAME = "messages.jsonl"
MAX_CONTENT_CHARS = 16_384
_DIRECTIONS = frozenset({"parent_to_child", "child_to_parent"})
_KINDS = frozenset({"steer", "progress", "ack", "error", "task_complete"})
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
_KIND_DIRECTIONS = {
    "steer": "parent_to_child",
    "progress": "child_to_parent",
    "ack": "child_to_parent",
    "error": "child_to_parent",
    "task_complete": "child_to_parent",
}

CONTROL_BRIDGE_SCHEMA = "agent-workflow/control-intent/v1"
CONTROL_BRIDGE_ENV = "AGENT_WORKFLOW_CONTROL_BRIDGE"
CONTROL_BRIDGE_MAX_BYTES = 32 * 1024
_SHA256_HEX_LENGTH = 64


def canonical_message_bytes(message: dict[str, Any]) -> bytes:
    """Return the bytes used to identify an immutable source message."""
    validate_message(message)
    return json.dumps(
        message, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def message_digest(message: dict[str, Any]) -> str:
    """Return a digest bound to the complete canonical source record."""
    return "sha256:" + hashlib.sha256(canonical_message_bytes(message)).hexdigest()


def _bridge_path() -> Path | None:
    value = os.environ.get(CONTROL_BRIDGE_ENV)
    return Path(value) if value else None


def bridge_available(session_id: str | None = None) -> bool:
    """Return whether the current process is the bridged child for a run.

    The bridge variables are inherited by the operator shell that launched a
    run.  Merely seeing a writable directory must not redirect host-side CLI
    commands into that directory.
    """
    if session_id is not None and os.environ.get("AGENT_WORKFLOW_SESSION_ID") != session_id:
        return False
    path = _bridge_path()
    return path is not None and path.is_dir() and not path.is_symlink()


def bridge_required(session_id: str) -> bool:
    """Identify a launched child so missing host bridge access is explicit."""
    return os.environ.get("AGENT_WORKFLOW_SESSION_ID") == session_id


def write_control_intent(
    *, session_id: str, kind: str, actor: str, content: str,
    correlation_id: str | None = None,
    outcome: str | None = None,
) -> dict[str, Any]:
    """Write one bounded child intent without touching host state or tmux."""
    bridge = _bridge_path()
    if bridge is None:
        raise WorkflowError("control bridge unavailable")
    try:
        mode = bridge.lstat().st_mode
    except OSError as exc:
        raise WorkflowError("control bridge unavailable") from exc
    if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
        raise WorkflowError("control bridge must be a real directory")
    validate_id(session_id, "session ID")
    validate_id(actor, "actor ID")
    if kind not in {"progress", "ack", "task_complete"}:
        raise WorkflowError("unsupported bridged control kind")
    if kind == "ack" and correlation_id is None:
        raise WorkflowError("ack messages require correlation_id")
    if kind != "ack" and correlation_id is not None:
        raise WorkflowError("only ack messages may include correlation_id")
    if kind == "ack" and outcome not in {"applied", "rejected"}:
        raise WorkflowError("ack control intents require applied or rejected outcome")
    if kind != "ack" and outcome is not None:
        raise WorkflowError("only ack control intents may include outcome")
    if correlation_id is not None:
        _uuid(correlation_id, "correlation_id")
    if not isinstance(content, str) or not content or len(content) > MAX_CONTENT_CHARS:
        raise WorkflowError("invalid control intent content")
    completion_sha256: str | None = None
    if kind == "task_complete":
        handoff_value = os.environ.get("AGENT_WORKFLOW_HANDOFF_DIR")
        if not handoff_value:
            raise WorkflowError("task completion requires a completion handoff directory")
        completion_path = Path(handoff_value) / "completion.json"
        try:
            mode = completion_path.lstat().st_mode
        except OSError as exc:
            raise WorkflowError("task completion requires a completion handoff") from exc
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise WorkflowError("task completion handoff must be a regular non-symlink file")
        try:
            completion_sha256 = hashlib.sha256(completion_path.read_bytes()).hexdigest()
        except OSError as exc:
            raise WorkflowError("cannot read task completion handoff") from exc
    sequence = 1
    for candidate in bridge.glob("intent-*.json"):
        try:
            sequence = max(sequence, int(candidate.stem.rsplit("-", 1)[1]) + 1)
        except (ValueError, IndexError):
            continue
    intent = {
        "schema": CONTROL_BRIDGE_SCHEMA,
        "request_id": str(uuid.uuid4()),
        "session_id": session_id,
        "sequence": sequence,
        "kind": kind,
        "actor": actor,
        "content": content,
        "correlation_id": correlation_id,
        "outcome": outcome,
        "completion_sha256": completion_sha256,
    }
    intent["digest"] = "sha256:" + hashlib.sha256(
        json.dumps(intent, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    target = bridge / f"intent-{intent['request_id']}-{sequence}.json"
    atomic_write_json(target, intent, mode=0o600)
    if target.stat().st_size > CONTROL_BRIDGE_MAX_BYTES:
        target.unlink(missing_ok=True)
        raise WorkflowError("control intent exceeds size limit")
    return {"outcome": "delivered", "request_id": intent["request_id"], "sequence": sequence}


def message_log_path(run_dir: Path) -> Path:
    """Return the fixed append-only message-log path for a real run directory."""
    try:
        mode = run_dir.lstat().st_mode
    except FileNotFoundError:
        run_dir.mkdir(parents=True, exist_ok=True)
        mode = run_dir.lstat().st_mode
    except OSError as exc:
        raise WorkflowError(f"cannot inspect run directory {run_dir}: {exc}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise WorkflowError("message run directory must be a real directory, not a symlink")
    path = run_dir / MESSAGE_LOG_NAME
    if path.exists() or path.is_symlink():
        try:
            path_mode = path.lstat().st_mode
        except OSError as exc:
            raise WorkflowError(f"cannot inspect session message log {path}: {exc}") from exc
        if stat.S_ISLNK(path_mode) or not stat.S_ISREG(path_mode):
            raise WorkflowError("session message log must be a regular non-symlink file")
    return path


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
    expected_direction = _KIND_DIRECTIONS[value["kind"]]
    if value["direction"] != expected_direction:
        raise WorkflowError(
            f"{value['kind']} messages must use {expected_direction} direction"
        )
    content = value["content"]
    if not isinstance(content, str) or not content:
        raise WorkflowError("session message content must be non-empty")
    if len(content) > MAX_CONTENT_CHARS:
        raise WorkflowError(f"session message content exceeds {MAX_CONTENT_CHARS} characters")
    correlation_id = value.get("correlation_id")
    if correlation_id is not None:
        _uuid(correlation_id, "correlation_id")
    if value["kind"] == "ack" and correlation_id is None:
        raise WorkflowError("ack messages require correlation_id")
    if value["kind"] not in {"ack", "error"} and correlation_id is not None:
        raise WorkflowError("only ack and error messages may include correlation_id")
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
        message = validate_message(value, expected_sequence=line_number)
        if messages and message["session_id"] != messages[0]["session_id"]:
            raise WorkflowError("session message log contains mixed session IDs")
        if any(item["message_id"] == message["message_id"] for item in messages):
            raise WorkflowError("session message log contains duplicate message_id")
        if message["kind"] == "ack":
            correlation_id = message["correlation_id"]
            steer = next(
                (item for item in messages if item["message_id"] == correlation_id),
                None,
            )
            if steer is None or steer["kind"] != "steer":
                raise WorkflowError("ack correlation_id must reference an earlier steer request")
            if any(
                item["kind"] == "ack" and item.get("correlation_id") == correlation_id
                for item in messages
            ):
                raise WorkflowError("steer request is already acknowledged")
        messages.append(message)
    return messages


def _validate_append_semantics(existing: list[dict[str, Any]], message: dict[str, Any]) -> None:
    if existing and message["session_id"] != existing[0]["session_id"]:
        raise WorkflowError("cannot append a different session ID to message log")
    if any(item["message_id"] == message["message_id"] for item in existing):
        raise WorkflowError("duplicate message_id")
    if message["kind"] == "ack":
        correlation_id = message["correlation_id"]
        steer = next((item for item in existing if item["message_id"] == correlation_id), None)
        if steer is None or steer["kind"] != "steer":
            raise WorkflowError("ack correlation_id must reference an existing steer request")
        if any(item["kind"] == "ack" and item.get("correlation_id") == correlation_id for item in existing):
            raise WorkflowError("steer request is already acknowledged")


def append_message(
    run_dir: Path,
    *,
    session_id: str,
    direction: str,
    kind: str,
    actor: str,
    content: str,
    correlation_id: str | None = None,
    after_commit: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Append and fsync a message, allocating its sequence under an exclusive lock.

    ``after_commit`` is a best-effort notification seam.  It runs only after
    the file is closed and its lock is released; failures cannot undo a durable
    append or turn it into an error.
    """
    path = message_log_path(run_dir)
    with path.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            existing = _read_locked(stream)
            if existing and any(item["session_id"] != session_id for item in existing):
                raise WorkflowError("cannot append a different session ID to message log")
            sequence = len(existing) + 1
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
            _validate_append_semantics(existing, message)
            stream.seek(0, os.SEEK_END)
            stream.write(json.dumps(message, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    if after_commit is not None:
        try:
            after_commit(message)
        except Exception:
            pass
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


def replay_messages_descriptor(descriptor: int, *, after_sequence: int = 0) -> list[dict[str, Any]]:
    """Replay messages from an already opened descriptor without reopening a path."""
    if not isinstance(after_sequence, int) or isinstance(after_sequence, bool) or after_sequence < 0:
        raise WorkflowError("after_sequence must be a non-negative integer")
    with os.fdopen(os.dup(descriptor), "rb") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_SH)
        try:
            messages = _read_locked(stream)
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    return [message for message in messages if message["sequence"] > after_sequence]


def wait_for_messages(
    run_dir: Path,
    *,
    after_sequence: int = 0,
    timeout_seconds: float | None = None,
    poll_seconds: float = 0.2,
    wakeup_channel: str | None = None,
    wait_for_wakeup: Callable[[str, float], bool] | None = None,
) -> list[dict[str, Any]]:
    """Block until durable records appear, then replay them in sequence order.

    The caller blocks rather than repeatedly issuing status commands. Replay is
    authoritative because a wakeup accelerator may lose signals.  When a
    waiter is supplied it is only a bounded hint; polling remains the fallback.
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
        remaining = deadline - time.monotonic() if deadline is not None else None
        if remaining is not None and remaining <= 0:
            return []
        wait_seconds = min(poll_seconds, remaining) if remaining is not None else poll_seconds
        started = time.monotonic()
        woke = False
        if wakeup_channel is not None and wait_for_wakeup is not None:
            try:
                woke = bool(wait_for_wakeup(wakeup_channel, wait_seconds))
            except Exception:
                pass
        elapsed = time.monotonic() - started
        # An unavailable/erroring waiter can return immediately.  Preserve the
        # ordinary polling cadence instead of turning that into a busy loop.
        if not woke and elapsed < wait_seconds:
            time.sleep(wait_seconds - elapsed)
