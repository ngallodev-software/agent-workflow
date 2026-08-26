"""SQLite schema ownership for the rebuildable evidence index.

The index is a disposable projection. This module creates the current schema
and refuses older database layouts; callers rebuild rather than carrying
historical projection migrations in runtime code.
"""

from __future__ import annotations

import sqlite3

from .errors import WorkflowError
from .util import utc_now

INDEX_SCHEMA_VERSION = 4
INDEX_APPLICATION_ID = 0x41574631  # "AWF1"

SCHEMA_BASE = r"""
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
    agent_run_id TEXT PRIMARY KEY,
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
    retry_of_agent_run_id TEXT,
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
    agent_run_id TEXT NOT NULL REFERENCES runs(agent_run_id) ON DELETE CASCADE,
    relative_path TEXT NOT NULL,
    file_kind TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    record_count INTEGER,
    schema_ids_json TEXT NOT NULL DEFAULT '[]',
    indexed_at TEXT NOT NULL,
    PRIMARY KEY (agent_run_id, relative_path)
);
CREATE INDEX IF NOT EXISTS source_files_sha_idx ON source_files(sha256);

CREATE TABLE IF NOT EXISTS events (
    agent_run_id TEXT NOT NULL REFERENCES runs(agent_run_id) ON DELETE CASCADE,
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
    PRIMARY KEY (agent_run_id, relative_path, source_sequence)
);
CREATE INDEX IF NOT EXISTS events_schema_idx ON events(schema_id, recorded_at);
CREATE INDEX IF NOT EXISTS events_category_idx ON events(category, state, recorded_at);
CREATE INDEX IF NOT EXISTS events_event_id_idx ON events(event_id);
CREATE INDEX IF NOT EXISTS events_correlation_idx ON events(correlation_id);

CREATE TABLE IF NOT EXISTS health_samples (
    agent_run_id TEXT NOT NULL REFERENCES runs(agent_run_id) ON DELETE CASCADE,
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
    last_semantic_progress_at TEXT,
    seconds_since_semantic_progress REAL,
    last_semantic_progress_source TEXT,
    record_sha256 TEXT NOT NULL,
    PRIMARY KEY (agent_run_id, relative_path, source_sequence)
);
CREATE INDEX IF NOT EXISTS health_recorded_idx ON health_samples(recorded_at);
CREATE INDEX IF NOT EXISTS health_progress_idx ON health_samples(seconds_since_semantic_progress);

CREATE TABLE IF NOT EXISTS permission_events (
    agent_run_id TEXT NOT NULL REFERENCES runs(agent_run_id) ON DELETE CASCADE,
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
    PRIMARY KEY (agent_run_id, relative_path, source_sequence)
);
CREATE INDEX IF NOT EXISTS permission_state_idx ON permission_events(state, recorded_at);
CREATE INDEX IF NOT EXISTS permission_operation_idx ON permission_events(operation, resource_class);

CREATE TABLE IF NOT EXISTS incident_events (
    agent_run_id TEXT NOT NULL REFERENCES runs(agent_run_id) ON DELETE CASCADE,
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
    PRIMARY KEY (agent_run_id, relative_path, source_sequence)
);
CREATE INDEX IF NOT EXISTS incident_category_idx ON incident_events(category, state, recorded_at);
CREATE INDEX IF NOT EXISTS incident_id_idx ON incident_events(incident_id);

CREATE TABLE IF NOT EXISTS remediation_events (
    agent_run_id TEXT NOT NULL REFERENCES runs(agent_run_id) ON DELETE CASCADE,
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
    PRIMARY KEY (agent_run_id, relative_path, source_sequence)
);
CREATE INDEX IF NOT EXISTS remediation_rule_idx ON remediation_events(rule_id, outcome, recorded_at);
CREATE INDEX IF NOT EXISTS remediation_incident_idx ON remediation_events(incident_id);

CREATE TABLE IF NOT EXISTS process_results (
    agent_run_id TEXT PRIMARY KEY REFERENCES runs(agent_run_id) ON DELETE CASCADE,
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
    agent_run_id TEXT NOT NULL REFERENCES runs(agent_run_id) ON DELETE CASCADE,
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
    PRIMARY KEY (agent_run_id, stage)
);
CREATE INDEX IF NOT EXISTS execution_metrics_stage_idx ON execution_metrics(stage, elapsed_seconds);

CREATE TABLE IF NOT EXISTS workflows (
    workflow_id TEXT PRIMARY KEY,
    owner_run_id TEXT NOT NULL REFERENCES runs(agent_run_id) ON DELETE CASCADE,
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
    configured_agent_run_id TEXT,
    bound_agent_run_id TEXT,
    state TEXT,
    attempt INTEGER,
    retry_of_agent_run_id TEXT,
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
    agent_run_id TEXT,
    source_path TEXT,
    detected_at TEXT NOT NULL,
    category TEXT NOT NULL,
    detail TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS index_errors_agent_run_idx ON index_errors(agent_run_id, detected_at);

CREATE VIEW IF NOT EXISTS run_overview AS
SELECT r.*,
       (SELECT MAX(h.recorded_at) FROM health_samples h WHERE h.agent_run_id = r.agent_run_id) AS last_health_at,
       (SELECT MAX(e.recorded_at) FROM incident_events e WHERE e.agent_run_id = r.agent_run_id AND e.state = 'open') AS last_open_incident_at,
       (SELECT COUNT(*) FROM incident_events e WHERE e.agent_run_id = r.agent_run_id AND e.state = 'open') AS open_incident_count,
       (SELECT COUNT(*) FROM permission_events p WHERE p.agent_run_id = r.agent_run_id AND p.state = 'pending') AS pending_permission_count
FROM runs r;

CREATE VIEW IF NOT EXISTS incident_summary AS
SELECT category, severity, state, COUNT(*) AS event_count,
       COUNT(DISTINCT agent_run_id) AS run_count,
       MIN(recorded_at) AS first_seen_at,
       MAX(recorded_at) AS last_seen_at
FROM incident_events
GROUP BY category, severity, state;

CREATE VIEW IF NOT EXISTS permission_summary AS
SELECT operation, resource_class, state, COUNT(*) AS event_count,
       COUNT(DISTINCT agent_run_id) AS run_count,
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
JOIN runs r ON r.agent_run_id = m.agent_run_id
GROUP BY r.executor, r.model, m.stage;
"""

SCHEMA_OUTCOMES = r"""
ALTER TABLE runs ADD COLUMN executor_result TEXT;
ALTER TABLE runs ADD COLUMN completion_result TEXT;
ALTER TABLE runs ADD COLUMN policy_result TEXT;
ALTER TABLE runs ADD COLUMN acceptance_eligible INTEGER;
ALTER TABLE runs ADD COLUMN attempt_classification TEXT;
ALTER TABLE runs ADD COLUMN score_verdict TEXT;
ALTER TABLE runs ADD COLUMN evaluation_state TEXT;
CREATE INDEX IF NOT EXISTS runs_attempt_class_idx ON runs(attempt_classification, evaluation_state);
CREATE VIEW IF NOT EXISTS attempt_summary AS
SELECT attempt_classification, executor_result, completion_result, policy_result,
       score_verdict, evaluation_state, COUNT(*) AS run_count,
       SUM(CASE WHEN acceptance_eligible = 1 THEN 1 ELSE 0 END) AS acceptance_eligible_count
FROM runs
GROUP BY attempt_classification, executor_result, completion_result, policy_result,
         score_verdict, evaluation_state;
"""




def validate_database_header(connection: sqlite3.Connection) -> tuple[int, int]:
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


def migrate(connection: sqlite3.Connection) -> None:
    """Create the current projection schema or require a clean rebuild."""
    application_id = int(connection.execute("PRAGMA application_id").fetchone()[0])
    version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if application_id not in {0, INDEX_APPLICATION_ID}:
        raise WorkflowError("refusing to open a SQLite database owned by another application")
    if application_id == INDEX_APPLICATION_ID:
        if version != INDEX_SCHEMA_VERSION:
            raise WorkflowError(
                f"SQLite index schema {version} is not current {INDEX_SCHEMA_VERSION}; "
                "run: agent-workflow index rebuild"
            )
        return
    if version != 0:
        raise WorkflowError("refusing to claim an unowned SQLite database with an existing schema")
    with connection:
        connection.execute(f"PRAGMA application_id = {INDEX_APPLICATION_ID}")
        connection.executescript(SCHEMA_BASE)
        connection.executescript(SCHEMA_OUTCOMES)
        connection.execute(
            "INSERT OR REPLACE INTO schema_migrations(version, applied_at, description) VALUES(?, ?, ?)",
            (INDEX_SCHEMA_VERSION, utc_now(), "current rebuildable evidence projection"),
        )
        connection.execute(f"PRAGMA user_version = {INDEX_SCHEMA_VERSION}")
        connection.execute(
            "INSERT OR REPLACE INTO index_metadata(key, value) VALUES('authority', 'json-jsonl-sealed-receipts')"
        )
        connection.execute(
            "INSERT OR REPLACE INTO index_metadata(key, value) VALUES('schema_version', ?)",
            (str(INDEX_SCHEMA_VERSION),),
        )
