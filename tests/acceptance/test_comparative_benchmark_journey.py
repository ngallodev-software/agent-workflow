from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


from agent_workflow.benchmarking.common import file_inventory
from tests.conftest import InstalledProduct

def test_installed_fast_benchmark_package_executes_scores_and_matches_authority(
    installed_product: InstalledProduct,
    tmp_path: Path,
) -> None:
    suite = tmp_path / "priority-picker-fast-v1"
    exported = installed_product.json(
        "benchmark",
        "suite-export",
        suite,
        "--benchmark-id",
        "priority-picker-fast-v1",
        timeout=30,
    )
    assert Path(exported["destination"]) == suite
    assert suite.is_dir()
    assert not (suite / "suite-layout.json").exists()
    assert len(file_inventory(suite)) == 51

    spec = json.loads((suite / "benchmark-spec.json").read_text(encoding="utf-8"))
    contract = json.loads((suite / "scoring-contract.json").read_text(encoding="utf-8"))
    assert spec["schema"] == "agent-workflow/benchmark-spec/v2"
    assert len(spec["phases"]) == 1
    phase_timeout = float(spec["phases"][0]["timeout_seconds"])
    assert 0 < phase_timeout < 180
    assert "live_review" in spec
    assert "{live_url}" in spec["visual"]["capture_argv"]

    def run_arm(arm: str) -> tuple[float, dict[str, object]]:
        worktree = tmp_path / arm
        shutil.copytree(suite / "fixture/starter", worktree)
        usage = tmp_path / "usage" / f"{arm}.json"
        usage.parent.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, "AGENT_WORKFLOW_BENCHMARK_ARM": arm}
        started = time.monotonic()
        result = subprocess.run(
            [
                str(installed_product.python),
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
            cwd=suite,
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

    worktree = tmp_path / "golden-worktree"
    stage_dir = tmp_path / "golden-stage"
    results_dir = tmp_path / "golden-results"
    shutil.copytree(suite / "fixture/starter", worktree)
    shutil.copytree(suite / "executors/solutions/workflow", worktree, dirs_exist_ok=True)
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
                    {"id": item["id"], "passed": True, "detail": "installed golden calibration"}
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
        if argv and Path(argv[0]).name.startswith("python"):
            argv[0] = str(installed_product.python)
        subprocess.run(argv, cwd=suite, check=True, timeout=30)
        score = json.loads(result_file.read_text(encoding="utf-8"))
        assert score["state"] == "pass", scorer["dimension"]
        assert score["earned_points"] == scorer["max_points"]
        assert all(check["passed"] for check in score["checks"])
        total += float(score["earned_points"])
    assert total == contract["total_points"] == 100
