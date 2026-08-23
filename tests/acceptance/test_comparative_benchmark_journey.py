from __future__ import annotations

import concurrent.futures
import importlib.util
import json
import os
import shutil
import subprocess
import time
from dataclasses import replace
from pathlib import Path

import pytest

from agent_workflow.benchmarking.common import file_inventory
from agent_workflow.benchmarking.service import (
    cleanup_benchmark,
    create_fixture,
    create_plan,
    prepare_or_submit_review,
    resume_benchmark,
    run_benchmark,
    verify_benchmark,
)
from agent_workflow.config import defaults
from tests.conftest import InstalledProduct

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC = REPO_ROOT / "benchmarks/specs/priority-picker-v1/benchmark-spec.json"
EXECUTOR = REPO_ROOT / "benchmarks/specs/priority-picker-v1/executors/synthetic.json"
DIMENSIONS = (
    "visual_hierarchy",
    "interaction_clarity",
    "readability_density",
    "consistency",
    "responsive_behavior",
    "polish",
)


def _settings(tmp_path: Path):
    return replace(
        defaults(tmp_path / "config.toml"),
        worktree_root=tmp_path / "worktrees",
        state_root=tmp_path / "state",
    )


def test_installed_fast_benchmark_package_executes_scores_and_matches_authority(
    installed_product: InstalledProduct,
    tmp_path: Path,
) -> None:
    located = subprocess.run(
        [
            str(installed_product.python),
            "-c",
            (
                "from pathlib import Path; import agent_workflow; "
                "print(Path(agent_workflow.__file__).resolve().parent / "
                "'assets/benchmarks/priority-picker-fast-v1')"
            ),
        ],
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    suite = Path(located.stdout.strip())
    source_suite = REPO_ROOT / "benchmarks/specs/priority-picker-fast-v1"
    assert suite.is_dir()
    def authority_inventory(root: Path) -> list[dict[str, object]]:
        return [
            item for item in file_inventory(root)
            if "__pycache__/" not in item["path"] and not item["path"].endswith(".pyc")
        ]
    assert authority_inventory(suite) == authority_inventory(source_suite)

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


@pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None
    or shutil.which("chromium") is None
    or shutil.which("tmux") is None
    or not os.environ.get("TMUX")
    or not os.environ.get("TMUX_PANE"),
    reason="comparative journey requires Playwright/Chromium and an invoking tmux pane",
)
def test_paired_benchmark_runs_scores_blinds_reviews_and_consolidates(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    repo = tmp_path / "fixture-repo"
    fixture = create_fixture(SPEC, repo)
    original_revision = fixture["revision"]
    plan_result = create_plan(
        settings,
        spec=SPEC,
        executor=EXECUTOR,
        repo=repo,
        base_ref="HEAD",
        run_id="paired-acceptance",
        repetitions=1,
        worktree_root=tmp_path / "benchmark-worktrees",
        allow_dirty=False,
    )
    plan_path = Path(plan_result["run_plan"])
    automated = run_benchmark(settings, plan_path)
    assert automated["state"] == "awaiting_human_review"
    assert automated["automated_pipeline_wall_seconds"] > 0
    live_apps = automated["live_review"]["apps"]
    assert len(live_apps) == 2
    assert {item["arm"] for item in live_apps} == {"control_raw", "workflow_full"}
    assert len({item["port"] for item in live_apps}) == 2
    assert all(item["host"] == "0.0.0.0" for item in live_apps)
    assert all(item["url"].startswith("http://") for item in live_apps)
    assert all(item["local_url"].startswith("http://127.0.0.1:") for item in live_apps)

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    run_dir = Path(plan["coordinator"]["run_dir"])
    operator_panes = json.loads(
        (run_dir.parents[2] / ".agent-workflow-benchmark-runtime" / plan["run_id"] / "operator-panes.json").read_text(
            encoding="utf-8"
        )
    )
    for pane_id in operator_panes["panes"].values():
        observed = subprocess.run(
            ["tmux", "display-message", "-p", "-t", pane_id, "#{pane_id}"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
        assert observed == pane_id
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    pair = report["pairs"][0]
    assert pair["arms"]["control_raw"]["machine_score"] == 88.0
    assert pair["arms"]["workflow_full"]["machine_score"] == 96.0
    assert pair["arms"]["control_raw"]["composite_score"] is None
    assert pair["arms"]["workflow_full"]["composite_score"] is None
    assert pair["arms"]["control_raw"]["usage"]["provider_total_tokens"] == 4380
    assert pair["arms"]["workflow_full"]["usage"]["provider_total_tokens"] == 6350
    assert pair["arms"]["control_raw"]["usage"]["provider_billed_cost"] == 0.01308
    assert pair["arms"]["workflow_full"]["usage"]["provider_billed_cost"] == 0.018964
    assert report["timing"]["automated_pipeline_wall_seconds"] > 0
    assert pair["timing"]["pair_wall_seconds"] > 0
    assert pair["arms"]["control_raw"]["timing"]["visual_capture_seconds"] > 0
    assert pair["arms"]["workflow_full"]["timing"]["machine_verification_seconds"] > 0
    assert pair["arms"]["control_raw"]["measured_total_seconds"] > pair["arms"]["control_raw"]["wall_seconds"]
    assert len(pair["arms"]["control_raw"]["phase_metrics"]) == 3

    events_before_resume = (run_dir / "events.jsonl").read_text(encoding="utf-8")
    resumed = resume_benchmark(settings, plan_path)
    assert resumed["existing"] is True
    assert resumed["automated_pipeline_wall_seconds"] == automated["automated_pipeline_wall_seconds"]
    assert (run_dir / "events.jsonl").read_text(encoding="utf-8") == events_before_resume

    events = [json.loads(line) for line in events_before_resume.splitlines()]
    sequences = [event["sequence"] for event in events]
    assert sequences == list(range(1, len(sequences) + 1))
    pair_state = json.loads(
        (run_dir / "pair-state/standard-backlog/r01/pair.json").read_text(encoding="utf-8")
    )
    assert pair_state["pair_start_skew_seconds"] <= 0.25

    assignment_result = prepare_or_submit_review(
        settings, plan_path, reviewer="acceptance-reviewer", input_path=None
    )
    assignment_path = Path(assignment_result["assignment"])
    assignment_text = assignment_path.read_text(encoding="utf-8")
    assert "control_raw" not in assignment_text
    assert "workflow_full" not in assignment_text
    assignment = json.loads(assignment_text)
    assert all(
        "/left/" in path or "/right/" in path
        for item in assignment["pairs"]
        for label in item["labels"].values()
        for path in label["evidence"]
    )

    template_path = Path(assignment_result["review_template"])
    completed = json.loads(template_path.read_text(encoding="utf-8"))
    private_mapping = json.loads(
        (run_dir / "human-review/.blinding/acceptance-reviewer.json").read_text(
            encoding="utf-8"
        )
    )["mappings"][0]["labels"]
    for item in completed["pairs"]:
        for label in ("left", "right"):
            rating = 5 if private_mapping[label] == "workflow_full" else 3
            item["scores"][label] = {dimension: rating for dimension in DIMENSIONS}
        item["preference"] = next(
            label for label, arm in private_mapping.items() if arm == "workflow_full"
        )
        item["confidence"] = 5
        item["blocking_defects"] = []
        item["comments"] = ["Synthetic acceptance review."]
    completed.update(
        submitted_at="2026-08-01T20:00:00+00:00",
        review_started_at="2026-08-01T19:59:00+00:00",
        review_completed_at="2026-08-01T20:00:00+00:00",
        active_review_seconds=60,
    )
    review_path = tmp_path / "completed-review.json"
    review_path.write_text(json.dumps(completed, indent=2) + "\n", encoding="utf-8")
    submitted = prepare_or_submit_review(
        settings,
        plan_path,
        reviewer="acceptance-reviewer",
        input_path=review_path,
    )
    assert submitted["report_state"] == "complete_no_winner_policy"
    report = json.loads((run_dir / "report.json").read_text(encoding="utf-8"))
    pair = report["pairs"][0]
    assert pair["arms"]["control_raw"]["composite_score"] == 76.6
    assert pair["arms"]["workflow_full"]["composite_score"] == 97.2
    assert report["winner"] is None
    assert report["timing"]["human_active_review_seconds"] == 60.0

    verified = verify_benchmark(settings, plan_path)
    assert verified["valid"] is True
    cleanup = cleanup_benchmark(settings, plan_path, remove_worktrees=True, stop_live_apps=True)
    assert all(item["worktree_removed"] for item in cleanup["removed"])
    assert Path(cleanup["coordinator_preserved"]).is_dir()
    assert verify_benchmark(settings, plan_path)["valid"] is True

    source_revision = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    source_status = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert source_revision == original_revision
    assert source_status == ""
