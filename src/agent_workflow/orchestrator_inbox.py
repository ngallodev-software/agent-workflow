"""Immutable orchestrator identity registry and durable aggregate inbox.

The registry binds child sessions to their launch and assignment evidence.  The
inbox is a delivery projection: child message journals and lifecycle evidence
remain authoritative for what a child actually did.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping

from .config import Settings
from .contracts import read_contract, read_launch_contract, validate_instance
from .errors import WorkflowError
from .messages import message_digest, validate_message
from .path import read_regular_file
from .state import run_dir
from .util import atomic_write_json, fsync_directory, utc_now, validate_id
from . import tmux


REGISTRY_SCHEMA = "agent-workflow/orchestrator-registry/v1"
EVENT_SCHEMA = "agent-workflow/orchestrator-event/v1"
ACKNOWLEDGEMENT_SCHEMA = "agent-workflow/orchestrator-acknowledgement/v1"
ACTION_SCHEMA = "agent-workflow/orchestrator-action/v1"
REGISTRY_NAME = "registry.json"
INBOX_NAME = "inbox.jsonl"
MAX_RECORD_BYTES = 64 * 1024
MAX_JOURNAL_BYTES = 64 * 1024 * 1024
MAX_REGISTRY_BYTES = 8 * 1024 * 1024
MAX_SUMMARY_CHARS = 16_384
MAX_CHILDREN = 10_000
MAX_READ_EVENTS = 1_000
MAX_SOURCE_RECORDS = 100_000

_EVENT_KINDS = {
    "progress": "agent_progress",
    "task_complete": "agent_idle",
    "error": "agent_error",
}
_REGISTRY_STATES = {"active", "completed", "abandoned"}
_CHILD_STATES = {"active", "completed", "abandoned"}


class OrchestratorInboxError(WorkflowError):
    """A registry or inbox identity conflict that must fail closed."""


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _uuid(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise OrchestratorInboxError(f"{label} must be a UUID string")
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise OrchestratorInboxError(f"{label} must be a UUID string") from exc
    if str(parsed) != value.lower():
        raise OrchestratorInboxError(f"{label} must be a canonical UUID string")
    return value


def _bounded_text(value: object, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value) or len(value) > MAX_SUMMARY_CHARS:
        raise OrchestratorInboxError(f"{label} must be a bounded text value")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise OrchestratorInboxError(f"{label} must be valid UTF-8") from exc
    return value


def _real_directory(path: Path, *, create: bool, label: str) -> Path:
    if create:
        try:
            path.mkdir(parents=True, mode=0o700, exist_ok=True)
        except OSError as exc:
            raise OrchestratorInboxError(f"cannot create {label}: {path}") from exc
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError as exc:
        raise OrchestratorInboxError(f"{label} does not exist: {path}") from exc
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise OrchestratorInboxError(f"{label} must be a real directory")
    return path


def _regular_file(path: Path, *, label: str, required: bool = True) -> Path | None:
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        if not required:
            return None
        raise OrchestratorInboxError(f"{label} does not exist: {path}")
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode) or path.stat().st_nlink != 1:
        raise OrchestratorInboxError(f"{label} must be a regular non-symlink file")
    return path


def _state_root(settings: Settings) -> Path:
    return _real_directory(settings.state_root, create=True, label="state root")


def orchestrator_key(orchestrator_id: str) -> str:
    """Return the non-sensitive stable directory/channel component."""
    validate_id(orchestrator_id, "orchestrator ID")
    return hashlib.sha256(orchestrator_id.encode("utf-8")).hexdigest()


def orchestrator_wakeup_channel(orchestrator_id: str) -> str:
    return tmux.orchestrator_wakeup_channel(orchestrator_id)


def orchestrator_dir(settings: Settings, orchestrator_id: str, *, create: bool = False) -> Path:
    root = _real_directory(_state_root(settings) / "orchestrators", create=create, label="orchestrator root")
    path = root / orchestrator_key(orchestrator_id)
    return _real_directory(path, create=create, label="orchestrator directory")


def _registry_identity(orchestrator_id: str, workflow_id: str | None) -> str:
    return _digest({"schema": "agent-workflow/orchestrator-identity/v1", "orchestrator_id": orchestrator_id, "workflow_id": workflow_id})


def _validate_registry(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OrchestratorInboxError("orchestrator registry must be a JSON object")
    validate_instance(value, REGISTRY_SCHEMA, artifact="orchestrator registry")
    return value


def _validate_event(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OrchestratorInboxError("orchestrator event must be a JSON object")
    validate_instance(value, EVENT_SCHEMA, artifact="orchestrator inbox event")
    _uuid(value["event_id"], "event_id")
    _uuid(value["source_message_id"], "source_message_id")
    if value.get("assignment_id") is not None:
        _uuid(value["assignment_id"], "assignment_id")
    return value


def _read_registry(settings: Settings, orchestrator_id: str) -> dict[str, Any]:
    path = orchestrator_dir(settings, orchestrator_id) / REGISTRY_NAME
    _regular_file(path, label="orchestrator registry")
    try:
        value = json.loads(read_regular_file(path, max_bytes=MAX_REGISTRY_BYTES).data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
        raise OrchestratorInboxError("cannot read orchestrator registry") from exc
    registry = _validate_registry(value)
    if registry["identity_digest"] != _registry_identity(orchestrator_id, registry.get("workflow_id")):
        raise OrchestratorInboxError("orchestrator registry identity digest does not match")
    return registry


def create_registry(settings: Settings, orchestrator_id: str, *, workflow_id: str | None = None) -> dict[str, Any]:
    validate_id(orchestrator_id, "orchestrator ID")
    if workflow_id is not None:
        validate_id(workflow_id, "workflow ID")
    directory = orchestrator_dir(settings, orchestrator_id, create=True)
    path = directory / REGISTRY_NAME
    existing = _regular_file(path, label="orchestrator registry", required=False)
    if existing is not None:
        prior = _read_registry(settings, orchestrator_id)
        if prior.get("workflow_id") != workflow_id:
            raise OrchestratorInboxError("orchestrator registry already exists with a different identity")
        return {"registry": prior, "path": str(path), "wakeup_channel": orchestrator_wakeup_channel(orchestrator_id)}
    now = utc_now()
    registry = {
        "schema": REGISTRY_SCHEMA,
        "schema_version": 1,
        "orchestrator_id": orchestrator_id,
        "workflow_id": workflow_id,
        "principal": "orchestrator",
        "identity_digest": _registry_identity(orchestrator_id, workflow_id),
        "state": "active",
        "created_at": now,
        "updated_at": now,
        "children": [],
    }
    _validate_registry(registry)
    atomic_write_json(path, registry, mode=0o600)
    fsync_directory(directory)
    # Create the append-only authority eagerly so a missing inbox cannot be
    # confused with an uninitialized registry after a restart.
    _append_records(directory / INBOX_NAME, [], expected_schema=EVENT_SCHEMA)
    return {"registry": registry, "path": str(path), "wakeup_channel": orchestrator_wakeup_channel(orchestrator_id)}


def _read_jsonl(path: Path, *, schema: str, max_records: int) -> list[dict[str, Any]]:
    _regular_file(path, label=f"{path.name} journal")
    try:
        raw = read_regular_file(path, max_bytes=MAX_JOURNAL_BYTES).data
    except WorkflowError as exc:
        raise OrchestratorInboxError(f"cannot read {path.name}") from exc
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(raw.splitlines(), start=1):
        if not raw_line.strip():
            raise OrchestratorInboxError(f"blank record in {path.name} line {line_number}")
        if len(raw_line) > MAX_RECORD_BYTES:
            raise OrchestratorInboxError(f"{path.name} record exceeds bounded size")
        try:
            value = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OrchestratorInboxError(f"invalid UTF-8 or JSON in {path.name} line {line_number}") from exc
        if not isinstance(value, dict):
            raise OrchestratorInboxError(f"{path.name} line {line_number} is not an object")
        if schema == EVENT_SCHEMA:
            record = _validate_event(value)
            if record["sequence"] != line_number:
                raise OrchestratorInboxError(f"inbox sequence mismatch at line {line_number}")
        elif schema == "agent-workflow/session-message/v1":
            record = validate_message(value, expected_sequence=line_number)
        elif schema == "agent-workflow/lifecycle-event/v1":
            required = {"schema", "sequence", "timestamp", "dimension", "prior", "new", "actor", "reason", "receipt_refs"}
            if set(value) != required or value.get("schema") != schema or value.get("sequence") != line_number:
                raise OrchestratorInboxError(f"invalid lifecycle evidence at line {line_number}")
            if not isinstance(value.get("receipt_refs"), list) or not all(isinstance(item, str) for item in value["receipt_refs"]):
                raise OrchestratorInboxError(f"invalid lifecycle evidence references at line {line_number}")
            record = value
        else:
            validate_instance(value, schema, artifact=f"{path.name} record")
            record = value
        records.append(record)
        if len(records) > max_records:
            raise OrchestratorInboxError(f"{path.name} exceeds the bounded record limit")
    return records


def _append_records(path: Path, records: Iterable[Mapping[str, Any]], *, expected_schema: str) -> None:
    directory = _real_directory(path.parent, create=True, label="journal parent")
    encoded_records = []
    for record in records:
        value = dict(record)
        if expected_schema == EVENT_SCHEMA:
            _validate_event(value)
        else:
            validate_instance(value, expected_schema, artifact="journal record")
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(encoded) > MAX_RECORD_BYTES:
            raise OrchestratorInboxError("journal record exceeds bounded size")
        encoded_records.append(encoded)
    _regular_file(path, label=f"{path.name} journal", required=False)
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise OrchestratorInboxError(f"cannot open {path.name} without following links") from exc
    with os.fdopen(descriptor, "a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            for encoded in encoded_records:
                stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    fsync_directory(directory)


def _write_registry(settings: Settings, registry: dict[str, Any]) -> None:
    _validate_registry(registry)
    directory = orchestrator_dir(settings, registry["orchestrator_id"])
    lock = directory / ".registry.lock"
    _append_records(lock, [], expected_schema=EVENT_SCHEMA)
    with lock.open("a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            atomic_write_json(directory / REGISTRY_NAME, registry, mode=0o600)
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _assignment_evidence(run: Path, session_id: str, assignment_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    ledger = run / "assignments.jsonl"
    records = _read_jsonl(ledger, schema="agent-workflow/assignment-event/v1", max_records=MAX_SOURCE_RECORDS)
    matching = [item for item in records if item.get("session_id") == session_id and item.get("assignment_id") == assignment_id]
    completed = [item for item in matching if item.get("event") == "task_completed"]
    if not completed:
        raise OrchestratorInboxError("child assignment has no immutable task completion evidence")
    lifecycle_path = run / "events.jsonl"
    lifecycle = _read_jsonl(lifecycle_path, schema="agent-workflow/lifecycle-event/v1", max_records=MAX_SOURCE_RECORDS)
    assignment_events = [item for item in lifecycle if item.get("dimension") == "assignment"]
    if not assignment_events or assignment_events[-1].get("new") != "idle_reusable":
        raise OrchestratorInboxError("child completion lacks current idle_reusable lifecycle evidence")
    return completed[-1], assignment_events[-1]


def _child_evidence(settings: Settings, child: dict[str, Any]) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    session_id = child["session_id"]
    run = run_dir(settings, session_id)
    contract_path = run / "launch-contract.json"
    _regular_file(contract_path, label="child launch contract")
    contract_read = read_regular_file(contract_path, max_bytes=MAX_RECORD_BYTES)
    if contract_read.mode & 0o222:
        raise OrchestratorInboxError("child launch contract is writable and cannot be trusted")
    if "sha256:" + contract_read.sha256 != child["launch_contract_digest"]:
        raise OrchestratorInboxError("child launch contract changed after registration")
    contract = read_launch_contract(contract_path)
    if contract["session"]["id"] != session_id:
        raise OrchestratorInboxError("launch contract session identity does not match registered child")
    context_path = run / "agent-context.json"
    _regular_file(context_path, label="child agent context")
    try:
        context = read_contract(context_path, "agent-workflow/agent-context/v1")
    except WorkflowError as exc:
        raise OrchestratorInboxError("child agent context is not immutable evidence") from exc
    if context.get("session_id") != session_id:
        raise OrchestratorInboxError("agent context session identity does not match registered child")
    return contract, run, context


def _child_identity(settings: Settings, session_id: str) -> tuple[str, Path, dict[str, Any], dict[str, Any], str]:
    validate_id(session_id, "child session ID")
    run = run_dir(settings, session_id)
    contract_path = run / "launch-contract.json"
    _regular_file(contract_path, label="child launch contract")
    contract_read = read_regular_file(contract_path, max_bytes=MAX_RECORD_BYTES)
    contract = read_launch_contract(contract_path)
    if contract["session"]["id"] != session_id:
        raise OrchestratorInboxError("launch contract session identity does not match child session ID")
    context_path = run / "agent-context.json"
    _regular_file(context_path, label="child agent context")
    context = read_contract(context_path, "agent-workflow/agent-context/v1")
    if context.get("session_id") != session_id:
        raise OrchestratorInboxError("agent context session identity does not match child session ID")
    assignment = context.get("current_assignment")
    if not isinstance(assignment, dict):
        completed = context.get("completed_assignments")
        assignment = completed[-1] if isinstance(completed, list) and completed and isinstance(completed[-1], dict) else None
    if not isinstance(assignment, dict) or not isinstance(assignment.get("assignment_id"), str):
        raise OrchestratorInboxError("child has no launch-bound assignment identity")
    assignment_id = _uuid(assignment["assignment_id"], "assignment_id")
    launch_digest = "sha256:" + contract_read.sha256
    return assignment_id, run, contract, context, launch_digest


def register_child(settings: Settings, orchestrator_id: str, session_id: str) -> dict[str, Any]:
    registry = _read_registry(settings, orchestrator_id)
    assignment_id, run, contract, context, launch_digest = _child_identity(settings, session_id)
    source_path = run / "messages.jsonl"
    source_journal_id = _digest({"schema": "agent-workflow/source-journal/v1", "path": str(source_path.resolve(strict=False))})
    entry_identity = _digest({"schema": "agent-workflow/orchestrator-child/v1", "session_id": session_id, "assignment_id": assignment_id, "launch_contract_digest": launch_digest, "source_journal_id": source_journal_id})
    prior = next((item for item in registry["children"] if item["session_id"] == session_id), None)
    if prior is not None:
        if prior["identity_digest"] != entry_identity:
            raise OrchestratorInboxError("child session is already registered with conflicting immutable evidence")
        return {"registry": registry, "child": prior, "path": str(orchestrator_dir(settings, orchestrator_id) / REGISTRY_NAME)}
    if len(registry["children"]) >= MAX_CHILDREN:
        raise OrchestratorInboxError("orchestrator child registry is full")
    now = utc_now()
    child = {
        "schema": "agent-workflow/orchestrator-child/v1",
        "session_id": session_id,
        "assignment_id": assignment_id,
        "launch_contract_path": str(run / "launch-contract.json"),
        "launch_contract_digest": launch_digest,
        "source_journal_path": str(source_path),
        "source_journal_id": source_journal_id,
        "worktree": str(contract["worktree"]["path"]),
        "agent_name": context.get("agent_name"),
        "registered_at": now,
        "state": "active",
        "unregistered_at": None,
        "identity_digest": entry_identity,
    }
    registry["children"].append(child)
    registry["updated_at"] = now
    _write_registry(settings, registry)
    return {"registry": registry, "child": child, "path": str(orchestrator_dir(settings, orchestrator_id) / REGISTRY_NAME)}


def unregister_child(settings: Settings, orchestrator_id: str, session_id: str, *, state: str) -> dict[str, Any]:
    if state not in {"completed", "abandoned"}:
        raise OrchestratorInboxError("unregistration state must be completed or abandoned")
    registry = _read_registry(settings, orchestrator_id)
    child = next((item for item in registry["children"] if item["session_id"] == session_id), None)
    if child is None:
        raise OrchestratorInboxError("child session is not registered")
    if child["state"] not in {"active", state}:
        raise OrchestratorInboxError("child session has a conflicting terminal registration state")
    if state == "completed":
        _contract, run, context = _child_evidence(settings, child)
        if context.get("state") != "idle_reusable":
            raise OrchestratorInboxError("completed child unregister requires idle_reusable evidence")
        _assignment_evidence(run, session_id, child["assignment_id"])
    child["state"] = state
    child["unregistered_at"] = child.get("unregistered_at") or utc_now()
    registry["updated_at"] = utc_now()
    _write_registry(settings, registry)
    return {"registry": registry, "child": child, "source_evidence_retained": True}


def _source_records(path: Path) -> list[dict[str, Any]]:
    return _read_jsonl(path, schema="agent-workflow/session-message/v1", max_records=MAX_SOURCE_RECORDS)


def _verify_source(child: dict[str, Any], record: Mapping[str, Any], settings: Settings) -> tuple[dict[str, Any], Path, dict[str, Any], dict[str, Any] | None]:
    source = dict(record)
    validate_message(source)
    if source["session_id"] != child["session_id"]:
        raise OrchestratorInboxError("source record claims another registered session identity")
    if source["kind"] not in _EVENT_KINDS:
        raise OrchestratorInboxError(f"source message kind is not allowed for aggregate delivery: {source['kind']}")
    contract, run, context = _child_evidence(settings, child)
    source_path = Path(child["source_journal_path"])
    if source_path != run / "messages.jsonl":
        raise OrchestratorInboxError("registered source journal does not match child launch run")
    source_records = _source_records(source_path)
    exact = [item for item in source_records if item["message_id"] == source["message_id"]]
    if not exact or exact[0] != source:
        raise OrchestratorInboxError("source record is not the immutable bytes in the registered journal")
    if source["sequence"] != exact[0]["sequence"]:
        raise OrchestratorInboxError("source sequence is not authoritative")
    assignment_evidence = None
    if source["kind"] == "task_complete":
        if context.get("state") != "idle_reusable" or context.get("current_assignment") is not None:
            raise OrchestratorInboxError("agent_idle source lacks current idle_reusable assignment evidence")
        completed, _lifecycle = _assignment_evidence(run, child["session_id"], child["assignment_id"])
        if completed.get("summary") != source["content"]:
            raise OrchestratorInboxError("completion summary does not match assignment evidence")
        assignment_evidence = completed
    return source, run, contract, assignment_evidence


def _event_id(orchestrator_id: str, session_id: str, message_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"agent-workflow/{orchestrator_key(orchestrator_id)}/{session_id}/{message_id}"))


def _metadata(event: dict[str, Any], *, include_content: bool) -> dict[str, Any]:
    result = dict(event)
    if not include_content:
        result.pop("summary", None)
        result["content_available"] = True
    return result


def import_message(settings: Settings, orchestrator_id: str, session_id: str, source_message: Mapping[str, Any]) -> dict[str, Any]:
    registry = _read_registry(settings, orchestrator_id)
    child = next((item for item in registry["children"] if item["session_id"] == session_id), None)
    if child is None or child["state"] != "active":
        raise OrchestratorInboxError("child session is not an active registered source")
    source, _run, contract, assignment = _verify_source(child, source_message, settings)
    source_digest = message_digest(source)
    source_identity = f"{source['session_id']}:{source['message_id']}"
    event = {
        "schema": EVENT_SCHEMA,
        "schema_version": 1,
        # The final sequence is allocated while holding the inbox lock.  A
        # positive placeholder keeps schema validation strict before commit.
        "sequence": 1,
        "event_id": _event_id(orchestrator_id, source["session_id"], source["message_id"]),
        "workflow_id": registry.get("workflow_id") or contract.get("pack", {}).get("id"),
        "sender_session_id": source["session_id"],
        "recipient_id": orchestrator_id,
        "kind": _EVENT_KINDS[source["kind"]],
        "assignment_id": child["assignment_id"],
        "source_journal_id": child["source_journal_id"],
        "source_identity": source_identity,
        "source_message_id": source["message_id"],
        "source_sequence": source["sequence"],
        "state": "idle_reusable" if source["kind"] == "task_complete" else None,
        "summary": _bounded_text(source["content"], "event summary"),
        "created_at": source["timestamp"],
        "source_digest": source_digest,
    }
    _validate_event(event)
    path = orchestrator_dir(settings, orchestrator_id) / INBOX_NAME
    _regular_file(path, label="orchestrator inbox")
    flags = os.O_RDWR | os.O_APPEND | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise OrchestratorInboxError("cannot open orchestrator inbox without following links") from exc
    with os.fdopen(descriptor, "a+b") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            existing = _read_jsonl(path, schema=EVENT_SCHEMA, max_records=MAX_SOURCE_RECORDS)
            for prior in existing:
                if prior.get("source_identity") != source_identity:
                    continue
                if prior.get("source_digest") != source_digest:
                    raise OrchestratorInboxError("source ID is reused with a different digest")
                if prior.get("source_journal_id") != child["source_journal_id"]:
                    raise OrchestratorInboxError("source identity conflicts with another journal")
                if any(prior.get(key) != event.get(key) for key in event if key != "sequence"):
                    raise OrchestratorInboxError("duplicate source identity has conflicting normalized bytes")
                return {"event": prior, "duplicate": True, "content_available": True}
            event["sequence"] = len(existing) + 1
            _validate_event(event)
            encoded = json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
            if len(encoded) > MAX_RECORD_BYTES:
                raise OrchestratorInboxError("orchestrator inbox event exceeds bounded size")
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    fsync_directory(path.parent)
    return {"event": event, "duplicate": False, "content_available": True}


def import_registered(settings: Settings, orchestrator_id: str, *, session_id: str | None = None, max_per_child: int = MAX_SOURCE_RECORDS) -> dict[str, Any]:
    if max_per_child < 1 or max_per_child > MAX_SOURCE_RECORDS:
        raise OrchestratorInboxError("max_per_child is outside the bounded import limit")
    registry = _read_registry(settings, orchestrator_id)
    children = [item for item in registry["children"] if item["state"] == "active" and (session_id is None or item["session_id"] == session_id)]
    if session_id is not None and not children:
        raise OrchestratorInboxError("child session is not an active registered source")
    imported: list[dict[str, Any]] = []
    for child in children:
        records = _source_records(Path(child["source_journal_path"]))
        if len(records) > max_per_child:
            raise OrchestratorInboxError("source journal exceeds the bounded import limit")
        for source in records:
            if source["kind"] not in _EVENT_KINDS:
                continue
            result = import_message(settings, orchestrator_id, child["session_id"], source)
            imported.append(_metadata(result["event"], include_content=False) | {"duplicate": result["duplicate"]})
    return {"orchestrator_id": orchestrator_id, "imported": imported, "count": len(imported)}


def _cursor_path(directory: Path, child: Mapping[str, Any]) -> Path:
    cursor_root = _real_directory(directory / "cursors", create=True, label="orchestrator cursor root")
    key = hashlib.sha256(child["identity_digest"].encode("utf-8")).hexdigest()
    return cursor_root / f"{key}.json"


def _read_source_cursor(path: Path, child: Mapping[str, Any]) -> int:
    if not path.exists():
        return 0
    _regular_file(path, label="orchestrator source cursor")
    try:
        value = json.loads(read_regular_file(path, max_bytes=MAX_RECORD_BYTES).data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, WorkflowError) as exc:
        raise OrchestratorInboxError("orchestrator source cursor is invalid") from exc
    if not isinstance(value, dict) or value.get("schema") != "agent-workflow/orchestrator-source-cursor/v1":
        raise OrchestratorInboxError("orchestrator source cursor has an unsupported schema")
    if value.get("child_identity_digest") != child["identity_digest"] or value.get("source_journal_id") != child["source_journal_id"]:
        raise OrchestratorInboxError("orchestrator source cursor identity does not match registry")
    sequence = value.get("last_source_sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise OrchestratorInboxError("orchestrator source cursor sequence is invalid")
    return sequence


def _write_source_cursor(path: Path, child: Mapping[str, Any], sequence: int, message: Mapping[str, Any]) -> None:
    value = {
        "schema": "agent-workflow/orchestrator-source-cursor/v1",
        "schema_version": 1,
        "child_identity_digest": child["identity_digest"],
        "source_journal_id": child["source_journal_id"],
        "last_source_sequence": sequence,
        "last_source_message_id": message["message_id"],
        "updated_at": utc_now(),
    }
    atomic_write_json(path, value, mode=0o600)
    fsync_directory(path.parent)


def replay_registered(
    settings: Settings,
    orchestrator_id: str,
    *,
    batch_size: int = 100,
    max_per_child: int = 25,
) -> dict[str, Any]:
    """Fairly replay registered journals, committing inbox before cursors."""
    if batch_size < 1 or batch_size > MAX_SOURCE_RECORDS or max_per_child < 1 or max_per_child > MAX_SOURCE_RECORDS:
        raise OrchestratorInboxError("replay batch limits are outside the bounded range")
    registry = _read_registry(settings, orchestrator_id)
    children = [item for item in registry["children"] if item["state"] == "active"]
    directory = orchestrator_dir(settings, orchestrator_id)
    cursors = {child["session_id"]: _read_source_cursor(_cursor_path(directory, child), child) for child in children}
    records_by_child = {child["session_id"]: _source_records(Path(child["source_journal_path"])) for child in children}
    if any(cursors[child["session_id"]] > len(records_by_child[child["session_id"]]) for child in children):
        raise OrchestratorInboxError("orchestrator source cursor is ahead of its journal")
    imported: list[dict[str, Any]] = []
    advanced = 0
    position = 0
    processed_by_child: dict[str, int] = {child["session_id"]: 0 for child in children}
    while position < batch_size and children:
        made_progress = False
        for child in children:
            if position >= batch_size:
                break
            sid = child["session_id"]
            if processed_by_child[sid] >= max_per_child:
                continue
            sequence = cursors[sid]
            records = records_by_child[sid]
            if sequence >= len(records):
                continue
            source = records[sequence]
            if source["kind"] in _EVENT_KINDS:
                result = import_message(settings, orchestrator_id, sid, source)
                imported.append(_metadata(result["event"], include_content=False) | {"duplicate": result["duplicate"]})
            _write_source_cursor(_cursor_path(directory, child), child, source["sequence"], source)
            cursors[sid] = source["sequence"]
            position += 1
            advanced += 1
            processed_by_child[sid] += 1
            made_progress = True
        if not made_progress:
            break
    return {
        "orchestrator_id": orchestrator_id,
        "children": len(children),
        "advanced": advanced,
        "count": len(imported),
        "imported": imported,
        "remaining": sum(max(0, len(records_by_child[c["session_id"]]) - cursors[c["session_id"]]) for c in children),
    }


def read_inbox(settings: Settings, orchestrator_id: str, *, after_sequence: int = 0, limit: int = 100, event_id: str | None = None, include_content: bool = False) -> list[dict[str, Any]]:
    if not isinstance(after_sequence, int) or isinstance(after_sequence, bool) or after_sequence < 0:
        raise OrchestratorInboxError("after_sequence must be a non-negative integer")
    if limit < 1 or limit > MAX_READ_EVENTS:
        raise OrchestratorInboxError(f"limit must be between 1 and {MAX_READ_EVENTS}")
    if event_id is not None:
        _uuid(event_id, "event_id")
    path = orchestrator_dir(settings, orchestrator_id) / INBOX_NAME
    events = _read_jsonl(path, schema=EVENT_SCHEMA, max_records=MAX_SOURCE_RECORDS)
    if event_id is not None:
        return [_metadata(item, include_content=include_content) for item in events if item["event_id"] == event_id]
    return [_metadata(item, include_content=include_content) for item in events if item["sequence"] > after_sequence][:limit]


def read_child_registry(settings: Settings, orchestrator_id: str) -> dict[str, Any]:
    return _read_registry(settings, orchestrator_id)
