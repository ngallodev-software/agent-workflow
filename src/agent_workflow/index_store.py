"""Rebuildable SQLite projection over authoritative run evidence.

The database is never execution authority.  Every row is derived from files
under the configured state root and carries source provenance.  Removing the
database and running ``agent-workflow index rebuild`` must restore the same
query surface from the JSON/JSONL and sealed-receipt evidence.
"""

from __future__ import annotations

import json
import sqlite3
import stat
from pathlib import Path
from typing import Any, Iterable, Iterator

from .config import Settings
from .errors import WorkflowError
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
from .index_db import connect as _connect, database_path, writer_lock as _writer_lock
from .index_review import verify_review_projection
from .index_schema import (
    INDEX_APPLICATION_ID,
    INDEX_SCHEMA_VERSION,
    migrate as _migrate,
    validate_database_header as _validated_database_header,
)
from .state import runs_root
from .util import canonical_json_bytes, canonical_json_sha256, sha256_bytes, utc_now, validate_id

MAX_EVENT_SUMMARY = 2048
INTEGRITY_AUTHORITY_SCHEMA = "agent-workflow/index-integrity-authority/v2"
INTEGRITY_GENERATOR = "agent-workflow.index-integrity"
INTEGRITY_GENERATOR_VERSION = "2"



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
        # JSON Schema is intentionally expensive to import. Query/status-only
        # index commands never validate source artifacts, so keep the validator
        # behind the artifact parsing boundary instead of charging every index
        # CLI process for it.
        from .contracts import validate_instance

        try:
            validate_instance(value, schema, artifact=str(path))
        except WorkflowError as exc:
            raise WorkflowError(f"invalid {path}: {exc}") from exc
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
            from .contracts import validate_instance

            try:
                validate_instance(value, schema, artifact=f"{path}:{source_sequence}")
            except WorkflowError as exc:
                raise WorkflowError(f"invalid {path}:{source_sequence}: {exc}") from exc
        records.append((source_sequence, value, sha256_bytes(canonical_json_bytes(value))))
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
    agent_run_id: str,
    relative_path: str,
    sequence: int,
    value: dict[str, Any],
    record_sha256: str,
) -> None:
    runner = value.get("runner") if isinstance(value.get("runner"), dict) else {}
    executor = value.get("executor") if isinstance(value.get("executor"), dict) else {}
    host = value.get("host") if isinstance(value.get("host"), dict) else {}
    connection.execute(
        """INSERT INTO health_samples VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            agent_run_id,
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
            value.get("last_semantic_progress_at"),
            value.get("seconds_since_semantic_progress"),
            value.get("last_semantic_progress_source"),
            record_sha256,
        ),
    )


def _bool_int(value: Any) -> int | None:
    return None if value is None else int(bool(value))


def _delete_run_projection(connection: sqlite3.Connection, agent_run_id: str) -> None:
    connection.execute("DELETE FROM runs WHERE agent_run_id = ?", (agent_run_id,))
    # A workflow can use a separate identity but is owned by one run directory.
    connection.execute("DELETE FROM workflows WHERE owner_run_id = ?", (agent_run_id,))


def _index_workflow(
    connection: sqlite3.Connection,
    agent_run_id: str,
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
        (workflow_id, agent_run_id, pack_id, snapshot_sha, workflow_state, event_count, indexed_at),
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
                workflow_id,node_id,kind,ticket_id,configured_agent_run_id,bound_agent_run_id,state,
                attempt,retry_of_agent_run_id,executor,model,interactive,terminal_reason
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                workflow_id,
                node_id,
                configured_node.get("kind"),
                configured_node.get("ticket_id"),
                configured_node.get("agent_run_id"),
                current_node.get("agent_run_id"),
                current_node.get("state"),
                current_node.get("attempt"),
                current_node.get("retry_of_agent_run_id"),
                configured_node.get("executor"),
                configured_node.get("model"),
                _bool_int(configured_node.get("interactive")),
                current_node.get("terminal_reason"),
            ),
        )
    return workflow_id, workflow_state


def _index_run(
    connection: sqlite3.Connection,
    agent_run_id: str,
    storage_class: str,
    run_dir: Path,
    source_fingerprint: str,
) -> dict[str, Any]:
    indexed_at = utc_now()
    unsafe = _unsafe_artifact_paths(run_dir)
    if unsafe:
        relative = ", ".join(path.relative_to(run_dir).as_posix() for path in unsafe)
        raise WorkflowError(f"unsafe source artifact symlink(s): {relative}")
    launch = _read_json(run_dir / "agent-run-contract.json") or {}
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

    agent_run = launch.get("agent_run") if isinstance(launch.get("agent_run"), dict) else {}
    worker_plan = launch.get("worker_plan") if isinstance(launch.get("worker_plan"), dict) else {}
    worktree = launch.get("worktree") if isinstance(launch.get("worktree"), dict) else {}
    pack = launch.get("pack") if isinstance(launch.get("pack"), dict) else {}
    workflow = provenance.get("workflow") if isinstance(provenance.get("workflow"), dict) else {}

    _delete_run_projection(connection, agent_run_id)
    connection.execute(
        """INSERT INTO runs(
            agent_run_id,source_dir,storage_class,index_state,index_error,source_fingerprint,
            launch_schema,ticket_id,pack_id,workflow_id,workflow_node_id,retry_of_agent_run_id,
            agent_name,agent_class,tier,executor,model,interactive,workdir,source_revision,
            branch,dirty_at_launch,created_at,started_at,finished_at,durable_status,
            disposition,failure_category,exit_code,final_receipt_sha256,evidence_complete,
            executor_result,completion_result,policy_result,acceptance_eligible,
            attempt_classification,score_verdict,evaluation_state,indexed_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            agent_run_id,
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
            agent_run.get("retry_of_agent_run_id") or provenance.get("retry_of_agent_run_id"),
            agent_run.get("agent_name") or provenance.get("agent_name"),
            agent_run.get("agent_class") or provenance.get("agent_class"),
            agent_run.get("tier"),
            worker_plan.get("executor") or provenance.get("executor"),
            worker_plan.get("model") or provenance.get("model"),
            _bool_int(worker_plan.get("interactive_stdio")),
            worktree.get("path") or provenance.get("worktree") or status.get("workdir"),
            worktree.get("source_revision") or provenance.get("source_revision"),
            worktree.get("branch"),
            _bool_int(worktree.get("dirty_at_launch")),
            agent_run.get("created_at") or status.get("created_at"),
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
                agent_run_id,returncode,exit_code,signal,timed_out,cancelled,stdout_truncated,
                stderr_truncated,stdout_bytes,stderr_bytes,duration_seconds,error_category,
                resolved_executable,executable_sha256,runner_pid,executor_pid,recorded_at,source_sha256
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                agent_run_id,
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
                    agent_run_id,stage,input_tokens,cached_input_tokens,output_tokens,
                    provider_total_tokens,reasoning_output_tokens,provider_billed_cost,
                    local_estimated_cost,currency,elapsed_seconds,first_output_latency_seconds,
                    retry_count,steer_count,steer_acknowledged_count,steer_pending_count,source_sha256
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    agent_run_id,
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
        file_sha = sha256_bytes(raw)
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
                        agent_run_id,relative_path,source_sequence,schema_id,event_id,recorded_at,
                        event_kind,category,state,outcome,actor,correlation_id,fingerprint,
                        content_sha256,summary,record_sha256
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (agent_run_id, relative, sequence, *fields, record_sha),
                )
                if schema == "agent-workflow/run-health-sample/v1":
                    _insert_health(connection, agent_run_id, relative, sequence, value, record_sha)
                elif schema == "agent-workflow/permission-event/v1":
                    connection.execute(
                        """INSERT INTO permission_events(
                            agent_run_id,relative_path,source_sequence,event_id,recorded_at,principal,operation,
                            resource_class,target,requested_access,state,source,policy_rule_id,
                            evidence_sha256,remediation_class,record_sha256
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            agent_run_id, relative, sequence, value["event_id"], value["recorded_at"],
                            value.get("principal"), value["operation"], value["resource_class"],
                            value.get("target"), value.get("requested_access"), value["state"],
                            value["source"], value.get("policy_rule_id"), value["evidence_sha256"],
                            value["remediation_class"], record_sha,
                        ),
                    )
                elif schema == "agent-workflow/incident-event/v1":
                    connection.execute(
                        """INSERT INTO incident_events(
                            agent_run_id,relative_path,source_sequence,incident_id,recorded_at,category,severity,
                            summary,fingerprint,state,record_sha256
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            agent_run_id, relative, sequence, value["incident_id"], value["recorded_at"],
                            value["category"], value["severity"], value["summary"],
                            value["fingerprint"], value["state"], record_sha,
                        ),
                    )
                elif schema == "agent-workflow/remediation-event/v1":
                    connection.execute(
                        """INSERT INTO remediation_events(
                            agent_run_id,relative_path,source_sequence,event_id,incident_id,recorded_at,rule_id,
                            action,outcome,reason_sha256,record_sha256
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            agent_run_id, relative, sequence, value["event_id"], value.get("incident_id"),
                            value["recorded_at"], value["rule_id"], value["action"],
                            value["outcome"], sha256_bytes(str(value.get("reason", "")).encode("utf-8")) if value.get("reason") else None, record_sha,
                        ),
                    )
        schema_ids_by_file[relative] = schemas
        if record_count is not None:
            record_counts[relative] = record_count
        connection.execute(
            "INSERT INTO source_files VALUES(?,?,?,?,?,?,?,?,?)",
            (
                agent_run_id,
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

    workflow_id, workflow_state = _index_workflow(connection, agent_run_id, run_dir, indexed_at)
    if workflow_id is not None:
        connection.execute(
            "UPDATE runs SET workflow_id = COALESCE(workflow_id, ?) WHERE agent_run_id = ?",
            (workflow_id, agent_run_id),
        )
    return {
        "agent_run_id": agent_run_id,
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
    agent_run_id: str,
    storage_class: str,
    run_dir: Path,
    source_fingerprint: str,
    error: Exception,
) -> None:
    indexed_at = utc_now()
    _delete_run_projection(connection, agent_run_id)
    detail = str(error)[:4096]
    connection.execute(
        """INSERT INTO runs(
            agent_run_id,source_dir,storage_class,index_state,index_error,source_fingerprint,
            evidence_complete,indexed_at
        ) VALUES(?,?,?,?,?,?,?,?)""",
        (agent_run_id, str(run_dir), storage_class, "error", detail, source_fingerprint, 0, indexed_at),
    )
    category = "unsafe_source" if "unsafe source artifact" in detail else "run_index_failed"
    connection.execute(
        "INSERT INTO index_errors(agent_run_id,source_path,detected_at,category,detail) VALUES(?,?,?,?,?)",
        (agent_run_id, str(run_dir), indexed_at, category, detail),
    )



def _sync_locked(
    settings: Settings,
    *,
    agent_run_id: str | None,
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
            settings, include_archived=include_archived, agent_run_id=agent_run_id
        )
        discovered_ids = {item[0] for item in discovered}
        for current_agent_run_id, storage_class, run_dir in discovered:
            fingerprint = _source_fingerprint(run_dir)
            current = connection.execute(
                "SELECT source_fingerprint, source_dir, storage_class, index_state FROM runs WHERE agent_run_id = ?",
                (current_agent_run_id,),
            ).fetchone()
            if (
                not force
                and current is not None
                and current["source_fingerprint"] == fingerprint
                and current["source_dir"] == str(run_dir)
                and current["storage_class"] == storage_class
                and current["index_state"] == "current"
            ):
                skipped.append(current_agent_run_id)
                continue
            try:
                with connection:
                    indexed.append(
                        _index_run(
                            connection,
                            current_agent_run_id,
                            storage_class,
                            run_dir,
                            fingerprint,
                        )
                    )
            except Exception as exc:  # preserve other healthy projections
                with connection:
                    _record_index_error(
                        connection,
                        agent_run_id=current_agent_run_id,
                        storage_class=storage_class,
                        run_dir=run_dir,
                        source_fingerprint=fingerprint,
                        error=exc,
                    )
                errors.append({"agent_run_id": current_agent_run_id, "error": str(exc)})
        if agent_run_id is None:
            existing = {
                str(row[0])
                for row in connection.execute("SELECT agent_run_id FROM runs").fetchall()
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
    return report


def sync_index(
    settings: Settings,
    *,
    agent_run_id: str | None = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    with _writer_lock(settings):
        return _sync_locked(
            settings,
            agent_run_id=agent_run_id,
            include_archived=include_archived,
            force=False,
        )


def rebuild_index(
    settings: Settings,
    *,
    agent_run_id: str | None = None,
    include_archived: bool = True,
) -> dict[str, Any]:
    with _writer_lock(settings):
        if agent_run_id is None:
            path = database_path(settings)
            for candidate in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
                if candidate.exists() or candidate.is_symlink():
                    if candidate.is_symlink() or not candidate.is_file():
                        raise WorkflowError(f"unsafe SQLite index path: {candidate}")
                    candidate.unlink()
        return _sync_locked(
            settings,
            agent_run_id=agent_run_id,
            include_archived=include_archived,
            force=True,
        )


def index_status(settings: Settings) -> dict[str, Any]:
    path = database_path(settings)
    discovered = _discover_runs(settings, include_archived=True, agent_run_id=None)
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
        return report
    connection = _connect(settings, readonly=True)
    try:
        application_id, version = _validated_database_header(connection)
        journal_mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0])
        rows = {
            str(row["agent_run_id"]): row
            for row in connection.execute(
                "SELECT agent_run_id,source_dir,storage_class,index_state,source_fingerprint FROM runs"
            )
        }
        error_count = sum(
            1 for row in rows.values() if row["index_state"] == "error"
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
    for agent_run_id, storage_class, run_dir in discovered:
        row = rows.get(agent_run_id)
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
    return report


def verify_index(
    settings: Settings, *, full: bool = False, review_agent_run_id: str | None = None
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
                "SELECT r.source_dir, f.agent_run_id, f.relative_path, f.sha256, f.size_bytes "
                "FROM source_files f JOIN runs r ON r.agent_run_id=f.agent_run_id ORDER BY f.agent_run_id,f.relative_path"
            ):
                path = Path(str(row["source_dir"])) / str(row["relative_path"])
                if path.is_symlink() or not path.is_file():
                    mismatches.append(
                        {"agent_run_id": row["agent_run_id"], "path": str(path), "reason": "missing_or_unsafe"}
                    )
                    continue
                info = path.stat()
                if info.st_size != row["size_bytes"] or _sha256_file(path) != row["sha256"]:
                    mismatches.append(
                        {"agent_run_id": row["agent_run_id"], "path": str(path), "reason": "content_changed"}
                    )
        for row in connection.execute(
            "SELECT r.agent_run_id,r.source_dir,r.index_error,e.category "
            "FROM runs r LEFT JOIN index_errors e ON e.agent_run_id=r.agent_run_id "
            "AND e.detected_at=(SELECT MAX(e2.detected_at) FROM index_errors e2 WHERE e2.agent_run_id=r.agent_run_id) "
            "WHERE r.index_state != 'current' ORDER BY r.agent_run_id"
        ):
            mismatches.append(
                {
                    "agent_run_id": row["agent_run_id"],
                    "path": row["source_dir"],
                    "reason": (
                        "unsafe_symlink"
                        if "unsafe source artifact" in (row["index_error"] or "")
                        else "index_error"
                    ),
                    "classification": "blocking",
                    "outcome": "verification_failed",
                    "detail": row["index_error"],
                }
            )
        if review_agent_run_id is not None:
            review_result = verify_review_projection(settings, connection, review_agent_run_id)
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
    if review_result is not None:
        report.update(review_result)
    else:
        report.update({"review_scope": None, "review_valid": None, "review_errors": [], "review_evidence": None})
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
    agent_run_id: str | None = None,
    state: str | None = None,
    category: str | None = None,
    executor: str | None = None,
    model: str | None = None,
    pack_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    sql, parameters = _build_query(
        kind,
        agent_run_id=agent_run_id,
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
