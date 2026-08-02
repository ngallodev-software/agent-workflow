from __future__ import annotations

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.index_queries import QUERY_COLUMNS, build_query, build_query_report


def test_public_query_inventory_is_explicit() -> None:
    assert set(QUERY_COLUMNS) == {
        "runs",
        "incidents",
        "permissions",
        "performance",
        "workflows",
        "workflow-nodes",
        "errors",
    }


def test_query_builder_preserves_filters_order_and_bound_limit() -> None:
    sql, parameters = build_query(
        "runs",
        session_id="session-1",
        state="running",
        executor="codex",
        model="gpt-5.6-luna",
        pack_id="pack-1",
        limit=25,
    )
    assert "session_id = ?" in sql
    assert "durable_status = ?" in sql
    assert "executor = ?" in sql
    assert "model = ?" in sql
    assert "pack_id = ?" in sql
    assert sql.endswith("ORDER BY started_at DESC LIMIT ?")
    assert parameters == [
        "session-1",
        "running",
        "codex",
        "gpt-5.6-luna",
        "pack-1",
        25,
    ]


def test_query_builder_rejects_unsupported_filter_and_limit() -> None:
    with pytest.raises(WorkflowError, match="not supported"):
        build_query("performance", session_id="session-1")
    with pytest.raises(WorkflowError, match="between 1 and 10000"):
        build_query("runs", limit=0)
    with pytest.raises(WorkflowError, match="unsupported index query"):
        build_query("unknown")


def test_query_report_binds_rows_to_freshness_metadata() -> None:
    status = {
        "database": "/tmp/index.sqlite3",
        "authority": "json-jsonl-sealed-receipts",
        "freshness": "stale",
        "current_run_count": 2,
        "stale_run_count": 1,
        "error_count": 0,
    }
    rows = [{"session_id": "session-1"}]
    report = build_query_report(status, "runs", rows)
    assert report["schema"] == "agent-workflow/index-query/v1"
    assert report["freshness"] == "stale"
    assert report["rows"] is rows
