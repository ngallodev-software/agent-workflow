"""Rebuildable SQLite projection over authoritative run evidence.

The database is never execution authority.  Every row is derived from files
under the configured state root and carries source provenance.  Removing the
database and running ``agent-workflow index rebuild`` must restore the same
query surface from the JSON/JSONL and sealed-receipt evidence.
"""

from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import sqlite3
import stat
from urllib.parse import quote
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from .config import Settings, enforce_trust
from .contracts import validate_instance
from .errors import WorkflowError
from .path import require_directory
from .receipts import verify_seal_details
from .state import runs_root
from .util import utc_now, validate_id

INDEX_SCHEMA_VERSION = 1
INDEX_APPLICATION_ID = 0x41574631  # "AWF1"
MAX_INDEXED_FILE_BYTES = 64 * 1024 * 1024
MAX_EVENT_SUMMARY = 2048

JSON_ARTIFACT_SUFFIXES = {".json", ".jsonl"}
TEXT_METADATA_SUFFIXES: set[str] = set()
IGNORED_FILENAMES = {"workflow.lock", "supervisor.lock", "index.lock"}

MIGRATION_1 = r"""
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS index_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    session_id TEXT PRIMARY KEY,
    source_dir TEXT NOT NULL,
    storage_class TEXT NOT NULL CHECK (storage_class IN ('active','archive')),
    index_state TEXT NOT NULL CHECK (index_state IN ('current','error')),
    index_error TEXT,
    source_fingerprint TEXT NOT NULL,
    launch_schema TEXT,
    ticket_id TEXT,
    pack_id TEXT,
    workflow_id TEXT,
    workflow_node_id TEXT,
    retry_of_run_id TEXT,
    agent_name TEXT,
    agent_class TEXT,
    tier TEXT,
    executor TEXT,
    model TEXT,
    interactive INTEGER,
    workdir TEXT,
    source_revision TEXT,
    branch TEXT,
    dirty_at_launch INTEGER,
    created_at TEXT,
    started_at TEXT,
    finished_at TEXT,
    durable_status TEXT,
    disposition TEXT,
    failure_category TEXT,
    exit_code INTEGER,
    final_receipt_sha256 TEXT,
    evidence_complete INTEGER NOT NULL DEFAULT 0,
    indexed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_status_idx ON runs(durable_status, disposition);
CREATE INDEX IF NOT EXISTS runs_pack_ticket_idx ON runs(pack_id, ticket_id);
CREATE INDEX IF NOT EXISTS runs_executor_model_idx ON runs(executor, model);
CREATE INDEX IF NOT EXISTS runs_workflow_idx ON runs(workflow_id, workflow_node_id);
CREATE INDEX IF NOT EXISTS runs_started_idx ON runs(started_at);

CREATE TABLE IF NOT EXISTS source_files (
    session_id TEXT NOT NULL REFERENCES runs(session_id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    file_kind TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    record_count INTEGER,
    schema_ids_json TEXT NOT NULL DEFAULT '[]',
    indexed_at TEXT NOT NULL,
    PRIMARY KEY (session_id, relative_path)
);
CREATE INDEX IF NOT EXISTS source_files_sha_idx ON source_files(sha256);

CREATE TABLE IF NOT EXISTS events (
    session_id TEXT NOT NULL REFERENCES runs(session_id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    source_sequence INTEGER NOT NULL,
    schema_id TEXT,
    event_id TEXT,
    recorded_at TEXT,
    event_kind TEXT,
    category TEXT,
    state TEXT,
    outcome TEXT,
    actor TEXT,
    correlation_id TEXT,
    fingerprint TEXT,
    content_sha256 TEXT,
    summary TEXT,
    record_sha256 TEXT NOT NULL,
    PRIMARY KEY (session_id, relative_path, source_sequence)
);
CREATE INDEX IF NOT EXISTS events_schema_idx ON events(schema_id, recorded_at);
CREATE INDEX IF NOT EXISTS events_category_idx ON events(category, state, recorded_at);
CREATE INDEX IF NOT EXISTS events_event_id_idx ON events(event_id);
CREATE INDEX IF NOT EXISTS events_correlation_idx ON events(correlation_id);

CREATE TABLE IF NOT EXISTS health_samples (
    session_id TEXT NOT NULL REFERENCES runs(session_id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    source_sequence INTEGER NOT NULL,
    recorded_at TEXT NOT NULL,
    runner_alive INTEGER,
    executor_alive INTEGER,
    executor_state TEXT,
    cpu_user_seconds REAL,
    cpu_system_seconds REAL,
    rss_bytes INTEGER,
    peak_rss_bytes INTEGER,
    read_bytes INTEGER,
    write_bytes INTEGER,
    open_fd_count INTEGER,
    child_process_count INTEGER,
    host_load_1m REAL,
    host_available_memory_bytes INTEGER,
    disk_free_bytes INTEGER,
    output_bytes INTEGER,
    stderr_bytes INTEGER,
    executor_event_bytes INTEGER,
    terminal_event_bytes INTEGER,
    last_semantic_progress_at TEXT,
    seconds_since_semantic_progress REAL,
    last_semantic_progress_source TEXT,
    record_sha256 TEXT NOT NULL,
    PRIMARY KEY (session_id, relative_path, source_sequence)
);
CREATE INDEX IF NOT EXISTS health_recorded_idx ON health_samples(recorded_at);
CREATE INDEX IF NOT EXISTS health_progress_idx ON health_samples(seconds_since_semantic_progress);

CREATE TABLE IF NOT EXISTS permission_events (
    session_id TEXT NOT NULL REFERENCES runs(session_id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    source_sequence INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    principal TEXT,
    operation TEXT NOT NULL,
    resource_class TEXT NOT NULL,
    target TEXT,
    requested_access TEXT,
    state TEXT NOT NULL,
    source TEXT NOT NULL,
    policy_rule_id TEXT,
    evidence_sha256 TEXT NOT NULL,
    remediation_class TEXT NOT NULL,
    record_sha256 TEXT NOT NULL,
    PRIMARY KEY (session_id, relative_path, source_sequence)
);
CREATE INDEX IF NOT EXISTS permission_state_idx ON permission_events(state, recorded_at);
CREATE INDEX IF NOT EXISTS permission_operation_idx ON permission_events(operation, resource_class);

CREATE TABLE IF NOT EXISTS incident_events (
    session_id TEXT NOT NULL REFERENCES runs(session_id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    source_sequence INTEGER NOT NULL,
    incident_id TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    summary TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    state TEXT NOT NULL,
    record_sha256 TEXT NOT NULL,
    PRIMARY KEY (session_id, relative_path, source_sequence)
);
CREATE INDEX IF NOT EXISTS incident_category_idx ON incident_events(category, state, recorded_at);
CREATE INDEX IF NOT EXISTS incident_id_idx ON incident_events(incident_id);

CREATE TABLE IF NOT EXISTS remediation_events (
    session_id TEXT NOT NULL REFERENCES runs(session_id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    source_sequence INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    incident_id TEXT,
    recorded_at TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    reason_sha256 TEXT,
    record_sha256 TEXT NOT NULL,
    PRIMARY KEY (session_id, relative_path, source_sequence)
);
CREATE INDEX IF NOT EXISTS remediation_rule_idx ON remediation_events(rule_id, outcome, recorded_at);
CREATE INDEX IF NOT EXISTS remediation_incident_idx ON remediation_events(incident_id);

CREATE TABLE IF NOT EXISTS process_results (
    session_id TEXT PRIMARY KEY REFERENCES runs(session_id) ON DELETE CASCADE,
    returncode INTEGER NOT NULL,
    exit_code INTEGER,
    signal INTEGER,
    timed_out INTEGER NOT NULL,
    cancelled INTEGER NOT NULL,
    stdout_truncated INTEGER NOT NULL,
    stderr_truncated INTEGER NOT NULL,
    stdout_bytes INTEGER NOT NULL,
    stderr_bytes INTEGER NOT NULL,
    duration_seconds REAL NOT NULL,
    error_category TEXT NOT NULL,
    resolved_executable TEXT,
    executable_sha256 TEXT,
    runner_pid INTEGER NOT NULL,
    executor_pid INTEGER,
    recorded_at TEXT NOT NULL,
    source_sha256 TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_metrics (
    session_id TEXT NOT NULL REFERENCES runs(session_id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    input_tokens REAL,
    cached_input_tokens REAL,
    output_tokens REAL,
    provider_total_tokens REAL,
    reasoning_output_tokens REAL,
    provider_billed_cost REAL,
    local_estimated_cost REAL,
    currency TEXT,
    elapsed_seconds REAL,
    first_output_latency_seconds REAL,
    retry_count INTEGER NOT NULL,
    steer_count INTEGER NOT NULL,
    steer_acknowledged_count INTEGER NOT NULL,
    steer_pending_count INTEGER NOT NULL,
    source_sha256 TEXT NOT NULL,
    PRIMARY KEY (session_id, stage)
);
CREATE INDEX IF NOT EXISTS execution_metrics_stage_idx ON execution_metrics(stage, elapsed_seconds);

CREATE TABLE IF NOT EXISTS workflows (
    workflow_id TEXT PRIMARY KEY,
    owner_run_id TEXT NOT NULL REFERENCES runs(session_id) ON DELETE CASCADE,
    pack_id TEXT,
    snapshot_sha256 TEXT,
    workflow_state TEXT,
    event_count INTEGER,
    indexed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS workflow_nodes (
    workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    kind TEXT,
    ticket_id TEXT,
    configured_session_id TEXT,
    bound_run_id TEXT,
    state TEXT,
    attempt INTEGER,
    retry_of_run_id TEXT,
    executor TEXT,
    model TEXT,
    interactive INTEGER,
    terminal_reason TEXT,
    PRIMARY KEY (workflow_id, node_id)
);
CREATE INDEX IF NOT EXISTS workflow_nodes_state_idx ON workflow_nodes(state, workflow_id);
CREATE TABLE IF NOT EXISTS workflow_edges (
    workflow_id TEXT NOT NULL REFERENCES workflows(workflow_id) ON DELETE CASCADE,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    PRIMARY KEY (workflow_id, source_node_id, target_node_id)
);

CREATE TABLE IF NOT EXISTS index_errors (
    error_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    source_path TEXT,
    detected_at TEXT NOT NULL,
    category TEXT NOT NULL,
    detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS index_errors_session_idx ON index_errors(session_id, detected_at);

CREATE VIEW IF NOT EXISTS run_overview AS
SELECT r.*,
       (SELECT MAX(h.recorded_at) FROM health_samples h WHERE h.session_id = r.session_id) AS last_health_at,
       (SELECT MAX(e.recorded_at) FROM incident_events e WHERE e.session_id = r.session_id AND e.state = 'open') AS last_open_incident_at,
       (SELECT COUNT(*) FROM incident_events e WHERE e.session_id = r.session_id AND e.state = 'open') AS open_incident_count,
       (SELECT COUNT(*) FROM permission_events p WHERE p.session_id = r.session_id AND p.state = 'pending') AS pending_permission_count
FROM runs r;

CREATE VIEW IF NOT EXISTS incident_summary AS
SELECT category, severity, state, COUNT(*) AS event_count,
       COUNT(DISTINCT session_id) AS run_count,
       MIN(recorded_at) AS first_seen_at,
       MAX(recorded_at) AS last_seen_at
FROM incident_events
GROUP BY category, severity, state;

CREATE VIEW IF NOT EXISTS permission_summary AS
SELECT operation, resource_class, state, COUNT(*) AS event_count,
       COUNT(DISTINCT session_id) AS run_count,
       MIN(recorded_at) AS first_seen_at,
       MAX(recorded_at) AS last_seen_at
FROM permission_events
GROUP BY operation, resource_class, state;

CREATE VIEW IF NOT EXISTS performance_summary AS
SELECT r.executor, r.model, m.stage,
       COUNT(*) AS sample_count,
       AVG(m.elapsed_seconds) AS avg_elapsed_seconds,
       AVG(m.first_output_latency_seconds) AS avg_first_output_latency_seconds,
       AVG(m.input_tokens) AS avg_input_tokens,
       AVG(m.output_tokens) AS avg_output_tokens,
       SUM(CASE WHEN m.provider_billed_cost IS NOT NULL THEN 1 ELSE 0 END) AS provider_billed_sample_count,
       CASE WHEN SUM(CASE WHEN m.provider_billed_cost IS NOT NULL THEN 1 ELSE 0 END) = 0 THEN NULL
            WHEN COUNT(DISTINCT CASE WHEN m.provider_billed_cost IS NOT NULL THEN m.currency END) = 1
             AND SUM(CASE WHEN m.provider_billed_cost IS NOT NULL AND m.currency IS NULL THEN 1 ELSE 0 END) = 0
            THEN AVG(m.provider_billed_cost)
            ELSE NULL END AS avg_provider_billed_cost,
       CASE WHEN COUNT(DISTINCT CASE WHEN m.provider_billed_cost IS NOT NULL THEN m.currency END) = 1
             AND SUM(CASE WHEN m.provider_billed_cost IS NOT NULL AND m.currency IS NULL THEN 1 ELSE 0 END) = 0
            THEN MAX(CASE WHEN m.provider_billed_cost IS NOT NULL THEN m.currency END)
            ELSE NULL END AS provider_billed_currency,
       SUM(CASE WHEN m.local_estimated_cost IS NOT NULL THEN 1 ELSE 0 END) AS local_estimated_sample_count,
       CASE WHEN SUM(CASE WHEN m.local_estimated_cost IS NOT NULL THEN 1 ELSE 0 END) = 0 THEN NULL
            WHEN COUNT(DISTINCT CASE WHEN m.local_estimated_cost IS NOT NULL THEN m.currency END) = 1
             AND SUM(CASE WHEN m.local_estimated_cost IS NOT NULL AND m.currency IS NULL THEN 1 ELSE 0 END) = 0
            THEN AVG(m.local_estimated_cost)
            ELSE NULL END AS avg_local_estimated_cost,
       CASE WHEN COUNT(DISTINCT CASE WHEN m.local_estimated_cost IS NOT NULL THEN m.currency END) = 1
             AND SUM(CASE WHEN m.local_estimated_cost IS NOT NULL AND m.currency IS NULL THEN 1 ELSE 0 END) = 0
            THEN MAX(CASE WHEN m.local_estimated_cost IS NOT NULL THEN m.currency END)
            ELSE NULL END AS local_estimated_currency
FROM execution_metrics m
JOIN runs r ON r.session_id = m.session_id
GROUP BY r.executor, r.model, m.stage;
"""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_stable_bytes(path: Path, *, shared_lock: bool = False) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise WorkflowError(f"cannot open indexed artifact {path}: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowError(f"indexed artifact must be a regular file: {path}")
        if info.st_size > MAX_INDEXED_FILE_BYTES:
            raise WorkflowError(f"artifact exceeds index safety limit: {path}")
        if shared_lock:
            fcntl.flock(descriptor, fcntl.LOCK_SH)
        try:
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            if shared_lock:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(_read_stable_bytes(path, shared_lock=path.suffix.lower() == ".jsonl"))


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


def _validated_database_header(connection: sqlite3.Connection) -> tuple[int, int]:
    application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if application_id != INDEX_APPLICATION_ID:
        raise WorkflowError("refusing to read a SQLite database not owned by agent-workflow")
    if version != INDEX_SCHEMA_VERSION:
        relation = "newer" if version > INDEX_SCHEMA_VERSION else "older"
        raise WorkflowError(
            f"SQLite index schema {version} is {relation} than supported {INDEX_SCHEMA_VERSION}; "
            "run the matching agent-workflow version or rebuild with a writable current version"
        )
    return application_id, version


def _migrate(connection: sqlite3.Connection) -> None:
    application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
    if application_id not in {0, INDEX_APPLICATION_ID}:
        raise WorkflowError("refusing to open a SQLite database owned by another application")
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if application_id == 0 and version > 0:
        raise WorkflowError("refusing to claim an unowned SQLite database with an existing schema")
    if version > INDEX_SCHEMA_VERSION:
        raise WorkflowError(
            f"SQLite index schema {version} is newer than supported {INDEX_SCHEMA_VERSION}"
        )
    if version < 1:
        with connection:
            connection.execute(f"PRAGMA application_id = {INDEX_APPLICATION_ID}")
            connection.executescript(MIGRATION_1)
            connection.execute(
                "INSERT OR REPLACE INTO schema_migrations(version, applied_at, description) VALUES(1, ?, ?)",
                (utc_now(), "initial rebuildable evidence projection"),
            )
            connection.execute(f"PRAGMA user_version = {INDEX_SCHEMA_VERSION}")
            connection.execute(
                "INSERT OR REPLACE INTO index_metadata(key, value) VALUES('authority', 'json-jsonl-sealed-receipts')"
            )
            connection.execute(
                "INSERT OR REPLACE INTO index_metadata(key, value) VALUES('schema_version', ?)",
                (str(INDEX_SCHEMA_VERSION),),
            )


def initialize(settings: Settings) -> dict[str, Any]:
    with _writer_lock(settings):
        connection = _connect(settings)
        try:
            _migrate(connection)
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        finally:
            connection.close()
    return index_status(settings)


def _run_roots(settings: Settings, *, include_archived: bool) -> list[tuple[str, Path]]:
    roots = [("active", runs_root(settings))]
    if include_archived:
        archive = settings.state_root / "archive"
        if archive.exists() or archive.is_symlink():
            if archive.is_symlink() or not archive.is_dir():
                raise WorkflowError(f"archive root is unsafe: {archive}")
            roots.append(("archive", archive))
    return roots


def _discover_runs(
    settings: Settings,
    *,
    include_archived: bool,
    session_id: str | None,
) -> list[tuple[str, str, Path]]:
    if session_id is not None:
        validate_id(session_id, "session ID")
    discovered: dict[str, tuple[str, str, Path]] = {}
    for storage_class, root in _run_roots(settings, include_archived=include_archived):
        for path in sorted(root.iterdir() if root.is_dir() else []):
            if session_id is not None and path.name != session_id:
                continue
            if path.is_symlink() or not path.is_dir():
                continue
            validate_id(path.name, "session ID")
            # Active state wins if a hostile/malformed state root contains both.
            candidate = (path.name, storage_class, path)
            if path.name not in discovered or storage_class == "active":
                discovered[path.name] = candidate
    return [discovered[key] for key in sorted(discovered)]


def _artifact_paths(run_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(run_dir.rglob("*")):
        if path.is_symlink() or not path.is_file() or path.name in IGNORED_FILENAMES:
            continue
        if path.suffix.lower() in JSON_ARTIFACT_SUFFIXES | TEXT_METADATA_SUFFIXES:
            paths.append(path)
    return paths


def _source_fingerprint(run_dir: Path) -> str:
    digest = hashlib.sha256()
    for path in _artifact_paths(run_dir):
        info = path.stat()
        relative = path.relative_to(run_dir).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(info.st_size).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(info.st_mtime_ns).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(info.st_ctime_ns).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(info.st_dev).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(info.st_ino).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(stat.S_IMODE(info.st_mode)).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _parse_json_object(data: bytes, path: Path) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"cannot index JSON artifact {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"indexed JSON artifact must be an object: {path}")
    schema = value.get("schema")
    if isinstance(schema, str) and schema.startswith("agent-workflow/"):
        validate_instance(value, schema, artifact=str(path))
    return value


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return _parse_json_object(_read_stable_bytes(path), path)


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
            validate_instance(value, schema, artifact=f"{path}:{source_sequence}")
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
    launch = _read_json(run_dir / "launch-contract.json") or {}
    provenance = _read_json(run_dir / "run-provenance.json") or {}
    status = _read_json(run_dir / "final-status.json") or _read_json(run_dir / "status.json") or {}
    process_result = _read_json(run_dir / "process-result.json")
    metrics = _read_json(run_dir / "execution-metrics.json")

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
            disposition,failure_category,exit_code,final_receipt_sha256,evidence_complete,indexed_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
) -> None:
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
    connection.execute(
        "INSERT INTO index_errors(session_id,source_path,detected_at,category,detail) VALUES(?,?,?,?,?)",
        (session_id, str(run_dir), indexed_at, "run_index_failed", detail),
    )


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
                    _record_index_error(
                        connection,
                        session_id=current_session_id,
                        storage_class=storage_class,
                        run_dir=run_dir,
                        source_fingerprint=fingerprint,
                        error=exc,
                    )
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
        error_count = sum(1 for row in rows.values() if row["index_state"] == "error")
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
        "last_sync_at": metadata.get("last_sync_at"),
        "last_sync_scope": metadata.get("last_sync_scope"),
        "size_bytes": size,
    }
    validate_instance(report, report["schema"], artifact="SQLite index status")
    return report


def verify_index(settings: Settings, *, full: bool = False) -> dict[str, Any]:
    connection = _connect(settings, readonly=True)
    mismatches: list[dict[str, Any]] = []
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
    finally:
        connection.close()
    valid = integrity == ["ok"] and not foreign_keys and version == INDEX_SCHEMA_VERSION and not mismatches
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
    }
    validate_instance(report, report["schema"], artifact="SQLite index verification")
    return report


_QUERY_COLUMNS: dict[str, tuple[str, Sequence[str]]] = {
    "runs": (
        "SELECT session_id,source_dir,storage_class,ticket_id,pack_id,executor,model,durable_status,disposition,index_state,index_error,started_at,finished_at,final_receipt_sha256,evidence_complete,indexed_at,open_incident_count,pending_permission_count FROM run_overview",
        ("session_id", "source_dir", "storage_class", "ticket_id", "pack_id", "executor", "model", "durable_status", "disposition", "index_state", "index_error", "started_at", "finished_at", "final_receipt_sha256", "evidence_complete", "indexed_at", "open_incident_count", "pending_permission_count"),
    ),
    "incidents": (
        "SELECT session_id,relative_path,source_sequence,incident_id,recorded_at,category,severity,state,summary,record_sha256 FROM incident_events",
        ("session_id", "relative_path", "source_sequence", "incident_id", "recorded_at", "category", "severity", "state", "summary", "record_sha256"),
    ),
    "permissions": (
        "SELECT session_id,relative_path,source_sequence,event_id,recorded_at,operation,resource_class,state,source,remediation_class,record_sha256 FROM permission_events",
        ("session_id", "relative_path", "source_sequence", "event_id", "recorded_at", "operation", "resource_class", "state", "source", "remediation_class", "record_sha256"),
    ),
    "performance": (
        "SELECT executor,model,stage,sample_count,avg_elapsed_seconds,avg_first_output_latency_seconds,avg_input_tokens,avg_output_tokens,provider_billed_sample_count,avg_provider_billed_cost,provider_billed_currency,local_estimated_sample_count,avg_local_estimated_cost,local_estimated_currency FROM performance_summary",
        ("executor", "model", "stage", "sample_count", "avg_elapsed_seconds", "avg_first_output_latency_seconds", "avg_input_tokens", "avg_output_tokens", "provider_billed_sample_count", "avg_provider_billed_cost", "provider_billed_currency", "local_estimated_sample_count", "avg_local_estimated_cost", "local_estimated_currency"),
    ),
    "workflows": (
        "SELECT workflow_id,owner_run_id,pack_id,workflow_state,event_count,indexed_at FROM workflows",
        ("workflow_id", "owner_run_id", "pack_id", "workflow_state", "event_count", "indexed_at"),
    ),
    "workflow-nodes": (
        "SELECT workflow_id,node_id,kind,ticket_id,bound_run_id,state,attempt,executor,model,terminal_reason FROM workflow_nodes",
        ("workflow_id", "node_id", "kind", "ticket_id", "bound_run_id", "state", "attempt", "executor", "model", "terminal_reason"),
    ),
    "errors": (
        "SELECT error_id,session_id,source_path,detected_at,category,detail FROM index_errors",
        ("error_id", "session_id", "source_path", "detected_at", "category", "detail"),
    ),
}


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
    report = {
        "schema": "agent-workflow/index-query/v1",
        "database": status["database"],
        "authority": status["authority"],
        "freshness": status["freshness"],
        "current_run_count": status["current_run_count"],
        "stale_run_count": status["stale_run_count"],
        "error_count": status["error_count"],
        "kind": kind,
        "rows": rows,
    }
    validate_instance(report, report["schema"], artifact="SQLite index query")
    return report


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
    if kind not in _QUERY_COLUMNS:
        raise WorkflowError(f"unsupported index query: {kind}")
    if not 1 <= limit <= 10000:
        raise WorkflowError("index query limit must be between 1 and 10000")
    if session_id is not None:
        validate_id(session_id, "session ID")
    base, columns = _QUERY_COLUMNS[kind]
    clauses: list[str] = []
    parameters: list[Any] = []
    supported = set(columns)
    state_column = {
        "runs": "durable_status",
        "workflows": "workflow_state",
        "workflow-nodes": "state",
        "incidents": "state",
        "permissions": "state",
    }.get(kind)
    filters = [
        ("session_id", session_id),
        (state_column, state),
        ("category", category),
        ("executor", executor),
        ("model", model),
        ("pack_id", pack_id),
    ]
    for column, value in filters:
        if value is None or column is None:
            continue
        if column not in supported:
            raise WorkflowError(f"filter {column!r} is not supported for index query {kind!r}")
        clauses.append(f"{column} = ?")
        parameters.append(value)
    sql = f"SELECT * FROM ({base})"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    order_column = "recorded_at" if "recorded_at" in supported else ("started_at" if "started_at" in supported else columns[0])
    sql += f" ORDER BY {order_column} DESC LIMIT ?"
    parameters.append(limit)
    connection = _connect(settings, readonly=True)
    try:
        _validated_database_header(connection)
        return [dict(row) for row in connection.execute(sql, parameters).fetchall()]
    finally:
        connection.close()
