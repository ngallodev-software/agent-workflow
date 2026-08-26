from __future__ import annotations

import json
import os
import sqlite3
import shutil

import pytest
from dataclasses import replace
from pathlib import Path

from agent_workflow.cli import main
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.index_db import database_path, integrity_authority_path
from agent_workflow.index_integrity import integrity_input_snapshot, record_integrity_authority
from agent_workflow.index_schema import INDEX_APPLICATION_ID, INDEX_SCHEMA_VERSION
from agent_workflow.index_store import (
    index_status,
    query_index,
    query_index_report,
    rebuild_index,
    sync_index,
    verify_index,
)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _append(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")


def _settings(tmp_path: Path):
    config = tmp_path / "config.toml"
    state_root = tmp_path / "state"
    worktree_root = tmp_path / "worktrees"
    config.write_text(
        "schema_version = 1\n\n"
        "[paths]\n"
        f"state_root = {json.dumps(str(state_root))}\n"
        f"worktree_root = {json.dumps(str(worktree_root))}\n",
        encoding="utf-8",
    )
    return replace(
        defaults(config),
        state_root=state_root,
        worktree_root=worktree_root,
    )


def _status(run: Path, agent_run_id: str) -> None:
    _write(
        run / "status.json",
        {
            "schema": "agent-workflow/agent-run-status/v1",
            "agent_run_id": agent_run_id,
            "status": "running",
            "created_at": "2026-07-30T00:00:00+00:00",
            "updated_at": "2026-07-30T00:01:00+00:00",
            "workdir": "/tmp/worktree",
            "prompt_path": str(run / "prompt.md"),
            "log_path": str(run / "output.log"),
            "ticket_id": "IDX-001",
            "pack_id": "sqlite-index",
            "disposition": None,
            "failure_category": None,
            "worker_mode": "headless",
        },
    )


def _health(agent_run_id: str) -> dict:
    process = {
        "pid": 123,
        "alive": True,
        "state": "S",
        "parent_pid": 1,
        "process_start_ticks": 10,
        "cpu_user_seconds": 1.5,
        "cpu_system_seconds": 0.5,
        "rss_bytes": 4096,
        "peak_rss_bytes": 8192,
        "threads": 2,
        "read_bytes": 10,
        "write_bytes": 20,
        "open_fd_count": 3,
        "child_process_count": 0,
        "collector": "test",
    }
    return {
        "schema": "agent-workflow/run-health-sample/v2",
        "agent_run_id": agent_run_id,
        "recorded_at": "2026-07-30T00:02:00+00:00",
        "runner": process,
        "executor": process,
        "host": {
            "load_1m": 0.1,
            "load_5m": 0.2,
            "load_15m": 0.3,
            "available_memory_bytes": 100000,
            "disk_free_bytes": 200000,
            "disk_total_bytes": 300000,
        },
        "output_bytes": 100,
        "stderr_bytes": 0,
        "executor_event_bytes": 50,
        "last_semantic_progress_at": "2026-07-30T00:01:59+00:00",
        "seconds_since_semantic_progress": 1.0,
        "last_semantic_progress_source": "executor_event",
    }


def _seed_run(settings, agent_run_id: str = "run-one") -> Path:
    run = settings.state_root / "runs" / agent_run_id
    run.mkdir(parents=True)
    _status(run, agent_run_id)
    _append(run / "run-health-samples.jsonl", _health(agent_run_id))
    _append(
        run / "incident-events.jsonl",
        {
            "schema": "agent-workflow/incident-event/v1",
            "incident_id": "a" * 24,
            "agent_run_id": agent_run_id,
            "recorded_at": "2026-07-30T00:03:00+00:00",
            "category": "process_alive_no_progress",
            "severity": "medium",
            "summary": "No semantic progress",
            "fingerprint": "b" * 64,
            "evidence": {"seconds": 600},
            "state": "open",
        },
    )
    _append(
        run / "permission-events.jsonl",
        {
            "schema": "agent-workflow/permission-event/v1",
            "event_id": "c" * 24,
            "agent_run_id": agent_run_id,
            "recorded_at": "2026-07-30T00:04:00+00:00",
            "principal": None,
            "operation": "execute",
            "resource_class": "command",
            "target": None,
            "requested_access": "manual approval",
            "state": "pending",
            "source": "executor_stderr",
            "policy_rule_id": None,
            "evidence_sha256": "d" * 64,
            "remediation_class": "human_required",
        },
    )
    _append(
        run / "remediation-events.jsonl",
        {
            "schema": "agent-workflow/remediation-event/v1",
            "event_id": "e" * 24,
            "agent_run_id": agent_run_id,
            "incident_id": "a" * 24,
            "recorded_at": "2026-07-30T00:05:00+00:00",
            "rule_id": "probe-stalled-v1",
            "action": "progress_probe",
            "outcome": "queued",
            "reason": "SECRET REMEDIATION REASON",
            "details": {},
        },
    )
    _write(
        run / "process-result.json",
        {
            "schema": "agent-workflow/process-result/v1",
            "argv": ["executor"],
            "resolved_executable": "/usr/bin/executor",
            "executable_version": None,
            "executable_sha256": None,
            "returncode": 0,
            "exit_code": 0,
            "signal": None,
            "timed_out": False,
            "cancelled": False,
            "stdout_truncated": False,
            "stderr_truncated": False,
            "stdout_bytes": 100,
            "stderr_bytes": 0,
            "stdout_spool": None,
            "stderr_spool": None,
            "duration_seconds": 12.0,
            "error_category": "none",
            "environment_policy": "controlled",
            "runner_pid": 122,
            "executor_pid": 123,
            "recorded_at": "2026-07-30T00:06:00+00:00",
        },
    )
    _write(
        run / "execution-metrics.json",
        {
            "schema": "agent-workflow/execution-metrics/v1",
            "agent_run_id": agent_run_id,
            "stages": [
                {
                    "stage": "total",
                    "input_tokens": 100,
                    "cached_input_tokens": 20,
                    "output_tokens": 30,
                    "provider_total_tokens": 130,
                    "cache_write_input_tokens": None,
                    "reasoning_output_tokens": 5,
                    "provider_billed_cost": 0.01,
                    "local_estimated_cost": None,
                    "price_catalog_id": "test",
                    "currency": "USD",
                    "elapsed_seconds": 12,
                    "first_output_latency_seconds": 1,
                    "retry_count": 0,
                    "errors": [],
                    "steer_count": 1,
                    "steer_acknowledged_count": 1,
                    "steer_pending_count": 0,
                }
            ],
        },
    )
    return run


def test_corrupt_run_is_rejected_without_losing_other_runs(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _seed_run(settings, "healthy")
    corrupt = settings.state_root / "runs" / "corrupt"
    corrupt.mkdir(parents=True)
    _status(corrupt, "corrupt")
    (corrupt / "incident-events.jsonl").write_text("{not-json}\n", encoding="utf-8")

    report = rebuild_index(settings)
    assert report["indexed_count"] == 1
    assert report["error_count"] == 1
    rows = {row["agent_run_id"]: row for row in query_index(settings, "runs")}
    assert rows["healthy"]["index_state"] == "current"
    assert rows["corrupt"]["index_state"] == "error"
    assert query_index(settings, "errors", agent_run_id="corrupt")


def test_symlinked_source_is_rejected_without_following_target(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    run = settings.state_root / "runs" / "unsafe"
    run.mkdir(parents=True)
    _status(run, "unsafe")
    target = tmp_path / "external-incident.jsonl"
    target.write_text("SECRET TARGET CONTENT\n", encoding="utf-8")
    (run / "incident-events.jsonl").symlink_to(target)

    report = rebuild_index(settings)
    assert report["indexed_count"] == 0
    assert report["error_count"] == 1
    row = query_index(settings, "runs", agent_run_id="unsafe")[0]
    assert row["index_state"] == "error"
    assert "incident-events.jsonl" in row["index_error"]
    error = query_index(settings, "errors", agent_run_id="unsafe")[0]
    assert error["category"] == "unsafe_source"
    assert index_status(settings)["freshness"] == "incomplete"
    verification = verify_index(settings, full=True)
    assert verification["valid"] is False
    assert any(item["reason"] == "unsafe_symlink" for item in verification["source_mismatches"])
    with sqlite3.connect(database_path(settings)) as connection:
        assert "SECRET TARGET CONTENT" not in "\n".join(connection.iterdump())






def test_execution_metrics_missing_current_required_fields_is_blocking(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    run = _seed_run(settings, "metrics-invalid")
    metrics_path = run / "execution-metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    for stage in metrics["stages"]:
        for field in (
            "cache_write_input_tokens",
            "reasoning_output_tokens",
            "provider_billed_cost",
            "local_estimated_cost",
            "price_catalog_id",
        ):
            stage.pop(field, None)
    _write(metrics_path, metrics)
    status_path = run / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["status"] = "completed"
    _write(status_path, status)

    rebuilt = rebuild_index(settings)
    assert rebuilt["error_count"] == 1
    row = query_index(settings, "runs", agent_run_id="metrics-invalid")[0]
    assert row["index_state"] == "error"
    assert verify_index(settings, full=True)["valid"] is False




def test_workflow_projection_materializes_nodes_and_edges(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    run = _seed_run(settings, "workflow-owner")
    _write(
        run / "workflow-snapshot.json",
        {
            "schema": "agent-workflow/workflow-snapshot/v1",
            "workflow_id": "wf-one",
            "pack_id": "pack-one",
            "pack_manifest_sha256": "3" * 64,
            "nodes": [
                {
                    "node_id": "build",
                    "kind": "task",
                    "ticket_id": "IDX-001",
                    "agent_run_id": "build-run",
                    "prompt_path": "build.md",
                    "dependencies": [],
                    "executor": "codex",
                    "model": "gpt-test",
                    "interactive": False,
                },
                {
                    "node_id": "review",
                    "kind": "task",
                    "ticket_id": "IDX-002",
                    "agent_run_id": "review-run",
                    "prompt_path": "review.md",
                    "dependencies": ["build"],
                    "executor": "claude",
                    "model": "sonnet",
                    "interactive": False,
                },
            ],
        },
    )
    _write(
        run / "workflow-status.json",
        {
            "schema": "agent-workflow/workflow-status/v1",
            "workflow_id": "wf-one",
            "snapshot_sha256": "4" * 64,
            "event_count": 2,
            "workflow_state": "running",
            "nodes": [
                {
                    "node_id": "build",
                    "kind": "task",
                    "state": "completed",
                    "agent_run_id": "build-run",
                    "attempt": 1,
                    "retry_of_agent_run_id": None,
                    "bound_at": "2026-07-30T00:00:00+00:00",
                    "terminal_reason": None,
                },
                {
                    "node_id": "review",
                    "kind": "task",
                    "state": "running",
                    "agent_run_id": "review-run",
                    "attempt": 1,
                    "retry_of_agent_run_id": None,
                    "bound_at": "2026-07-30T00:10:00+00:00",
                    "terminal_reason": None,
                },
            ],
        },
    )

    report = rebuild_index(settings)
    assert report["error_count"] == 0
    assert query_index(settings, "workflows")[0]["workflow_state"] == "running"
    nodes = query_index(settings, "workflow-nodes", limit=10)
    assert {row["node_id"] for row in nodes} == {"build", "review"}
    with sqlite3.connect(database_path(settings)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM workflow_edges").fetchone()[0] == 1


def test_foreign_or_newer_database_is_rejected_without_touching_sources(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    run = _seed_run(settings, "authority-run")
    path = database_path(settings)

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA application_id = 1234")
    with pytest.raises(WorkflowError, match="another application"):
        sync_index(settings)
    assert (run / "status.json").is_file()

    path.unlink()
    with sqlite3.connect(path) as connection:
        connection.execute(f"PRAGMA application_id = {INDEX_APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version = {INDEX_SCHEMA_VERSION + 1}")
    with pytest.raises(WorkflowError, match="not current"):
        sync_index(settings)
    assert (run / "status.json").is_file()


def test_read_paths_reject_foreign_database_and_database_symlink(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _seed_run(settings, "read-guard")
    path = database_path(settings)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA application_id = 1234")
    with pytest.raises(WorkflowError, match="not owned"):
        index_status(settings)
    with pytest.raises(WorkflowError, match="not owned"):
        query_index(settings, "runs")

    path.unlink()
    target = tmp_path / "foreign.sqlite3"
    with sqlite3.connect(target) as connection:
        connection.execute("CREATE TABLE foreign_data(value TEXT)")
    path.symlink_to(target)
    with pytest.raises(WorkflowError, match="unsafe"):
        sync_index(settings)


def test_performance_projection_never_coalesces_provider_and_local_cost(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _seed_run(settings, "provider-cost")
    local_run = _seed_run(settings, "local-cost")
    metrics_path = local_run / "execution-metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    stage = metrics["stages"][0]
    stage["provider_billed_cost"] = None
    stage["local_estimated_cost"] = 0.02
    stage["currency"] = "EUR"
    _write(metrics_path, metrics)

    rebuild_index(settings)
    row = query_index(settings, "performance")[0]
    assert row["sample_count"] == 2
    assert row["provider_billed_sample_count"] == 1
    assert row["avg_provider_billed_cost"] == pytest.approx(0.01)
    assert row["provider_billed_currency"] == "USD"
    assert row["local_estimated_sample_count"] == 1
    assert row["avg_local_estimated_cost"] == pytest.approx(0.02)
    assert row["local_estimated_currency"] == "EUR"
    assert "avg_cost" not in row


def test_performance_projection_nulls_mixed_currency_averages(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    usd_run = _seed_run(settings, "usd-cost")
    eur_run = _seed_run(settings, "eur-cost")
    eur_metrics_path = eur_run / "execution-metrics.json"
    eur_metrics = json.loads(eur_metrics_path.read_text(encoding="utf-8"))
    eur_metrics["stages"][0]["provider_billed_cost"] = 0.02
    eur_metrics["stages"][0]["currency"] = "EUR"
    _write(eur_metrics_path, eur_metrics)

    rebuild_index(settings)
    row = query_index(settings, "performance")[0]
    assert row["sample_count"] == 2
    assert row["provider_billed_sample_count"] == 2
    assert row["avg_provider_billed_cost"] is None
    assert row["provider_billed_currency"] is None


def test_query_report_exposes_stale_projection_freshness(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    run = _seed_run(settings, "stale-query")
    rebuild_index(settings)

    status_path = run / "status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["ticket_id"] = "IDX-002"
    _write(status_path, status)

    report = query_index_report(settings, "runs", agent_run_id="stale-query")
    assert report["freshness"] == "stale"
    assert report["stale_run_count"] == 1
    assert report["rows"][0]["durable_status"] == "running"


def test_source_fingerprint_detects_same_size_same_mtime_content_change(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    run = _seed_run(settings, "ctime-change")
    rebuild_index(settings)

    status_path = run / "status.json"
    before = status_path.stat()
    raw = status_path.read_text(encoding="utf-8")
    changed = raw.replace('"ticket_id": "IDX-001"', '"ticket_id": "IDX-002"')
    assert len(changed.encode("utf-8")) == len(raw.encode("utf-8"))
    status_path.write_text(changed, encoding="utf-8")
    os.utime(status_path, ns=(before.st_atime_ns, before.st_mtime_ns))

    assert index_status(settings)["freshness"] == "stale"


def test_status_rejects_broken_database_symlink(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    path = database_path(settings)
    path.symlink_to(tmp_path / "missing.sqlite3")
    with pytest.raises(WorkflowError, match="unsafe"):
        index_status(settings)
