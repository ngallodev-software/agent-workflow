"""Append-only operator integrity authority for the rebuildable SQLite index."""

from __future__ import annotations

import sqlite3
import time
from typing import Any

from .config import Settings
from .contracts import validate_instance
from .errors import WorkflowError
from .index_db import connect, integrity_authority_path, writer_lock
from .journal import append_jsonl
from .util import canonical_json_bytes, canonical_json_sha256, sha256_bytes

INTEGRITY_AUTHORITY_SCHEMA = "agent-workflow/index-integrity-authority/v2"
INTEGRITY_GENERATOR = "agent-workflow.index-integrity"
INTEGRITY_GENERATOR_VERSION = "2"


def _integrity_snapshot(connection: sqlite3.Connection) -> str:
    inputs = []
    for row in connection.execute(
        "SELECT agent_run_id,relative_path,file_kind,size_bytes,mtime_ns,sha256,record_count,schema_ids_json "
        "FROM source_files ORDER BY agent_run_id,relative_path"
    ):
        inputs.append({key: row[key] for key in row.keys()})
    errors = [
        {key: row[key] for key in row.keys()}
        for row in connection.execute(
            "SELECT error_id,agent_run_id,source_path,detected_at,category,detail "
            "FROM index_errors ORDER BY error_id"
        )
    ]
    return sha256_bytes(canonical_json_bytes({"source_files": inputs, "index_errors": errors}))


def integrity_input_snapshot(settings: Settings) -> str:
    connection = connect(settings, readonly=True)
    try:
        return _integrity_snapshot(connection)
    finally:
        connection.close()


def _validate_integrity_record(value: object, _line_number: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError("integrity authority record must be a JSON object")
    validate_instance(value, INTEGRITY_AUTHORITY_SCHEMA, artifact="integrity authority record")
    return value


def _append_integrity_record(settings: Settings, record: dict[str, Any]) -> dict[str, Any]:
    return append_jsonl(
        integrity_authority_path(settings),
        record,
        validator=_validate_integrity_record,
    )


def record_integrity_authority(
    settings: Settings,
    *,
    agent_run_id: str,
    artifact_path: str,
    error_id: int,
    error_category: str,
    error_detail: str,
) -> dict[str, Any]:
    """Explicitly append one integrity decision/incident binding."""
    if not agent_run_id or not artifact_path or error_id < 1 or not error_category or not error_detail:
        raise WorkflowError("integrity authority records require complete error identity")
    snapshot = integrity_input_snapshot(settings)
    record = {
        "schema": INTEGRITY_AUTHORITY_SCHEMA,
        "record_id": canonical_json_sha256(
            {"agent_run_id": agent_run_id, "artifact_path": artifact_path, "error_id": error_id, "snapshot": snapshot}
        ),
        "recorded_at_ns": time.time_ns(),
        "agent_run_id": agent_run_id,
        "artifact_path": artifact_path,
        "error_id": error_id,
        "error_category": error_category,
        "error_detail_sha256": sha256_bytes(error_detail.encode("utf-8")),
        "generator": {"identity": INTEGRITY_GENERATOR, "version": INTEGRITY_GENERATOR_VERSION},
        "verified_index_input_snapshot_sha256": snapshot,
        "authority": "v2-append-only",
    }
    validate_instance(record, INTEGRITY_AUTHORITY_SCHEMA, artifact="integrity authority record")
    with writer_lock(settings):
        return _append_integrity_record(settings, record)
