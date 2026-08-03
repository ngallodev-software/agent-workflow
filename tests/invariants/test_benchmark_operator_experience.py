from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_workflow.benchmarking import operator_panes
from agent_workflow.benchmarking.common import file_inventory
from agent_workflow.benchmarking.operator_panes import (
    ensure_operator_panes,
    operator_pane_preflight,
    respawn,
)
from agent_workflow.errors import WorkflowError

REPO_ROOT = Path(__file__).resolve().parents[2]


def _plan(tmp_path: Path) -> dict[str, object]:
    coordinator = tmp_path / "coordinator"
    coordinator.mkdir()
    return {
        "run_id": "operator-test",
        "benchmark_id": "priority-picker-fast-v1",
        "coordinator": {"worktree": str(coordinator)},
    }


def _result(returncode: int = 0, stdout: str = "", stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)



def test_operator_pane_preflight_reports_capacity_without_splitting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TMUX", "socket")
    monkeypatch.setenv("TMUX_PANE", "%1")
    monkeypatch.setattr(operator_panes.shutil, "which", lambda name: "/usr/bin/tmux")
    monkeypatch.setattr(operator_panes.tmux, "current_window_target", lambda: "bench:3")
    monkeypatch.setattr(operator_panes.tmux, "interactive_pane_count", lambda target: 6)
    monkeypatch.setattr(
        operator_panes.tmux,
        "split_window",
        lambda *args, **kwargs: pytest.fail("readiness must not mutate tmux layout"),
    )

    value = operator_pane_preflight()

    assert value == {
        "passed": True,
        "detail": "window=bench:3; occupied=6/8; available=2; required=2",
        "window": "bench:3",
        "occupied": 6,
        "available": 2,
        "required": 2,
        "maximum": 8,
    }


def test_operator_pane_preflight_rejects_insufficient_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TMUX", "socket")
    monkeypatch.setenv("TMUX_PANE", "%1")
    monkeypatch.setattr(operator_panes.shutil, "which", lambda name: "/usr/bin/tmux")
    monkeypatch.setattr(operator_panes.tmux, "current_window_target", lambda: "bench:3")
    monkeypatch.setattr(operator_panes.tmux, "interactive_pane_count", lambda target: 7)

    value = operator_pane_preflight()

    assert value["passed"] is False
    assert value["available"] == 1
    assert value["required"] == 2


def test_benchmark_requires_launch_from_inside_tmux(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(operator_panes.shutil, "which", lambda name: "/usr/bin/tmux")
    monkeypatch.delenv("TMUX", raising=False)
    monkeypatch.delenv("TMUX_PANE", raising=False)
    with pytest.raises(WorkflowError, match="launched from inside tmux"):
        ensure_operator_panes(_plan(tmp_path))


def test_benchmark_creates_exactly_two_bound_panes_in_launching_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path)
    monkeypatch.setenv("TMUX", "socket")
    monkeypatch.setenv("TMUX_PANE", "%1")
    monkeypatch.setattr(operator_panes.shutil, "which", lambda name: "/usr/bin/tmux")
    monkeypatch.setattr(operator_panes.tmux, "current_window_target", lambda: "bench:3")
    monkeypatch.setattr(operator_panes.tmux, "interactive_pane_count", lambda target: 1)
    created: list[tuple[str, str, str]] = []

    def split(target: str, workdir: str, runner: str, **_: object) -> str:
        pane = f"%{len(created) + 2}"
        created.append((target, workdir, runner))
        return pane

    bindings: list[tuple[str, str, str | None]] = []
    monkeypatch.setattr(operator_panes.tmux, "split_window", split)
    monkeypatch.setattr(
        operator_panes.tmux,
        "set_pane_binding",
        lambda pane, *, run_id, assignment_id=None: bindings.append((pane, run_id, assignment_id)),
    )
    monkeypatch.setattr(operator_panes, "run", lambda *args, **kwargs: _result())

    value = ensure_operator_panes(plan)

    assert len(created) == 2
    assert {item[0] for item in created} == {"bench:3"}
    assert value["launching_pane"] == "%1"
    assert value["panes"] == {"control_raw": "%2", "workflow_full": "%3"}
    assert bindings == [
        ("%2", "operator-test", "control_raw"),
        ("%3", "operator-test", "workflow_full"),
    ]


def test_benchmark_refuses_before_partial_split_when_two_panes_do_not_fit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TMUX", "socket")
    monkeypatch.setenv("TMUX_PANE", "%1")
    monkeypatch.setattr(operator_panes.shutil, "which", lambda name: "/usr/bin/tmux")
    monkeypatch.setattr(operator_panes.tmux, "current_window_target", lambda: "bench:3")
    monkeypatch.setattr(operator_panes.tmux, "interactive_pane_count", lambda target: 7)
    monkeypatch.setattr(
        operator_panes.tmux,
        "split_window",
        lambda *args, **kwargs: pytest.fail("split_window must not run after failed preflight"),
    )
    with pytest.raises(WorkflowError, match="requires two additional panes"):
        ensure_operator_panes(_plan(tmp_path))


def test_respawn_passes_one_shell_quoted_command_to_tmux(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed: list[list[str]] = []
    monkeypatch.setattr(
        operator_panes,
        "run",
        lambda argv, **kwargs: observed.append(list(argv)) or _result(),
    )
    monkeypatch.setattr(operator_panes.tmux, "set_pane_binding", lambda *args, **kwargs: None)
    monkeypatch.setattr(operator_panes.tmux, "set_pane_name", lambda *args, **kwargs: None)
    panes = {
        "run_id": "operator-test",
        "panes": {"control_raw": "%2", "workflow_full": "%3"},
    }
    respawn(
        panes,
        "control_raw",
        worktree=tmp_path,
        argv=[sys.executable, "script with spaces.py", "--value", "two words"],
        title="phase",
    )
    command = observed[0]
    assert command[:8] == ["tmux", "respawn-pane", "-k", "-t", "%2", "-c", str(tmp_path), command[7]]
    assert len(command) == 8
    assert "'script with spaces.py'" in command[-1]
    assert "'two words'" in command[-1]
    assert ["tmux", "set-option", "-p", "-t", "%2", "remain-on-exit", "on"] in observed


def test_tmux_runner_streams_output_and_writes_atomic_result(tmp_path: Path) -> None:
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("visible input", encoding="utf-8")
    stdout = tmp_path / "stdout.log"
    stderr = tmp_path / "stderr.log"
    result = tmp_path / "result.json"
    runner = REPO_ROOT / "src/agent_workflow/benchmarking/tmux_runner.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--cwd",
            str(tmp_path),
            "--prompt",
            str(prompt),
            "--stdout",
            str(stdout),
            "--stderr",
            str(stderr),
            "--result",
            str(result),
            "--timeout",
            "5",
            "--max-stdout",
            "4096",
            "--max-stderr",
            "4096",
            "--",
            sys.executable,
            "-c",
            "import sys; print(sys.stdin.read()); print('visible error', file=sys.stderr)",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    assert "visible input" in completed.stdout
    assert "visible error" in completed.stderr
    assert stdout.read_text(encoding="utf-8").strip() == "visible input"
    assert stderr.read_text(encoding="utf-8").strip() == "visible error"
    assert json.loads(result.read_text(encoding="utf-8"))["returncode"] == 0
    assert not list(tmp_path.glob("result.json.tmp-*"))


def test_fast_suite_synthetic_pair_completes_within_three_minute_wall_budget(tmp_path: Path) -> None:
    suite = REPO_ROOT / "benchmarks/specs/priority-picker-fast-v1"
    spec = json.loads((suite / "benchmark-spec.json").read_text(encoding="utf-8"))
    phase_timeout = float(spec["phases"][0]["timeout_seconds"])
    assert phase_timeout < 180

    def run_arm(arm: str) -> tuple[float, dict[str, object]]:
        worktree = tmp_path / arm
        shutil.copytree(suite / "fixture/starter", worktree)
        usage = tmp_path / "usage" / f"{arm}.json"
        usage.parent.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "AGENT_WORKFLOW_BENCHMARK_ARM": arm}
        started = time.monotonic()
        result = subprocess.run(
            [
                sys.executable,
                str(suite / "executors/synthetic_agent.py"),
                "--worktree",
                str(worktree),
                "--prompt",
                str(suite / "phases/01-build-verify.md"),
                "--phase",
                "build-verify",
                "--usage",
                str(usage),
            ],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=phase_timeout,
        )
        elapsed = time.monotonic() - started
        assert result.returncode == 0, result.stdout + result.stderr
        assert usage.is_file()
        assert "state" in result.stdout and "completed" in result.stdout
        return elapsed, json.loads(usage.read_text(encoding="utf-8"))

    pair_started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = {arm: pool.submit(run_arm, arm) for arm in ("control_raw", "workflow_full")}
        results = {arm: future.result() for arm, future in futures.items()}
    pair_elapsed = time.monotonic() - pair_started

    assert pair_elapsed < 180
    assert all(elapsed < phase_timeout for elapsed, _ in results.values())
    assert all(float(usage["provider_elapsed_seconds"]) < phase_timeout for _, usage in results.values())


def test_fast_suite_has_one_model_phase_bounded_below_three_minutes() -> None:
    spec = json.loads(
        (REPO_ROOT / "benchmarks/specs/priority-picker-fast-v1/benchmark-spec.json").read_text(
            encoding="utf-8"
        )
    )
    assert spec["schema"] == "agent-workflow/benchmark-spec/v2"
    assert len(spec["phases"]) == 1
    assert 0 < spec["phases"][0]["timeout_seconds"] < 180
    assert "live_review" in spec
    assert "{live_url}" in spec["visual"]["capture_argv"]


def test_fast_suite_reference_solution_reconciles_to_exactly_100_points(tmp_path: Path) -> None:
    suite = REPO_ROOT / "benchmarks/specs/priority-picker-fast-v1"
    spec = json.loads((suite / "benchmark-spec.json").read_text(encoding="utf-8"))
    contract = json.loads((suite / "scoring-contract.json").read_text(encoding="utf-8"))
    worktree = tmp_path / "worktree"
    stage_dir = tmp_path / "stage"
    results_dir = tmp_path / "results"
    shutil.copytree(suite / "fixture/starter", worktree)
    shutil.copytree(
        suite / "executors/solutions/workflow",
        worktree,
        dirs_exist_ok=True,
    )
    visual_checks = next(
        dimension["checks"]
        for dimension in contract["dimensions"]
        if dimension["id"] == "accessibility_ui"
    )
    visual_dir = stage_dir / "visual"
    visual_dir.mkdir(parents=True)
    (visual_dir / "assessment.json").write_text(
        json.dumps(
            {
                "checks": [
                    {
                        "id": item["id"],
                        "passed": True,
                        "detail": "synthetic golden calibration",
                    }
                    for item in visual_checks
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    total = 0.0
    for scorer in spec["machine_scoring"]["scorers"]:
        result_file = results_dir / f"{scorer['dimension']}.json"
        argv = [
            value.format(
                suite=suite,
                worktree=worktree,
                stage_dir=stage_dir,
                result_file=result_file,
                max_points=scorer["max_points"],
                scoring_contract=suite / spec["scoring_contract_path"],
            )
            for value in scorer["argv"]
        ]
        subprocess.run(argv, cwd=suite, check=True)
        result = json.loads(result_file.read_text(encoding="utf-8"))
        assert result["state"] == "pass", scorer["dimension"]
        assert result["earned_points"] == scorer["max_points"]
        assert all(check["passed"] for check in result["checks"])
        total += float(result["earned_points"])

    assert total == contract["total_points"] == 100


def test_all_builtin_benchmark_packages_match_authoring_sources() -> None:
    for source in sorted((REPO_ROOT / "benchmarks/specs").iterdir()):
        if not source.is_dir():
            continue
        packaged = REPO_ROOT / "src/agent_workflow/assets/benchmarks" / source.name
        assert packaged.is_dir()
        assert file_inventory(packaged) == file_inventory(source)


def test_close_operator_panes_only_kills_panes_still_owned_by_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path)
    runtime = Path(plan["coordinator"]["worktree"]) / ".agent-workflow-benchmark-runtime" / "operator-test"
    runtime.mkdir(parents=True)
    (runtime / "operator-panes.json").write_text(
        json.dumps(
            {
                "run_id": "operator-test",
                "panes": {"control_raw": "%2", "workflow_full": "%3"},
            }
        ),
        encoding="utf-8",
    )
    owned = SimpleNamespace(dead=False, run_id="operator-test", assignment_id="control_raw")
    rebound = SimpleNamespace(dead=False, run_id="another-run", assignment_id="workflow_full")
    monkeypatch.setattr(
        operator_panes.tmux,
        "pane_info",
        lambda pane: owned if pane == "%2" else rebound,
    )
    commands: list[list[str]] = []
    monkeypatch.setattr(
        operator_panes,
        "run",
        lambda argv, **kwargs: commands.append(list(argv)) or _result(),
    )

    result = operator_panes.close_operator_panes(plan)

    assert result == {
        "run_id": "operator-test",
        "closed": 1,
        "already_closed": 0,
        "preserved": 1,
    }
    assert commands == [["tmux", "kill-pane", "-t", "%2"]]
