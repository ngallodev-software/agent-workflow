"""Rebuildable SQLite projection over authoritative run evidence.

The database is never execution authority.  Every row is derived from files
under the configured state root and carries source provenance.  Removing the
database and running ``agent-workflow index rebuild`` must restore the same
query surface from the JSON/JSONL and sealed-receipt evidence.
"""

from __future__ import annotations

import contextlib
import copy
import fcntl
import hashlib
import json
import os
import sqlite3
import stat
import time
from urllib.parse import quote
from pathlib import Path
from typing import Any, Iterable, Iterator

from .config import Settings, enforce_trust
from .contracts import load_schema, validate_instance
from .errors import WorkflowError
from .evidence_repair import evidence_repairs_root, list_evidence_repairs
from .eval.outcomes import classify_attempt
from .index_sources import (
    artifact_paths as _artifact_paths,
    discover_runs as _discover_runs,
    read_stable_bytes as _read_stable_bytes,
    sha256_file as _sha256_file,
    source_fingerprint as _source_fingerprint,
    unsafe_artifact_paths as _unsafe_artifact_paths,
)
from .index_queries import build_query as _build_query, build_query_report as _build_query_report
from .index_schema import (
    INDEX_APPLICATION_ID,
    INDEX_SCHEMA_VERSION,
    migrate as _migrate,
    validate_database_header as _validated_database_header,
)
from .path import require_directory
from .receipts import read_sealed_contract, verify_legacy_seal_details, verify_seal_details
from .lifecycle import lifecycle_receipts
from .state import run_dir, runs_root
from .util import utc_now, validate_id

MAX_EVENT_SUMMARY = 2048
INTEGRITY_AUTHORITY_SCHEMA = "agent-workflow/index-integrity-authority/v2"
INTEGRITY_MIGRATION_SCHEMA = "agent-workflow/index-integrity-migration/v2"
INTEGRITY_GENERATOR = "agent-workflow.index-integrity"
INTEGRITY_GENERATOR_VERSION = "2"

# Compatibility is intentionally data-driven and finite. These are the only
# historical schemas/field drift that may be preserved outside current
# evidence; arbitrary retired-looking IDs are not compatibility evidence.
RETIRED_HISTORICAL_SCHEMA_IDS = frozenset(
    {
        "agent-workflow/command-collection-set/v1",
        "agent-workflow/lifecycle-event/v1",
    }
)
LEGACY_EXECUTION_METRICS_SCHEMA_IDS = frozenset(
    {"agent-workflow/execution-metrics/retired-v1"}
)
LEGACY_EXECUTION_METRICS_FIELDS = frozenset(
    {
        "cache_write_input_tokens",
        "reasoning_output_tokens",
        "provider_billed_cost",
        "local_estimated_cost",
        "price_catalog_id",
    }
)
LEGACY_ENVELOPE_DRIFT = {
    "agent-workflow/launch-contract/v2": frozenset({"ticket_identity"}),
    "agent-workflow/command/v1": frozenset({"classification"}),
    "agent-workflow/run-provenance/v1": frozenset({"external_snapshots"}),
}



def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()






def index_root(settings: Settings) -> Path:
    enforce_trust(settings)
    runs_root(settings)
    root = settings.state_root / "index"
    if root.exists() or root.is_symlink():
        if root.is_symlink() or not root.is_dir():
            raise WorkflowError(f"index root is unsafe: {root}")
    else:
        root.mkdir(mode=0o700)
    require_directory(root, label="index root")
    return root


def database_path(settings: Settings) -> Path:
    return index_root(settings) / "agent-workflow.sqlite3"


def _lock_path(settings: Settings) -> Path:
    return index_root(settings) / "index.lock"


def integrity_authority_path(settings: Settings) -> Path:
    """Return the explicit-command-only v2 authority outside run artifacts."""
    return index_root(settings) / "integrity-authority-v2.jsonl"


def _integrity_snapshot(connection: sqlite3.Connection) -> str:
    """Digest the exact inputs available to the verified index projection."""
    inputs = []
    for row in connection.execute(
        "SELECT session_id,relative_path,file_kind,size_bytes,mtime_ns,sha256,record_count,schema_ids_json "
        "FROM source_files ORDER BY session_id,relative_path"
    ):
        inputs.append({key: row[key] for key in row.keys()})
    errors = [
        {key: row[key] for key in row.keys()}
        for row in connection.execute(
            "SELECT error_id,session_id,source_path,detected_at,category,detail "
            "FROM index_errors ORDER BY error_id"
        )
    ]
    return _sha256_bytes(_canonical_json({"source_files": inputs, "index_errors": errors}))


def integrity_input_snapshot(settings: Settings) -> str:
    """Return a deterministic snapshot digest without changing the index."""
    connection = _connect(settings, readonly=True)
    try:
        _validated_database_header(connection)
        return _integrity_snapshot(connection)
    finally:
        connection.close()


def _append_integrity_record(settings: Settings, record: dict[str, Any]) -> dict[str, Any]:
    path = integrity_authority_path(settings)
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise WorkflowError(f"integrity authority path is unsafe: {path}")
    payload = _canonical_json(record) + b"\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return record


def record_integrity_authority(
    settings: Settings,
    *,
    session_id: str,
    artifact_path: str,
    error_id: int,
    error_category: str,
    error_detail: str,
) -> dict[str, Any]:
    """Explicitly append one v2 integrity decision/incident binding."""
    if not session_id or not artifact_path or error_id < 1 or not error_category or not error_detail:
        raise WorkflowError("integrity authority records require complete error identity")
    snapshot = integrity_input_snapshot(settings)
    record = {
        "schema": INTEGRITY_AUTHORITY_SCHEMA,
        "record_id": hashlib.sha256(
            _canonical_json({"session_id": session_id, "artifact_path": artifact_path, "error_id": error_id, "snapshot": snapshot})
        ).hexdigest(),
        "recorded_at_ns": time.time_ns(),
        "session_id": session_id,
        "artifact_path": artifact_path,
        "error_id": error_id,
        "error_category": error_category,
        "error_detail_sha256": _sha256_bytes(error_detail.encode("utf-8")),
        "generator": {"identity": INTEGRITY_GENERATOR, "version": INTEGRITY_GENERATOR_VERSION},
        "verified_index_input_snapshot_sha256": snapshot,
        "authority": "v2-append-only",
    }
    validate_instance(record, INTEGRITY_AUTHORITY_SCHEMA, artifact="integrity authority record")
    with _writer_lock(settings):
        return _append_integrity_record(settings, record)


def migrate_integrity_authority(settings: Settings) -> dict[str, Any]:
    """Append a lineage record; never interprets legacy rows as authority."""
    connection = _connect(settings, readonly=True)
    try:
        rows = [
            {key: row[key] for key in row.keys()}
            for row in connection.execute(
                "SELECT error_id,session_id,source_path,detected_at,category,detail "
                "FROM index_errors ORDER BY error_id"
            )
        ]
        snapshot = _integrity_snapshot(connection)
    finally:
        connection.close()
    legacy_digest = _sha256_bytes(_canonical_json(rows))
    record = {
        "schema": INTEGRITY_MIGRATION_SCHEMA,
        "record_id": hashlib.sha256((legacy_digest + snapshot).encode("ascii")).hexdigest(),
        "recorded_at_ns": time.time_ns(),
        "supersedes_schema": "agent-workflow/index-errors/v1",
        "legacy_ledger_sha256": legacy_digest,
        "verified_index_input_snapshot_sha256": snapshot,
        "generator": {"identity": INTEGRITY_GENERATOR, "version": INTEGRITY_GENERATOR_VERSION},
        "authority": "v2-append-only",
        "legacy_trust": "none",
    }
    validate_instance(record, INTEGRITY_MIGRATION_SCHEMA, artifact="integrity migration record")
    with _writer_lock(settings):
        return _append_integrity_record(settings, record)


@contextlib.contextmanager
def _writer_lock(settings: Settings) -> Iterator[None]:
    path = _lock_path(settings)
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as exc:
        raise WorkflowError(f"cannot open index lock {path}: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"index lock must be a regular file: {path}")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _connect(settings: Settings, *, readonly: bool = False) -> sqlite3.Connection:
    path = database_path(settings)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise WorkflowError(f"SQLite index path is unsafe: {path}")
    elif readonly:
        raise WorkflowError("SQLite index does not exist; run: agent-workflow index rebuild")
    mode = "ro" if readonly else "rwc"
    uri_path = quote(str(path), safe="/")
    try:
        connection = sqlite3.connect(
            f"file:{uri_path}?mode={mode}&nofollow=1", uri=True, timeout=5.0
        )
    except sqlite3.Error as exc:
        raise WorkflowError(f"cannot open SQLite index {path}: {exc}") from exc
    if not readonly:
        try:
            os.chmod(path, 0o600)
        except OSError:
            connection.close()
            raise
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    if not readonly:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
    return connection






def initialize(settings: Settings) -> dict[str, Any]:
    with _writer_lock(settings):
        connection = _connect(settings)
        try:
            _migrate(connection)
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        finally:
            connection.close()
    return index_status(settings)










def _parse_json_object(data: bytes, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot index JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"indexed JSON artifact must be an object: {path}")
    schema = value.get("schema")
    if isinstance(schema, str) and schema.startswith("agent-workflow/"):
        try:
            validate_instance(value, schema, artifact=str(path))
        except WorkflowError as exc:
            raise WorkflowError(f"invalid {path}: {exc}") from exc
    return value


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return _parse_json_object(_read_stable_bytes(path), path)


def _raw_json(path: Path) -> dict[str, Any] | None:
    """Read only enough metadata to classify a failed historical projection."""
    if not path.is_file() or path.is_symlink():
        return None
    try:
        value = json.loads(_read_stable_bytes(path).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _historical_artifact_class(
    run_dir: Path, storage_class: str, error: Exception
) -> str | None:
    """Classify only obsolete retired schema drift as preserved evidence.

    Historical artifacts may predate fields added to otherwise familiar
    schemas, or refer to schema IDs retired by the installed release.  That
    compatibility exception is deliberately narrower than "any historical
    path error": active/current evidence, sealed evidence, dispositions,
    unsafe paths, malformed JSON, and operational/indexing failures remain
    blocking.  A completed run may still be below the active ``runs`` root;
    storage location is provenance, not proof that the evidence is current.
    """
    detail = str(error)
    if storage_class not in {"active", "archive"} or "unsafe source artifact" in detail:
        return None
    status = _raw_json(run_dir / "final-status.json") or _raw_json(run_dir / "status.json")
    if not status or not str(status.get("schema", "")).startswith("agent-workflow/"):
        return None
    if status.get("disposition") is not None:
        return None
    if status.get("status") in {
        "prepared", "launched", "running", "interruption_requested"
    }:
        return None
    receipt_path = run_dir / "final-receipt.json"
    legacy_seal_verified = False
    if receipt_path.is_file():
        # A sealed historical record is compatible only when its immutable receipt
        # still verifies every listed artifact.  Receipt omissions and digest/size
        # mismatches therefore remain blocking index errors.
        try:
            verify_seal_details(run_dir)
        except WorkflowError:
            # The only alternate authority format is the pre-collection v1
            # receipt. It still verifies every receipt-listed artifact.
            try:
                verify_legacy_seal_details(run_dir)
                legacy_seal_verified = True
            except WorkflowError:
                return None
    if legacy_seal_verified and "final receipt omits required artifacts" in detail:
        return "pre_collection_sealed_receipt"
    schema_drift = (
        "unknown contract schema:" in detail
        or "required property" in detail
        or "invalid " in detail and "artifact" in detail
    )
    if not schema_drift:
        return None
    # Validation errors identify the artifact but may omit its schema ID.
    # Never scan the run and never infer a candidate from exception text that
    # merely happens to contain a schema name.
    candidate = next(
        (path for path in _artifact_paths(run_dir) if str(path) in detail), None
    )
    if candidate is None:
        return None
    try:
        raw = _read_stable_bytes(candidate, shared_lock=candidate.suffix == ".jsonl")
        values = (
            [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
            if candidate.suffix == ".jsonl"
            else [json.loads(raw.decode("utf-8"))]
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not all(isinstance(value, dict) for value in values):
        return None

    for value in values:
        schema_id = value.get("schema")
        legacy_fields = LEGACY_ENVELOPE_DRIFT.get(schema_id)
        if legacy_fields is not None:
            if any(field in value for field in legacy_fields):
                continue
            compatibility_schema = copy.deepcopy(load_schema(schema_id))
            compatibility_schema["required"] = [
                field for field in compatibility_schema["required"] if field not in legacy_fields
            ]
            if schema_id == "agent-workflow/run-provenance/v1":
                compatibility_schema["additionalProperties"] = True
            try:
                import jsonschema
                jsonschema.Draft202012Validator(compatibility_schema).validate(value)
            except (jsonschema.exceptions.ValidationError, KeyError):
                return None
            return "legacy_envelope_fields:" + ",".join(sorted(legacy_fields))
        if schema_id in RETIRED_HISTORICAL_SCHEMA_IDS | LEGACY_EXECUTION_METRICS_SCHEMA_IDS:
            return f"retired_schema_id:{schema_id}"
        if schema_id != "agent-workflow/execution-metrics/v1":
            continue
        stages = value.get("stages")
        if not isinstance(stages, list) or not stages or not all(
            isinstance(stage, dict) for stage in stages
        ):
            return None
        compatibility_schema = copy.deepcopy(load_schema(schema_id))
        required = compatibility_schema["$defs"]["stage"]["required"]
        compatibility_schema["$defs"]["stage"]["required"] = [
            field for field in required if field not in LEGACY_EXECUTION_METRICS_FIELDS
        ]
        try:
            import jsonschema
        except ImportError:
            return None
        try:
            jsonschema.Draft202012Validator(compatibility_schema).validate(value)
        except jsonschema.exceptions.ValidationError:
            return None
        missing_by_stage = [
            {field for field in LEGACY_EXECUTION_METRICS_FIELDS if field not in stage}
            for stage in stages
        ]
        if all(missing == LEGACY_EXECUTION_METRICS_FIELDS for missing in missing_by_stage):
            return "execution_metrics_legacy_fields:" + ",".join(
                sorted(LEGACY_EXECUTION_METRICS_FIELDS)
            )
        return None
    return None


def _parse_jsonl_records(
    data: bytes, path: Path
) -> list[tuple[int, dict[str, Any], str]]:
    records: list[tuple[int, dict[str, Any], str]] = []
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise WorkflowError(f"cannot index JSONL artifact {path}: {exc}") from exc
    for source_sequence, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise WorkflowError(
                f"cannot index JSONL artifact {path}:{source_sequence}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise WorkflowError(
                f"indexed JSONL record must be an object: {path}:{source_sequence}"
            )
        schema = value.get("schema")
        if isinstance(schema, str) and schema.startswith("agent-workflow/"):
            try:
                validate_instance(value, schema, artifact=f"{path}:{source_sequence}")
            except WorkflowError as exc:
                raise WorkflowError(f"invalid {path}:{source_sequence}: {exc}") from exc
        records.append((source_sequence, value, _sha256_bytes(_canonical_json(value))))
    return records


def _jsonl_records(path: Path) -> list[tuple[int, dict[str, Any], str]]:
    return _parse_jsonl_records(_read_stable_bytes(path, shared_lock=True), path)


def _bounded_text(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value[:MAX_EVENT_SUMMARY]


def _event_fields(value: dict[str, Any]) -> tuple[Any, ...]:
    recorded_at = value.get("recorded_at") or value.get("timestamp") or value.get("created_at")
    event_kind = value.get("kind") or value.get("dimension") or value.get("type")
    category = value.get("category") or value.get("failure_category")
    state = value.get("state") or value.get("new")
    outcome = value.get("outcome") or value.get("result")
    # Free-form message/reason/detail bodies stay in authoritative evidence.
    # Only the bounded incident summary is copied into the generic query row.
    schema_id = value.get("schema") if isinstance(value.get("schema"), str) else None
    summary = value.get("summary") if schema_id == "agent-workflow/incident-event/v1" else None
    return (
        value.get("schema") if isinstance(value.get("schema"), str) else None,
        value.get("event_id") or value.get("incident_id") or value.get("message_id"),
        recorded_at if isinstance(recorded_at, str) else None,
        str(event_kind) if event_kind is not None else None,
        str(category) if category is not None else None,
        str(state) if state is not None and not isinstance(state, (dict, list)) else None,
        str(outcome) if outcome is not None and not isinstance(outcome, (dict, list)) else None,
        value.get("actor") if isinstance(value.get("actor"), str) else None,
        value.get("correlation_id") if isinstance(value.get("correlation_id"), str) else None,
        value.get("fingerprint") if isinstance(value.get("fingerprint"), str) else None,
        value.get("content_sha256") if isinstance(value.get("content_sha256"), str) else None,
        _bounded_text(summary),
    )


def _insert_health(
    connection: sqlite3.Connection,
    session_id: str,
    relative_path: str,
    sequence: int,
    value: dict[str, Any],
    record_sha256: str,
) -> None:
    runner = value.get("runner") if isinstance(value.get("runner"), dict) else {}
    executor = value.get("executor") if isinstance(value.get("executor"), dict) else {}
    host = value.get("host") if isinstance(value.get("host"), dict) else {}
    connection.execute(
        """INSERT INTO health_samples VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            session_id,
            relative_path,
            sequence,
            value.get("recorded_at"),
            _bool_int(runner.get("alive")),
            _bool_int(executor.get("alive")),
            executor.get("state"),
            executor.get("cpu_user_seconds"),
            executor.get("cpu_system_seconds"),
            executor.get("rss_bytes"),
            executor.get("peak_rss_bytes"),
            executor.get("read_bytes"),
            executor.get("write_bytes"),
            executor.get("open_fd_count"),
            executor.get("child_process_count"),
            host.get("load_1m"),
            host.get("available_memory_bytes"),
            host.get("disk_free_bytes"),
            value.get("output_bytes"),
            value.get("stderr_bytes"),
            value.get("executor_event_bytes"),
            value.get("terminal_event_bytes"),
            value.get("last_semantic_progress_at"),
            value.get("seconds_since_semantic_progress"),
            value.get("last_semantic_progress_source"),
            record_sha256,
        ),
    )


def _bool_int(value: Any) -> int | None:
    return None if value is None else int(bool(value))


def _delete_run_projection(connection: sqlite3.Connection, session_id: str) -> None:
    connection.execute("DELETE FROM runs WHERE session_id = ?", (session_id,))
    # A workflow can use a separate identity but is owned by one run directory.
    connection.execute("DELETE FROM workflows WHERE owner_run_id = ?", (session_id,))


def _index_workflow(
    connection: sqlite3.Connection,
    session_id: str,
    run_dir: Path,
    indexed_at: str,
) -> tuple[str | None, str | None]:
    snapshot = _read_json(run_dir / "workflow-snapshot.json")
    status = _read_json(run_dir / "workflow-status.json")
    workflow_run = _read_json(run_dir / "workflow-run.json")
    if snapshot is None and workflow_run is not None:
        nested = workflow_run.get("status")
        status = nested if isinstance(nested, dict) else status
    if snapshot is None and status is None:
        return None, None
    workflow_id = None
    for candidate in (snapshot, status, workflow_run):
        if isinstance(candidate, dict) and isinstance(candidate.get("workflow_id"), str):
            workflow_id = candidate["workflow_id"]
            break
    if workflow_id is None:
        raise WorkflowError(f"workflow artifacts have no workflow_id: {run_dir}")
    pack_id = snapshot.get("pack_id") if snapshot else None
    snapshot_sha = None
    if status:
        snapshot_sha = status.get("snapshot_sha256")
    if snapshot_sha is None and workflow_run:
        snapshot_sha = workflow_run.get("snapshot_sha256")
    workflow_state = status.get("workflow_state") if status else None
    event_count = status.get("event_count") if status else None
    connection.execute(
        "INSERT INTO workflows VALUES(?,?,?,?,?,?,?)",
        (workflow_id, session_id, pack_id, snapshot_sha, workflow_state, event_count, indexed_at),
    )
    configured: dict[str, dict[str, Any]] = {}
    if snapshot:
        for node in snapshot.get("nodes", []):
            if isinstance(node, dict) and isinstance(node.get("node_id"), str):
                configured[node["node_id"]] = node
                for dependency in node.get("dependencies", []):
                    connection.execute(
                        "INSERT INTO workflow_edges VALUES(?,?,?)",
                        (workflow_id, str(dependency), node["node_id"]),
                    )
    current: dict[str, dict[str, Any]] = {}
    if status:
        for node in status.get("nodes", []):
            if isinstance(node, dict) and isinstance(node.get("node_id"), str):
                current[node["node_id"]] = node
    for node_id in sorted(set(configured) | set(current)):
        configured_node = configured.get(node_id, {})
        current_node = current.get(node_id, {})
        connection.execute(
            """INSERT INTO workflow_nodes(
                workflow_id,node_id,kind,ticket_id,configured_session_id,bound_run_id,state,
                attempt,retry_of_run_id,executor,model,interactive,terminal_reason
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                workflow_id,
                node_id,
                configured_node.get("kind"),
                configured_node.get("ticket_id"),
                configured_node.get("session_id"),
                current_node.get("run_id"),
                current_node.get("state"),
                current_node.get("attempt"),
                current_node.get("retry_of_run_id"),
                configured_node.get("executor"),
                configured_node.get("model"),
                _bool_int(configured_node.get("interactive")),
                current_node.get("terminal_reason"),
            ),
        )
    return workflow_id, workflow_state


def _index_run(
    connection: sqlite3.Connection,
    session_id: str,
    storage_class: str,
    run_dir: Path,
    source_fingerprint: str,
) -> dict[str, Any]:
    indexed_at = utc_now()
    unsafe = _unsafe_artifact_paths(run_dir)
    if unsafe:
        relative = ", ".join(path.relative_to(run_dir).as_posix() for path in unsafe)
        raise WorkflowError(f"unsafe source artifact symlink(s): {relative}")
    launch = _read_json(run_dir / "launch-contract.json") or {}
    provenance = _read_json(run_dir / "run-provenance.json") or {}
    status = _read_json(run_dir / "final-status.json") or _read_json(run_dir / "status.json") or {}
    process_result = _read_json(run_dir / "process-result.json")
    metrics = _read_json(run_dir / "execution-metrics.json")
    ledger_row = _read_json(run_dir / "ledger-row.json") or {}
    score_set = _read_json(run_dir / "scores" / "score-set.json") or {}
    completion_collection = _read_json(run_dir / "collections" / "completion.json") or {}

    evidence_complete = 0
    final_receipt_sha256 = None
    if (run_dir / "final-receipt.json").is_file():
        _, final_receipt_sha256 = verify_seal_details(run_dir)
        evidence_complete = 1

    session = launch.get("session") if isinstance(launch.get("session"), dict) else {}
    command_plan = launch.get("command_plan") if isinstance(launch.get("command_plan"), dict) else {}
    worktree = launch.get("worktree") if isinstance(launch.get("worktree"), dict) else {}
    pack = launch.get("pack") if isinstance(launch.get("pack"), dict) else {}
    workflow = provenance.get("workflow") if isinstance(provenance.get("workflow"), dict) else {}

    _delete_run_projection(connection, session_id)
    connection.execute(
        """INSERT INTO runs(
            session_id,source_dir,storage_class,index_state,index_error,source_fingerprint,
            launch_schema,ticket_id,pack_id,workflow_id,workflow_node_id,retry_of_run_id,
            agent_name,agent_class,tier,executor,model,interactive,workdir,source_revision,
            branch,dirty_at_launch,created_at,started_at,finished_at,durable_status,
            disposition,failure_category,exit_code,final_receipt_sha256,evidence_complete,
            executor_result,completion_result,policy_result,acceptance_eligible,
            attempt_classification,score_verdict,evaluation_state,indexed_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            session_id,
            str(run_dir),
            storage_class,
            "current",
            None,
            source_fingerprint,
            launch.get("schema"),
            launch.get("ticket") or status.get("ticket_id"),
            pack.get("id") or status.get("pack_id"),
            workflow.get("workflow_id"),
            workflow.get("node_id"),
            session.get("retry_of") or provenance.get("retry_of_run_id"),
            session.get("agent_name") or provenance.get("agent_name"),
            session.get("agent_class") or provenance.get("agent_class"),
            session.get("tier"),
            command_plan.get("executor") or provenance.get("executor"),
            command_plan.get("model") or provenance.get("model"),
            _bool_int(command_plan.get("interactive")),
            worktree.get("path") or provenance.get("worktree") or status.get("workdir"),
            worktree.get("source_revision") or provenance.get("source_revision"),
            worktree.get("branch"),
            _bool_int(worktree.get("dirty_at_launch")),
            session.get("created_at") or status.get("created_at"),
            provenance.get("started_at"),
            provenance.get("finished_at") or status.get("updated_at"),
            status.get("status"),
            status.get("disposition"),
            status.get("failure_category"),
            provenance.get("exit_code") if provenance.get("exit_code") is not None else (process_result or {}).get("exit_code"),
            final_receipt_sha256,
            evidence_complete,
            ledger_row.get("executor_result") or status.get("executor_result"),
            ledger_row.get("completion_result") or completion_collection.get("validation_status") or status.get("completion_result"),
            ledger_row.get("policy_result") or status.get("policy_result"),
            _bool_int(ledger_row.get("acceptance_eligible") if "acceptance_eligible" in ledger_row else status.get("acceptance_eligible")),
            ledger_row.get("attempt_classification") or (classify_attempt(status, completion_result=completion_collection.get("validation_status")) if evidence_complete else None),
            score_set.get("verdict") or ledger_row.get("evaluation_result"),
            ledger_row.get("evaluation_state") or ("verified" if score_set.get("verdict") in {"pass", "fail", "invalid"} else "not_verified" if status.get("evaluation_path") else "not_planned"),
            indexed_at,
        ),
    )

    if process_result:
        source_sha = _sha256_file(run_dir / "process-result.json")
        connection.execute(
            """INSERT INTO process_results(
                session_id,returncode,exit_code,signal,timed_out,cancelled,stdout_truncated,
                stderr_truncated,stdout_bytes,stderr_bytes,duration_seconds,error_category,
                resolved_executable,executable_sha256,runner_pid,executor_pid,recorded_at,source_sha256
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id,
                process_result["returncode"],
                process_result.get("exit_code"),
                process_result.get("signal"),
                int(process_result["timed_out"]),
                int(process_result["cancelled"]),
                int(process_result["stdout_truncated"]),
                int(process_result["stderr_truncated"]),
                process_result["stdout_bytes"],
                process_result["stderr_bytes"],
                process_result["duration_seconds"],
                process_result["error_category"],
                process_result.get("resolved_executable"),
                process_result.get("executable_sha256"),
                process_result["runner_pid"],
                process_result.get("executor_pid"),
                process_result["recorded_at"],
                source_sha,
            ),
        )

    if metrics:
        source_sha = _sha256_file(run_dir / "execution-metrics.json")
        for stage in metrics.get("stages", []):
            if not isinstance(stage, dict):
                continue
            connection.execute(
                """INSERT INTO execution_metrics(
                    session_id,stage,input_tokens,cached_input_tokens,output_tokens,
                    provider_total_tokens,reasoning_output_tokens,provider_billed_cost,
                    local_estimated_cost,currency,elapsed_seconds,first_output_latency_seconds,
                    retry_count,steer_count,steer_acknowledged_count,steer_pending_count,source_sha256
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    session_id,
                    stage.get("stage"),
                    stage.get("input_tokens"),
                    stage.get("cached_input_tokens"),
                    stage.get("output_tokens"),
                    stage.get("provider_total_tokens"),
                    stage.get("reasoning_output_tokens"),
                    stage.get("provider_billed_cost"),
                    stage.get("local_estimated_cost"),
                    stage.get("currency"),
                    stage.get("elapsed_seconds"),
                    stage.get("first_output_latency_seconds"),
                    stage.get("retry_count", 0),
                    stage.get("steer_count", 0),
                    stage.get("steer_acknowledged_count", 0),
                    stage.get("steer_pending_count", 0),
                    source_sha,
                ),
            )

    schema_ids_by_file: dict[str, set[str]] = {}
    record_counts: dict[str, int] = {}
    for path in _artifact_paths(run_dir):
        relative = path.relative_to(run_dir).as_posix()
        info = path.stat()
        raw = _read_stable_bytes(path, shared_lock=path.suffix.lower() == ".jsonl")
        file_sha = _sha256_bytes(raw)
        schemas: set[str] = set()
        record_count: int | None = None
        if path.suffix.lower() == ".json":
            value = _parse_json_object(raw, path)
            if value and isinstance(value.get("schema"), str):
                schemas.add(value["schema"])
            record_count = 1
        elif path.suffix.lower() == ".jsonl":
            records = _parse_jsonl_records(raw, path)
            record_count = len(records)
            for sequence, value, record_sha in records:
                schema = value.get("schema") if isinstance(value.get("schema"), str) else None
                if schema:
                    schemas.add(schema)
                fields = _event_fields(value)
                connection.execute(
                    """INSERT INTO events(
                        session_id,relative_path,source_sequence,schema_id,event_id,recorded_at,
                        event_kind,category,state,outcome,actor,correlation_id,fingerprint,
                        content_sha256,summary,record_sha256
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (session_id, relative, sequence, *fields, record_sha),
                )
                if schema == "agent-workflow/run-health-sample/v1":
                    _insert_health(connection, session_id, relative, sequence, value, record_sha)
                elif schema == "agent-workflow/permission-event/v1":
                    connection.execute(
                        """INSERT INTO permission_events(
                            session_id,relative_path,source_sequence,event_id,recorded_at,principal,operation,
                            resource_class,target,requested_access,state,source,policy_rule_id,
                            evidence_sha256,remediation_class,record_sha256
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            session_id, relative, sequence, value["event_id"], value["recorded_at"],
                            value.get("principal"), value["operation"], value["resource_class"],
                            value.get("target"), value.get("requested_access"), value["state"],
                            value["source"], value.get("policy_rule_id"), value["evidence_sha256"],
                            value["remediation_class"], record_sha,
                        ),
                    )
                elif schema == "agent-workflow/incident-event/v1":
                    connection.execute(
                        """INSERT INTO incident_events(
                            session_id,relative_path,source_sequence,incident_id,recorded_at,category,severity,
                            summary,fingerprint,state,record_sha256
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            session_id, relative, sequence, value["incident_id"], value["recorded_at"],
                            value["category"], value["severity"], value["summary"],
                            value["fingerprint"], value["state"], record_sha,
                        ),
                    )
                elif schema == "agent-workflow/remediation-event/v1":
                    connection.execute(
                        """INSERT INTO remediation_events(
                            session_id,relative_path,source_sequence,event_id,incident_id,recorded_at,rule_id,
                            action,outcome,reason_sha256,record_sha256
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            session_id, relative, sequence, value["event_id"], value.get("incident_id"),
                            value["recorded_at"], value["rule_id"], value["action"],
                            value["outcome"], _sha256_bytes(str(value.get("reason", "")).encode("utf-8")) if value.get("reason") else None, record_sha,
                        ),
                    )
        schema_ids_by_file[relative] = schemas
        if record_count is not None:
            record_counts[relative] = record_count
        connection.execute(
            "INSERT INTO source_files VALUES(?,?,?,?,?,?,?,?,?)",
            (
                session_id,
                relative,
                "jsonl" if path.suffix.lower() == ".jsonl" else ("json" if path.suffix.lower() == ".json" else "metadata"),
                info.st_size,
                info.st_mtime_ns,
                file_sha,
                record_count,
                json.dumps(sorted(schemas), separators=(",", ":")),
                indexed_at,
            ),
        )

    workflow_id, workflow_state = _index_workflow(connection, session_id, run_dir, indexed_at)
    if workflow_id is not None:
        connection.execute(
            "UPDATE runs SET workflow_id = COALESCE(workflow_id, ?) WHERE session_id = ?",
            (workflow_id, session_id),
        )
    return {
        "session_id": session_id,
        "storage_class": storage_class,
        "source_dir": str(run_dir),
        "file_count": len(schema_ids_by_file),
        "event_count": sum(record_counts.values()),
        "workflow_id": workflow_id,
        "workflow_state": workflow_state,
        "evidence_complete": bool(evidence_complete),
    }


def _record_index_error(
    connection: sqlite3.Connection,
    *,
    session_id: str,
    storage_class: str,
    run_dir: Path,
    source_fingerprint: str,
    error: Exception,
) -> str:
    indexed_at = utc_now()
    _delete_run_projection(connection, session_id)
    detail = str(error)[:4096]
    connection.execute(
        """INSERT INTO runs(
            session_id,source_dir,storage_class,index_state,index_error,source_fingerprint,
            evidence_complete,indexed_at
        ) VALUES(?,?,?,?,?,?,?,?)""",
        (session_id, str(run_dir), storage_class, "error", detail, source_fingerprint, 0, indexed_at),
    )
    historical_class = _historical_artifact_class(run_dir, storage_class, error)
    category = (
        "historical_artifact"
        if historical_class is not None
        else ("unsafe_source" if "unsafe source artifact" in detail else "run_index_failed")
    )
    if historical_class is not None:
        detail = f"{historical_class}: preserved and excluded from current evidence; {detail}"
        connection.execute(
            "UPDATE runs SET index_error = ? WHERE session_id = ?", (detail, session_id)
        )
    connection.execute(
        "INSERT INTO index_errors(session_id,source_path,detected_at,category,detail) VALUES(?,?,?,?,?)",
        (session_id, str(run_dir), indexed_at, category, detail),
    )
    return category



def _sync_evidence_repairs(
    connection: sqlite3.Connection,
    settings: Settings,
    *,
    source_session_id: str | None,
) -> list[dict[str, Any]]:
    if source_session_id is None:
        connection.execute("DELETE FROM evidence_repairs")
    else:
        connection.execute(
            "DELETE FROM evidence_repairs WHERE source_session_id = ?",
            (source_session_id,),
        )
    indexed: list[dict[str, Any]] = []
    for row in list_evidence_repairs(settings, source_session_id=source_session_id):
        if row.get("validation_result") != "valid":
            continue
        repair_root = Path(str(row["repair_dir"]))
        record = _read_json(repair_root / "evidence-repair.json") or {}
        receipt_sha256 = _sha256_file(repair_root / "repair-receipt.json")
        adapter = row.get("adapter") if isinstance(row.get("adapter"), dict) else {}
        connection.execute(
            """INSERT OR REPLACE INTO evidence_repairs(
                repair_id,source_session_id,source_final_receipt_sha256,
                source_artifact_path,source_artifact_sha256,adapter_id,adapter_version,
                adapter_sha256,canonical_sha256,validation_result,source_mutation_verified,
                repair_receipt_sha256,repair_dir,created_at,actor,indexed_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["repair_id"], row["source_session_id"],
                row["source_final_receipt_sha256"], row["source_artifact_path"],
                row["source_artifact_sha256"], adapter.get("id"),
                adapter.get("version"), adapter.get("sha256"),
                row["canonical_sha256"], row["validation_result"],
                int(bool(row.get("source_mutation_verified"))), receipt_sha256,
                str(repair_root), record.get("created_at"), record.get("actor"), utc_now(),
            ),
        )
        indexed.append({
            "repair_id": row["repair_id"],
            "source_session_id": row["source_session_id"],
            "validation_result": row["validation_result"],
        })
    return indexed

def _sync_locked(
    settings: Settings,
    *,
    session_id: str | None,
    include_archived: bool,
    force: bool,
) -> dict[str, Any]:
    connection = _connect(settings)
    indexed: list[dict[str, Any]] = []
    skipped: list[str] = []
    errors: list[dict[str, str]] = []
    quarantined: list[dict[str, str]] = []
    pruned: list[str] = []
    try:
        _migrate(connection)
        discovered = _discover_runs(
            settings, include_archived=include_archived, session_id=session_id
        )
        discovered_ids = {item[0] for item in discovered}
        for current_session_id, storage_class, run_dir in discovered:
            fingerprint = _source_fingerprint(run_dir)
            current = connection.execute(
                "SELECT source_fingerprint, source_dir, storage_class, index_state FROM runs WHERE session_id = ?",
                (current_session_id,),
            ).fetchone()
            current_category = connection.execute(
                "SELECT category FROM index_errors WHERE session_id = ? ORDER BY detected_at DESC LIMIT 1",
                (current_session_id,),
            ).fetchone()
            if (
                not force
                and current is not None
                and current["source_fingerprint"] == fingerprint
                and current["source_dir"] == str(run_dir)
                and current["storage_class"] == storage_class
                and current["index_state"] == "current"
            ):
                skipped.append(current_session_id)
                continue
            if (
                not force
                and current is not None
                and current["source_fingerprint"] == fingerprint
                and current["source_dir"] == str(run_dir)
                and current["storage_class"] == storage_class
                and current["index_state"] == "error"
                and current_category is not None
                and current_category["category"] == "historical_artifact"
            ):
                quarantined.append(
                    {"session_id": current_session_id, "classification": "historical_artifact"}
                )
                continue
            try:
                with connection:
                    indexed.append(
                        _index_run(
                            connection,
                            current_session_id,
                            storage_class,
                            run_dir,
                            fingerprint,
                        )
                    )
            except Exception as exc:  # preserve other healthy projections
                with connection:
                    category = _record_index_error(
                        connection,
                        session_id=current_session_id,
                        storage_class=storage_class,
                        run_dir=run_dir,
                        source_fingerprint=fingerprint,
                        error=exc,
                    )
                if category == "historical_artifact":
                    quarantined.append(
                        {"session_id": current_session_id, "classification": category}
                    )
                else:
                    errors.append({"session_id": current_session_id, "error": str(exc)})
        if session_id is None:
            existing = {
                str(row[0])
                for row in connection.execute("SELECT session_id FROM runs").fetchall()
            }
            for stale in sorted(existing - discovered_ids):
                with connection:
                    _delete_run_projection(connection, stale)
                pruned.append(stale)
        with connection:
            _sync_evidence_repairs(
                connection,
                settings,
                source_session_id=session_id,
            )
            connection.execute(
                "INSERT OR REPLACE INTO index_metadata(key,value) VALUES('last_sync_at',?)",
                (utc_now(),),
            )
            connection.execute(
                "INSERT OR REPLACE INTO index_metadata(key,value) VALUES('last_sync_scope',?)",
                ("active+archive" if include_archived else "active",),
            )
    finally:
        connection.close()
    report = {
        "schema": "agent-workflow/index-sync-report/v1",
        "database": str(database_path(settings)),
        "authority": "json-jsonl-sealed-receipts",
        "indexed": indexed,
        "indexed_count": len(indexed),
        "skipped": skipped,
        "skipped_count": len(skipped),
        "pruned": pruned,
        "error_count": len(errors),
        "errors": errors,
        "quarantined": quarantined,
        "quarantined_count": len(quarantined),
    }
    validate_instance(report, report["schema"], artifact="SQLite index sync report")
    return report


def sync_index(
    settings: Settings,
    *,
    session_id: str | None = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    with _writer_lock(settings):
        return _sync_locked(
            settings,
            session_id=session_id,
            include_archived=include_archived,
            force=False,
        )


def rebuild_index(
    settings: Settings,
    *,
    session_id: str | None = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    with _writer_lock(settings):
        if session_id is None:
            path = database_path(settings)
            for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
                if candidate.exists() or candidate.is_symlink():
                    if candidate.is_symlink() or not candidate.is_file():
                        raise WorkflowError(f"unsafe SQLite index path: {candidate}")
                    candidate.unlink()
        return _sync_locked(
            settings,
            session_id=session_id,
            include_archived=include_archived,
            force=True,
        )


def index_status(settings: Settings) -> dict[str, Any]:
    path = database_path(settings)
    discovered = _discover_runs(settings, include_archived=True, session_id=None)
    source_run_count = len(discovered)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise WorkflowError(f"SQLite index path is unsafe: {path}")
    else:
        report = {
            "schema": "agent-workflow/index-status/v1",
            "database": str(path),
            "exists": False,
            "authority": "json-jsonl-sealed-receipts",
            "application_id": None,
            "schema_version": None,
            "journal_mode": None,
            "source_run_count": source_run_count,
            "run_count": 0,
            "current_run_count": 0,
            "stale_run_count": source_run_count,
            "freshness": "missing",
            "error_count": 0,
            "last_sync_at": None,
            "last_sync_scope": None,
            "size_bytes": 0,
        }
        validate_instance(report, report["schema"], artifact="SQLite index status")
        return report
    connection = _connect(settings, readonly=True)
    try:
        application_id, version = _validated_database_header(connection)
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        rows = {
            str(row["session_id"]): row
            for row in connection.execute(
                "SELECT session_id,source_dir,storage_class,index_state,source_fingerprint FROM runs"
            )
        }
        historical_ids = {
            str(row[0])
            for row in connection.execute(
                "SELECT r.session_id FROM runs r JOIN index_errors e ON e.session_id=r.session_id "
                "WHERE r.index_state='error' AND e.category='historical_artifact' "
                "AND e.detected_at=(SELECT MAX(e2.detected_at) FROM index_errors e2 WHERE e2.session_id=r.session_id)"
            )
        }
        error_count = sum(
            1
            for row in rows.values()
            if row["index_state"] == "error" and row["session_id"] not in historical_ids
        )
        metadata = {
            str(row[0]): str(row[1])
            for row in connection.execute("SELECT key,value FROM index_metadata")
        }
        size = path.stat().st_size
    finally:
        connection.close()

    current_run_count = 0
    stale_run_count = 0
    for session_id, storage_class, run_dir in discovered:
        row = rows.get(session_id)
        if session_id in historical_ids:
            continue
        if row is None:
            stale_run_count += 1
            continue
        try:
            fingerprint = _source_fingerprint(run_dir)
        except Exception:
            stale_run_count += 1
            continue
        if (
            row["index_state"] == "current"
            and row["source_dir"] == str(run_dir)
            and row["storage_class"] == storage_class
            and row["source_fingerprint"] == fingerprint
        ):
            current_run_count += 1
        else:
            stale_run_count += 1
    # Rows with no current source are also stale until a full-scope sync prunes them.
    stale_run_count += len(set(rows) - {item[0] for item in discovered})
    if error_count:
        freshness = "incomplete"
    elif stale_run_count:
        freshness = "stale"
    else:
        freshness = "current"
    report = {
        "schema": "agent-workflow/index-status/v1",
        "database": str(path),
        "exists": True,
        "authority": metadata.get("authority", "json-jsonl-sealed-receipts"),
        "application_id": application_id,
        "schema_version": version,
        "journal_mode": journal_mode,
        "source_run_count": source_run_count,
        "run_count": len(rows),
        "current_run_count": current_run_count,
        "stale_run_count": stale_run_count,
        "freshness": freshness,
        "error_count": error_count,
        "historical_run_count": len(historical_ids),
        "last_sync_at": metadata.get("last_sync_at"),
        "last_sync_scope": metadata.get("last_sync_scope"),
        "size_bytes": size,
    }
    validate_instance(report, report["schema"], artifact="SQLite index status")
    return report


def _review_verification(settings: Settings, connection: sqlite3.Connection, session_id: str) -> dict[str, Any]:
    """Verify one reviewed run without changing the global index verdict."""
    result: dict[str, Any] = {
        "review_scope": session_id,
        "review_valid": False,
        "review_errors": [],
        "review_evidence": None,
    }
    try:
        row = connection.execute(
            "SELECT source_dir FROM runs WHERE session_id=?", (session_id,)
        ).fetchone()
        if row is None:
            raise WorkflowError("review target is not indexed")
        indexed = Path(str(row["source_dir"]))
        allowed = (run_dir(settings, session_id), settings.state_root / "archive" / session_id)
        target = next((candidate for candidate in allowed if candidate == indexed), None)
        if target is None or target.is_symlink() or not target.is_dir():
            raise WorkflowError("review target is outside trusted active/archive evidence")
        final_receipt, final_digest = verify_seal_details(target)
        if final_receipt.get("session_id") != session_id:
            raise WorkflowError("review final receipt belongs to another run")
        final_status, final_status_digest = read_sealed_contract(
            target, final_receipt, "final-status.json", "agent-workflow/session-status/v2"
        )
        if final_status.get("session_id") != session_id or final_status.get("status") != "completed":
            raise WorkflowError("review target is not a completed run")
        completion, completion_digest = read_sealed_contract(
            target, final_receipt, "completion.json", "agent-workflow/completion/v1"
        )
        collection, collection_digest = read_sealed_contract(
            target, final_receipt, "collections/completion.json", "agent-workflow/completion-collection/v1"
        )
        if completion.get("result") != "completed" or completion.get("unresolved"):
            raise WorkflowError("review completion is not a successful direct gate")
        disposition = completion.get("review_disposition")
        if disposition is not None and disposition != "approved":
            raise WorkflowError(
                f"review completion disposition is not approved: {disposition}"
            )
        if any(item.get("result") != "pass" for item in completion.get("criteria", [])):
            raise WorkflowError("review completion contains a failed direct gate")
        if any(item.get("exit_code") != 0 for item in completion.get("commands", [])):
            raise WorkflowError("review completion contains a failed command gate")
        if collection.get("validation_status") != "valid":
            raise WorkflowError("review completion collection is not valid")
        if final_status.get("policy_result") == "failed":
            raise WorkflowError("review run failed execution policy")
        chain = lifecycle_receipts(target, expected_final_receipt_sha256=final_digest)
        if not chain or chain[-1]["receipt"].get("action") != "reviewed":
            raise WorkflowError("review target has no current reviewed lifecycle gate")
        reviewed = chain[-1]
        result["review_valid"] = True
        result["review_evidence"] = {
            "source_dir": str(target),
            "final_receipt_sha256": final_digest,
            "final_status_sha256": final_status_digest,
            "completion_sha256": completion_digest,
            "completion_collection_sha256": collection_digest,
            "review_receipt_sha256": reviewed["sha256"],
            "review_receipt_path": str(reviewed["path"]),
        }
    except (OSError, WorkflowError, KeyError, TypeError, ValueError) as exc:
        result["review_errors"] = [str(exc)]
    return result


def verify_index(
    settings: Settings, *, full: bool = False, review_session_id: str | None = None
) -> dict[str, Any]:
    connection = _connect(settings, readonly=True)
    mismatches: list[dict[str, Any]] = []
    review_result: dict[str, Any] | None = None
    try:
        _, version = _validated_database_header(connection)
        integrity = [str(row[0]) for row in connection.execute("PRAGMA integrity_check")]
        foreign_keys = [dict(row) for row in connection.execute("PRAGMA foreign_key_check")]
        if full:
            for row in connection.execute(
                "SELECT r.source_dir, f.session_id, f.relative_path, f.sha256, f.size_bytes "
                "FROM source_files f JOIN runs r ON r.session_id=f.session_id ORDER BY f.session_id,f.relative_path"
            ):
                path = Path(str(row["source_dir"])) / str(row["relative_path"])
                if path.is_symlink() or not path.is_file():
                    mismatches.append(
                        {"session_id": row["session_id"], "path": str(path), "reason": "missing_or_unsafe"}
                    )
                    continue
                info = path.stat()
                if info.st_size != row["size_bytes"] or _sha256_file(path) != row["sha256"]:
                    mismatches.append(
                        {"session_id": row["session_id"], "path": str(path), "reason": "content_changed"}
                    )
        for row in connection.execute(
            "SELECT r.session_id,r.source_dir,r.index_error,e.category "
            "FROM runs r LEFT JOIN index_errors e ON e.session_id=r.session_id "
            "AND e.detected_at=(SELECT MAX(e2.detected_at) FROM index_errors e2 WHERE e2.session_id=r.session_id) "
            "WHERE r.index_state != 'current' ORDER BY r.session_id"
        ):
            mismatches.append(
                {
                    "session_id": row["session_id"],
                    "path": row["source_dir"],
                    "reason": (
                        "historical_artifact"
                        if row["category"] == "historical_artifact"
                        else ("unsafe_symlink" if "unsafe source artifact" in (row["index_error"] or "") else "index_error")
                    ),
                    "classification": "quarantined" if row["category"] == "historical_artifact" else "blocking",
                    "outcome": "preserved_excluded" if row["category"] == "historical_artifact" else "verification_failed",
                    "detail": row["index_error"],
                }
            )
        if review_session_id is not None:
            review_result = _review_verification(settings, connection, review_session_id)
    finally:
        connection.close()
    blocking_mismatches = [
        item for item in mismatches if item.get("classification") != "quarantined"
    ]
    valid = integrity == ["ok"] and not foreign_keys and version == INDEX_SCHEMA_VERSION and not blocking_mismatches
    report = {
        "schema": "agent-workflow/index-verification/v1",
        "database": str(database_path(settings)),
        "valid": valid,
        "schema_version": version,
        "expected_schema_version": INDEX_SCHEMA_VERSION,
        "integrity_check": integrity,
        "foreign_key_errors": foreign_keys,
        "source_verification": "full" if full else "not-requested",
        "source_mismatches": mismatches,
        "historical_artifacts": [
            item for item in mismatches if item.get("classification") == "quarantined"
        ],
    }
    if review_result is not None:
        report.update(review_result)
    else:
        report.update({"review_scope": None, "review_valid": None, "review_errors": [], "review_evidence": None})
    validate_instance(report, report["schema"], artifact="SQLite index verification")
    return report




def query_index_report(
    settings: Settings,
    kind: str,
    **filters: Any,
) -> dict[str, Any]:
    """Return query rows with the projection freshness required to interpret them."""
    status = index_status(settings)
    if not status["exists"]:
        raise WorkflowError("SQLite index does not exist; run: agent-workflow index rebuild")
    rows = query_index(settings, kind, **filters)
    return _build_query_report(status, kind, rows)


def query_index(
    settings: Settings,
    kind: str,
    *,
    session_id: str | None = None,
    state: str | None = None,
    category: str | None = None,
    executor: str | None = None,
    model: str | None = None,
    pack_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    sql, parameters = _build_query(
        kind,
        session_id=session_id,
        state=state,
        category=category,
        executor=executor,
        model=model,
        pack_id=pack_id,
        limit=limit,
    )
    connection = _connect(settings, readonly=True)
    try:
        _validated_database_header(connection)
        return [dict(row) for row in connection.execute(sql, parameters).fetchall()]
    finally:
        connection.close()
