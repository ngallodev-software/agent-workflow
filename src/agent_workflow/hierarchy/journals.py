"""Append-only hierarchy journals and deterministic authority replay."""

from __future__ import annotations

import fcntl
import json
import os
import re
import stat
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..contracts import validate_instance
from ..errors import WorkflowError
from ..path import require_directory
from ..util import fsync_directory, utc_now, validate_id
from .contracts import validate_hierarchy_contract, validate_team_delegation_contract

JOURNAL_RECORD_SCHEMA = "agent-workflow/hierarchy-journal-record/v1"
_MAX_JOURNAL_BYTES = 32 * 1024 * 1024
_MAX_RECORD_BYTES = 128 * 1024
_RECORD_TYPES = {"lifecycle", "action", "acknowledgement", "import", "diagnostic"}
_PRINCIPAL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}$")
_STATE = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _open_locked_journal(path: Path) -> tuple[int, bool]:
    parent = require_directory(path.parent, label="hierarchy journal parent")
    parent_fd = os.open(
        parent,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    created = False
    try:
        flags = (
            os.O_RDWR
            | os.O_CREAT
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            descriptor = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
        except OSError as exc:
            raise WorkflowError(f"cannot open hierarchy journal without following links: {path}") from exc
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            os.close(descriptor)
            raise WorkflowError(f"hierarchy journal must be a regular file: {path}")
        if info.st_nlink != 1:
            os.close(descriptor)
            raise WorkflowError(f"hierarchy journal must not be hard linked: {path}")
        created = info.st_size == 0
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        return descriptor, created
    finally:
        os.close(parent_fd)


def _decode_records(data: bytes, *, path: Path, expected_journal_id: str | None) -> list[dict[str, Any]]:
    if len(data) > _MAX_JOURNAL_BYTES:
        raise WorkflowError(f"hierarchy journal exceeds size limit: {path}")
    if data and not data.endswith(b"\n"):
        raise WorkflowError(f"hierarchy journal is truncated: {path}")
    records: list[dict[str, Any]] = []
    local_message_ids: set[str] = set()
    imported_ids: set[tuple[str, str]] = set()
    observed_journal_id = expected_journal_id
    for expected_sequence, raw in enumerate(data.splitlines(), start=1):
        if not raw:
            raise WorkflowError(f"hierarchy journal contains an empty record: {path}")
        if len(raw) > _MAX_RECORD_BYTES:
            raise WorkflowError(f"hierarchy journal record exceeds size limit: {path}")
        try:
            value = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkflowError(f"invalid hierarchy journal JSON at sequence {expected_sequence}: {path}") from exc
        if not isinstance(value, dict):
            raise WorkflowError(f"hierarchy journal record must be an object: {path}")
        validate_instance(value, JOURNAL_RECORD_SCHEMA, artifact=f"{path}:{expected_sequence}")
        if value["sequence"] != expected_sequence:
            raise WorkflowError(
                f"hierarchy journal sequence mismatch in {path}: "
                f"expected {expected_sequence}, got {value['sequence']}"
            )
        if observed_journal_id is None:
            observed_journal_id = value["journal_id"]
        if value["journal_id"] != observed_journal_id:
            raise WorkflowError(
                f"hierarchy journal identity mismatch in {path}: "
                f"expected {observed_journal_id}, got {value['journal_id']}"
            )
        message_id = value["message_id"]
        if message_id in local_message_ids:
            raise WorkflowError(f"duplicate hierarchy journal message_id {message_id!r}: {path}")
        local_message_ids.add(message_id)
        source = value.get("source")
        if source is not None:
            key = (source["journal_id"], source["message_id"])
            if key in imported_ids:
                raise WorkflowError(
                    f"duplicate imported hierarchy message {key[0]}:{key[1]} in {path}"
                )
            imported_ids.add(key)
        records.append(value)
    return records


def read_journal(path: Path, *, expected_journal_id: str | None = None) -> tuple[dict[str, Any], ...]:
    """Read and strictly validate one local hierarchy journal."""
    path = Path(path)
    if expected_journal_id is not None:
        validate_id(expected_journal_id, "journal id")
    parent = require_directory(path.parent, label="hierarchy journal parent")
    parent_fd = os.open(
        parent,
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        try:
            descriptor = os.open(
                path.name,
                os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_fd,
            )
        except OSError as exc:
            raise WorkflowError(f"cannot read hierarchy journal without following links: {path}") from exc
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise WorkflowError(f"hierarchy journal must be a single-link regular file: {path}")
            data = bytearray()
            while True:
                chunk = os.read(descriptor, min(1024 * 1024, _MAX_JOURNAL_BYTES - len(data) + 1))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > _MAX_JOURNAL_BYTES:
                    raise WorkflowError(f"hierarchy journal exceeds size limit: {path}")
            after = os.fstat(descriptor)
            if (
                before.st_dev,
                before.st_ino,
                before.st_size,
                before.st_mtime_ns,
                before.st_ctime_ns,
            ) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise WorkflowError(f"hierarchy journal changed during read: {path}")
        finally:
            os.close(descriptor)
    finally:
        os.close(parent_fd)
    return tuple(_decode_records(bytes(data), path=path, expected_journal_id=expected_journal_id))


def append_journal_record(
    path: Path,
    *,
    journal_id: str,
    record_type: str,
    actor: str,
    payload: Mapping[str, Any],
    team_id: str | None = None,
    message_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    source_journal_id: str | None = None,
    source_message_id: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Append one fsynced record, or return an existing idempotent import."""
    path = Path(path)
    validate_id(journal_id, "journal id")
    if not isinstance(actor, str) or not _PRINCIPAL.fullmatch(actor):
        raise WorkflowError(f"invalid journal actor: {actor!r}")
    if record_type not in _RECORD_TYPES:
        raise WorkflowError(f"invalid hierarchy journal record type: {record_type!r}")
    if team_id is not None:
        validate_id(team_id, "team id")
    if (source_journal_id is None) != (source_message_id is None):
        raise WorkflowError("source_journal_id and source_message_id must be supplied together")
    source: dict[str, str] | None = None
    if source_journal_id is not None and source_message_id is not None:
        validate_id(source_journal_id, "source journal id")
        validate_id(source_message_id, "source message id")
        source = {"journal_id": source_journal_id, "message_id": source_message_id}
    chosen_message_id = message_id or str(uuid.uuid4())
    validate_id(chosen_message_id, "message id")
    for label, value in (("correlation id", correlation_id), ("causation id", causation_id)):
        if value is not None:
            validate_id(value, label)
    if not isinstance(payload, Mapping):
        raise WorkflowError("hierarchy journal payload must be an object")

    descriptor, created = _open_locked_journal(path)
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        data = bytearray()
        while True:
            chunk = os.read(descriptor, min(1024 * 1024, _MAX_JOURNAL_BYTES - len(data) + 1))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > _MAX_JOURNAL_BYTES:
                raise WorkflowError(f"hierarchy journal exceeds size limit: {path}")
        existing = _decode_records(bytes(data), path=path, expected_journal_id=journal_id)
        if source is not None:
            for record in existing:
                if record.get("source") == source:
                    comparable = {
                        "record_type": record_type,
                        "actor": actor,
                        "team_id": team_id,
                        "correlation_id": correlation_id,
                        "causation_id": causation_id,
                        "source": source,
                        "payload": dict(payload),
                    }
                    actual = {key: record.get(key) for key in comparable}
                    if _canonical(actual) != _canonical(comparable):
                        raise WorkflowError(
                            f"conflicting idempotent hierarchy import {source_journal_id}:{source_message_id}"
                        )
                    return record
        if any(record["message_id"] == chosen_message_id for record in existing):
            raise WorkflowError(f"duplicate hierarchy journal message_id: {chosen_message_id}")
        stable = os.fstat(descriptor)
        if (
            not stat.S_ISREG(stable.st_mode)
            or stable.st_nlink != 1
            or stable.st_size != len(data)
        ):
            raise WorkflowError(f"hierarchy journal changed before append: {path}")

        record = {
            "schema": JOURNAL_RECORD_SCHEMA,
            "journal_id": journal_id,
            "sequence": len(existing) + 1,
            "message_id": chosen_message_id,
            "timestamp": timestamp or utc_now(),
            "record_type": record_type,
            "actor": actor,
            "team_id": team_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
            "source": source,
            "payload": dict(payload),
        }
        validate_instance(record, JOURNAL_RECORD_SCHEMA, artifact=f"new hierarchy record for {path}")
        encoded = _canonical(record) + b"\n"
        if len(encoded) > _MAX_RECORD_BYTES:
            raise WorkflowError("hierarchy journal record exceeds size limit")
        if len(data) + len(encoded) > _MAX_JOURNAL_BYTES:
            raise WorkflowError("hierarchy journal exceeds size limit")
        os.lseek(descriptor, 0, os.SEEK_END)
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise WorkflowError(f"short write while appending hierarchy journal: {path}")
            offset += written
        os.fsync(descriptor)
        if created:
            fsync_directory(path.parent)
        return record
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def replay_authority_state(
    hierarchy: Mapping[str, Any],
    delegations: tuple[Mapping[str, Any], ...] | list[Mapping[str, Any]],
    journals: Mapping[str, Path],
) -> dict[str, Any]:
    """Rebuild a deterministic projection from immutable contracts and local journals."""
    validate_hierarchy_contract(hierarchy)
    declared = {item["team_id"] for item in hierarchy["teams"]}
    contracts: dict[str, Mapping[str, Any]] = {}
    for contract in delegations:
        validate_team_delegation_contract(contract, hierarchy)
        team_id = contract["team_id"]
        if team_id in contracts:
            raise WorkflowError(f"duplicate delegation during hierarchy replay: {team_id}")
        contracts[team_id] = contract
    if set(contracts) != declared:
        raise WorkflowError("hierarchy replay contract set does not match declared teams")

    state: dict[str, Any] = {
        "orchestration_id": hierarchy["orchestration_id"],
        "hierarchy_identity_sha256": hierarchy["identity_sha256"],
        "teams": {
            team_id: {
                "state": "contracted",
                "last_sequence_by_journal": {},
                "action_count": 0,
                "acknowledgement_count": 0,
                "import_count": 0,
                "diagnostic_count": 0,
            }
            for team_id in sorted(declared)
        },
        "journals": {},
    }
    for journal_id in sorted(journals):
        validate_id(journal_id, "journal id")
        records = read_journal(journals[journal_id], expected_journal_id=journal_id)
        state["journals"][journal_id] = len(records)
        for record in records:
            team_id = record.get("team_id")
            if team_id is not None and team_id not in declared:
                raise WorkflowError(
                    f"hierarchy journal {journal_id} references undeclared team {team_id!r}"
                )
            if team_id is None:
                continue
            team_state = state["teams"][team_id]
            team_state["last_sequence_by_journal"][journal_id] = record["sequence"]
            record_type = record["record_type"]
            if record_type == "lifecycle":
                next_state = record["payload"].get("state")
                if not isinstance(next_state, str) or not _STATE.fullmatch(next_state):
                    raise WorkflowError("hierarchy lifecycle record has no bounded state")
                team_state["state"] = next_state
            elif record_type == "action":
                team_state["action_count"] += 1
            elif record_type == "acknowledgement":
                team_state["acknowledgement_count"] += 1
            elif record_type == "import":
                team_state["import_count"] += 1
            elif record_type == "diagnostic":
                team_state["diagnostic_count"] += 1
    return state
