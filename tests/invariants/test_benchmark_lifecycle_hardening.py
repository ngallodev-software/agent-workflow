from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_workflow.benchmarking import live_review, service
from agent_workflow.config import defaults


def test_live_review_status_reports_fully_stopped_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator = tmp_path / "coordinator"
    run_dir = coordinator / "benchmarks" / "runs" / "run-1"
    run_dir.mkdir(parents=True)
    plan = {
        "run_id": "run-1",
        "benchmark_id": "benchmark-1",
        "coordinator": {"worktree": str(coordinator), "run_dir": str(run_dir)},
    }
    plan_path = run_dir / "run-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    runtime = coordinator / ".agent-workflow-benchmark-runtime" / "run-1"
    runtime.mkdir(parents=True)
    (runtime / "live-review.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "apps": [
                    {"pid": 111, "state": "stopped", "url": "http://127.0.0.1:1"},
                    {"pid": 222, "state": "stopped", "url": "http://127.0.0.1:2"},
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(live_review, "_pid_alive", lambda pid: False)

    status = live_review.live_review_status(plan_path)

    assert status["state"] == "stopped"
    assert status["ready"] == 0
    assert status["total"] == 2


def test_live_review_defaults_to_lan_binding_and_distinct_ephemeral_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = live_review._server_config({})
    assert config["host"] == "0.0.0.0"
    first = live_review._free_port(config["host"])
    second = live_review._free_port(config["host"], excluded={first})
    assert first != second
    monkeypatch.setenv("AGENT_WORKFLOW_BENCHMARK_ADVERTISE_HOST", "192.168.1.42")
    assert live_review._lan_host() == "192.168.1.42"


def test_automated_pipeline_records_failed_stage_before_reraising(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    plan = {
        "run_id": "run-1",
        "benchmark_id": "benchmark-1",
        "coordinator": {"run_dir": str(run_dir)},
    }
    plan_path = run_dir / "run-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps({"run_id": "run-1", "state": "planned"}),
        encoding="utf-8",
    )

    monkeypatch.setattr(service, "execute_run", lambda path: {"state": "executed"})
    monkeypatch.setattr(
        service,
        "start_live_review",
        lambda path: (_ for _ in ()).throw(RuntimeError("server failed")),
    )

    with pytest.raises(RuntimeError, match="server failed"):
        service._finalize_automated(defaults(tmp_path / "config.toml"), plan_path)

    state = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert state["state"] == "failed"
    assert state["failed_stage"] == "live_review"
    assert state["error"] == "server failed"
    assert state["live_review_stage_wall_seconds"] >= 0


def test_pid_permission_error_is_treated_as_alive(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(pid: int, signal: int) -> None:
        raise PermissionError("not owner")

    monkeypatch.setattr(live_review.os, "kill", denied)
    assert live_review._pid_alive(1234) is True


def test_zombie_pid_is_treated_as_exited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    stat = tmp_path / "stat"
    stat.write_text("1234 (benchmark-server) Z 1 1234 1234\n", encoding="utf-8")
    monkeypatch.setattr(live_review.os, "kill", lambda pid, signal: None)
    original_path = live_review.Path

    def proc_path(value: str) -> Path:
        return stat if value == "/proc/1234/stat" else original_path(value)

    monkeypatch.setattr(live_review, "Path", proc_path)

    assert live_review._pid_alive(1234) is False


def test_cleanup_preserves_worktrees_when_live_server_cannot_stop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_dir = tmp_path / "coordinator" / "benchmarks" / "runs" / "run-1"
    coordinator = run_dir.parents[2]
    coordinator.mkdir(parents=True)
    worktree = tmp_path / "control"
    worktree.mkdir()
    plan = {
        "run_id": "run-1",
        "coordinator": {"run_dir": str(run_dir), "worktree": str(coordinator)},
        "source": {"repository": str(tmp_path / "source")},
        "pairs": [
            {
                "pair_id": "pair-1",
                "attempts": [
                    {
                        "attempt": 1,
                        "arms": {
                            "control_raw": {"worktree": str(worktree), "branch": "control"},
                            "workflow_full": {"worktree": str(tmp_path / "workflow"), "branch": "workflow"},
                        },
                    }
                ],
            }
        ],
    }
    (tmp_path / "workflow").mkdir()
    run_dir.mkdir(parents=True)
    plan_path = run_dir / "run-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(service, "verify_consolidated_run", lambda path: {"valid": True})
    monkeypatch.setattr(
        service,
        "stop_live_review",
        lambda path: {"remaining": 1, "failed": 1, "stopped": 0},
    )

    with pytest.raises(Exception, match="worktrees were preserved"):
        service.cleanup_benchmark(
            defaults(tmp_path / "config.toml"),
            plan_path,
            remove_worktrees=True,
            stop_live_apps=True,
        )

    assert worktree.is_dir()
