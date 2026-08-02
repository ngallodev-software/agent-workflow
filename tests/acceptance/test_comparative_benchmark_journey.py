from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

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


@pytest.mark.skipif(
    importlib.util.find_spec("playwright") is None or shutil.which("chromium") is None,
    reason="comparative visual journey requires the pinned Playwright/Chromium development runtime",
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

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    run_dir = Path(plan["coordinator"]["run_dir"])
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
    cleanup = cleanup_benchmark(settings, plan_path, remove_worktrees=True)
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
