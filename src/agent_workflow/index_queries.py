"""Pure query construction and report shaping for the SQLite projection."""

from __future__ import annotations

from typing import Any, Sequence

from .contracts import validate_instance
from .errors import WorkflowError
from .util import validate_id

QUERY_COLUMNS: dict[str, tuple[str, Sequence[str]]] = {
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
    "repairs": (
        "SELECT repair_id,source_session_id,source_final_receipt_sha256,source_artifact_path,source_artifact_sha256,adapter_id,adapter_version,adapter_sha256,canonical_sha256,validation_result,source_mutation_verified,repair_receipt_sha256,repair_dir,created_at,actor,indexed_at FROM evidence_repairs",
        ("repair_id", "source_session_id", "source_final_receipt_sha256", "source_artifact_path", "source_artifact_sha256", "adapter_id", "adapter_version", "adapter_sha256", "canonical_sha256", "validation_result", "source_mutation_verified", "repair_receipt_sha256", "repair_dir", "created_at", "actor", "indexed_at"),
    ),
    "errors": (
        "SELECT error_id,session_id,source_path,detected_at,category,detail FROM index_errors",
        ("error_id", "session_id", "source_path", "detected_at", "category", "detail"),
    ),
}


def build_query(
    kind: str,
    *,
    session_id: str | None = None,
    state: str | None = None,
    category: str | None = None,
    executor: str | None = None,
    model: str | None = None,
    pack_id: str | None = None,
    limit: int = 100,
) -> tuple[str, list[Any]]:
    """Build a parameterized, bounded read-only query for one public view."""
    if kind not in QUERY_COLUMNS:
        raise WorkflowError(f"unsupported index query: {kind}")
    if not 1 <= limit <= 10000:
        raise WorkflowError("index query limit must be between 1 and 10000")
    if session_id is not None:
        validate_id(session_id, "session ID")

    base, columns = QUERY_COLUMNS[kind]
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
        ("source_session_id" if kind == "repairs" else "session_id", session_id),
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
            raise WorkflowError(
                f"filter {column!r} is not supported for index query {kind!r}"
            )
        clauses.append(f"{column} = ?")
        parameters.append(value)

    sql = f"SELECT * FROM ({base})"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    order_column = (
        "recorded_at"
        if "recorded_at" in supported
        else ("started_at" if "started_at" in supported else columns[0])
    )
    sql += f" ORDER BY {order_column} DESC LIMIT ?"
    parameters.append(limit)
    return sql, parameters


def build_query_report(
    status: dict[str, Any],
    kind: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bind query rows to the freshness metadata needed to interpret them."""
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
