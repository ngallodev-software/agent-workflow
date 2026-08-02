from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.conftest import InstalledProduct


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def test_installed_index_rebuilds_and_preserves_query_results_after_database_loss(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
) -> None:
    state = Path(product_env["XDG_STATE_HOME"]) / "agent-workflow"
    run = state / "runs" / "index-product"
    _write_json(
        run / "status.json",
        {
            "schema": "agent-workflow/session-status/v2",
            "session_id": "index-product",
            "status": "running",
            "created_at": "2026-07-30T00:00:00+00:00",
            "updated_at": "2026-07-30T00:01:00+00:00",
            "workdir": "/tmp/index-product",
            "prompt_path": str(run / "prompt.md"),
            "log_path": str(run / "output.log"),
            "ticket_id": "IDX-004",
            "pack_id": "sqlite-evidence-index",
            "disposition": None,
            "failure_category": None,
        },
    )
    (run / "incident-events.jsonl").write_text(
        json.dumps(
            {
                "schema": "agent-workflow/incident-event/v1",
                "incident_id": "a" * 24,
                "session_id": "index-product",
                "recorded_at": "2026-07-30T00:02:00+00:00",
                "category": "process_alive_no_progress",
                "severity": "medium",
                "summary": "No semantic progress",
                "fingerprint": "b" * 64,
                "evidence": {},
                "state": "open",
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    first = installed_product.json("index", "rebuild", env=product_env)
    assert first["indexed_count"] == 1
    status = installed_product.json("index", "status", env=product_env)
    assert status["freshness"] == "current"
    assert status["journal_mode"] == "wal"
    runs_query_before = installed_product.json(
        "index", "query", "runs", "--session", "index-product", env=product_env
    )
    incidents_query_before = installed_product.json(
        "index",
        "query",
        "incidents",
        "--category",
        "process_alive_no_progress",
        env=product_env,
    )
    assert runs_query_before["freshness"] == "current"
    assert incidents_query_before["freshness"] == "current"
    rows_before = runs_query_before["rows"]
    incidents_before = incidents_query_before["rows"]
    assert rows_before[0]["source_dir"] == str(run)
    assert incidents_before[0]["relative_path"] == "incident-events.jsonl"
    assert installed_product.json("index", "verify", "--full", env=product_env)["valid"] is True

    database = Path(status["database"])
    for candidate in (database, Path(f"{database}-wal"), Path(f"{database}-shm")):
        if candidate.exists():
            candidate.unlink()

    missing = installed_product.json("index", "status", env=product_env)
    assert missing["freshness"] == "missing"
    second = installed_product.json("index", "rebuild", env=product_env)
    assert second["indexed_count"] == 1
    runs_query_after = installed_product.json(
        "index", "query", "runs", "--session", "index-product", env=product_env
    )
    incidents_query_after = installed_product.json(
        "index",
        "query",
        "incidents",
        "--category",
        "process_alive_no_progress",
        env=product_env,
    )
    rows_after = runs_query_after["rows"]
    incidents_after = incidents_query_after["rows"]
    comparable_before = [
        {key: value for key, value in row.items() if key != "indexed_at"}
        for row in rows_before
    ]
    comparable_after = [
        {key: value for key, value in row.items() if key != "indexed_at"}
        for row in rows_after
    ]
    assert comparable_after == comparable_before
    assert rows_after[0]["indexed_at"] != rows_before[0]["indexed_at"]
    assert incidents_after == incidents_before


def test_installed_integrity_authority_is_explicit_and_legacy_is_untrusted(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
) -> None:
    state = Path(product_env["XDG_STATE_HOME"]) / "agent-workflow"
    run = state / "runs" / "integrity-product"
    _write_json(
        run / "status.json",
        {
            "schema": "agent-workflow/session-status/v2",
            "session_id": "integrity-product",
            "status": "running",
            "created_at": "2026-07-30T00:00:00+00:00",
            "updated_at": "2026-07-30T00:01:00+00:00",
            "workdir": "/tmp/integrity-product",
            "prompt_path": str(run / "prompt.md"),
            "log_path": str(run / "output.log"),
            "ticket_id": "MAINT-007-A",
            "pack_id": "delegation-communication-reliability",
            "disposition": None,
            "failure_category": None,
        },
    )
    rebuilt = installed_product.json("index", "rebuild", env=product_env)
    assert rebuilt["error_count"] == 0
    authority = Path(rebuilt["database"]).parent / "integrity-authority-v2.jsonl"
    assert not authority.exists()
    assert installed_product.json("index", "verify", "--full", env=product_env)["valid"] is True
    assert not authority.exists()
    migration = installed_product.json("index", "integrity", "migrate", env=product_env)
    assert migration["legacy_trust"] == "none"
    record = installed_product.json(
        "index", "integrity", "record", "integrity-product", "status.json", "1",
        "run_index_failed", "installed test error", env=product_env
    )
    assert record["authority"] == "v2-append-only"
    assert len(authority.read_text(encoding="utf-8").splitlines()) == 2


@pytest.mark.parametrize("storage_root", ["runs", "archive"])
def test_installed_full_verify_classifies_legacy_retired_record_without_accepting_it(
    installed_product: InstalledProduct,
    product_env: dict[str, str],
    storage_root: str,
) -> None:
    state = Path(product_env["XDG_STATE_HOME"]) / "agent-workflow"
    legacy = state / storage_root / "legacy-installed"
    _write_json(
        legacy / "status.json",
        {
            "schema": "agent-workflow/session-status/v2",
            "session_id": "legacy-installed",
            "status": "completed",
            "created_at": "2025-01-01T00:00:00+00:00",
            "workdir": "/tmp/legacy-installed",
            "prompt_path": str(legacy / "prompt.md"),
            "log_path": str(legacy / "output.log"),
        },
    )
    _write_json(
        legacy / "execution-metrics.json",
        {"schema": "agent-workflow/execution-metrics/retired-v1"},
    )

    rebuilt = installed_product.json("index", "rebuild", env=product_env)
    assert rebuilt["error_count"] == 0
    assert rebuilt["quarantined_count"] == 1
    verification = installed_product.json("index", "verify", "--full", env=product_env)
    assert verification["valid"] is True
    assert verification["historical_artifacts"][0]["classification"] == "quarantined"
