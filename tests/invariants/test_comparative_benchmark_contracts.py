from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_workflow.benchmarking.metrics import aggregate_usage, empty_usage
from agent_workflow.benchmarking.common import file_inventory, tree_sha256
from agent_workflow.benchmarking.planning import create_run_plan, materialize_fixture
from agent_workflow.benchmarking.review import (
    _require_exact_pair_ids,
    _unblind_blocking_defects,
)
from agent_workflow.benchmarking.scoring import _observed_machine_score
from agent_workflow.benchmarking.service import cleanup_benchmark, export_builtin_suite
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError

def _suite(tmp_path: Path) -> Path:
    destination = tmp_path / "priority-picker-v1"
    export_builtin_suite(destination, benchmark_id="priority-picker-v1")
    return destination


def _settings(tmp_path: Path):
    return replace(
        defaults(tmp_path / "config.toml"),
        worktree_root=tmp_path / "worktrees",
        state_root=tmp_path / "state",
    )


def test_planned_pair_preserves_task_identity_and_declares_treatment(tmp_path: Path) -> None:
    suite = _suite(tmp_path)
    spec = suite / "benchmark-spec.json"
    executor = suite / "executors" / "synthetic.json"
    repo = tmp_path / "fixture"
    materialize_fixture(spec, repo)
    result = create_run_plan(
        _settings(tmp_path),
        spec_path=spec,
        executor_path=executor,
        repo=repo,
        base_ref="HEAD",
        run_id="contract-pair",
        repetitions=1,
        worktree_root=tmp_path / "isolated",
        allow_dirty=False,
    )
    plan = json.loads(Path(result["run_plan"]).read_text(encoding="utf-8"))
    pair = plan["pairs"][0]
    control = pair["arms"]["control_raw"]
    workflow = pair["arms"]["workflow_full"]

    assert control["task_prompt_sha256"] == workflow["task_prompt_sha256"]
    assert control["task_prompt_sha256"] == pair["task_prompt_sha256"]
    assert control["arm_wrapper_sha256"] != workflow["arm_wrapper_sha256"]
    assert control["constraint_profile_sha256"] != workflow["constraint_profile_sha256"]
    assert {control["slot"], workflow["slot"]} == {"A", "B"}
    assert Path(plan["coordinator"]["run_dir"]).is_relative_to(
        Path(plan["coordinator"]["worktree"])
    )
    for arm in (control, workflow):
        assert Path(arm["stage_dir"]).is_relative_to(Path(arm["worktree"]))
        assert all(Path(item["path"]).is_relative_to(Path(arm["worktree"])) for item in arm["prompts"])


def test_planner_rejects_noncanonical_fixture_and_cleans_created_branch(tmp_path: Path) -> None:
    suite = _suite(tmp_path)
    spec = suite / "benchmark-spec.json"
    executor = suite / "executors" / "synthetic.json"
    repo = tmp_path / "fixture"
    materialize_fixture(spec, repo)
    (repo / "README.md").write_text("mutated fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "mutate"], check=True)

    with pytest.raises(WorkflowError, match="does not match the frozen fixture"):
        create_run_plan(
            _settings(tmp_path),
            spec_path=spec,
            executor_path=executor,
            repo=repo,
            base_ref="HEAD",
            run_id="fixture-mismatch",
            repetitions=1,
            worktree_root=tmp_path / "isolated",
            allow_dirty=False,
        )
    branches = subprocess.run(
        ["git", "-C", str(repo), "branch", "--format=%(refname:short)"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()
    assert not any(branch.startswith("benchmark/fixture-mismatch/") for branch in branches)


def test_usage_unknowns_remain_null_instead_of_becoming_zero() -> None:
    first = empty_usage(currency="USD", price_catalog_id="catalog-v1")
    second = dict(first)
    second.update(input_tokens=10, output_tokens=3, provider_total_tokens=13)
    aggregate = aggregate_usage([second])
    assert aggregate["input_tokens"] == 10
    assert aggregate["provider_billed_cost"] is None
    assert aggregate["complete"] is False


def test_observed_machine_score_survives_invalid_eligibility() -> None:
    components = [{"earned_points": 37.5}, {"earned_points": 12.25}]
    assert _observed_machine_score(components) == 49.75


def test_cleanup_retains_arm_worktrees_by_default(tmp_path: Path) -> None:
    run_dir = tmp_path / "coordinator" / "benchmarks" / "runs" / "run-1"
    coordinator = run_dir.parents[2]
    coordinator.mkdir(parents=True)
    arms = {}
    for name in ("control_raw", "workflow_full"):
        worktree = tmp_path / name
        worktree.mkdir()
        arms[name] = {"worktree": str(worktree), "branch": f"benchmark/run-1/{name}"}
    plan = {
        "run_id": "run-1",
        "coordinator": {"run_dir": str(run_dir), "worktree": str(coordinator)},
        "source": {"repository": str(tmp_path / "source")},
        "pairs": [{"pair_id": "pair-1", "attempts": [{"attempt": 1, "arms": arms}]}],
    }
    run_dir.mkdir(parents=True)
    plan_path = run_dir / "run-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    with (
        patch("agent_workflow.benchmarking.service.verify_consolidated_run", return_value={"valid": False}),
        patch("agent_workflow.benchmarking.service.write_manifest"),
    ):
        result = cleanup_benchmark(_settings(tmp_path), plan_path)
    assert result["remove_worktrees"] is False
    assert result["removed"] == []
    assert len(result["preserved"]) == 2
    assert all(item["worktree_present"] for item in result["preserved"])


@pytest.mark.parametrize(
    ("benchmark_id", "expected_files", "expected_tree_sha256"),
    [
        ("priority-picker-v1", 50, "a4e4be0214650c283327fe903a241dca1cdebed85eb914f4097c84fa9a3e85c3"),
        ("priority-picker-v2", 51, "28d9274d1d7bd3b3744bcf0c596b2cbd19a09b3ae02358ff3864bf3e26f78ab5"),
        ("priority-picker-fast-v1", 51, "219b41fdde09d995773da92ce6f584021347e12721a477d328da96bb7745bc90"),
    ],
)
def test_packaged_suite_exports_a_self_contained_frozen_suite(
    tmp_path: Path,
    benchmark_id: str,
    expected_files: int,
    expected_tree_sha256: str,
) -> None:
    destination = tmp_path / benchmark_id
    result = export_builtin_suite(destination, benchmark_id=benchmark_id)
    assert Path(result["spec"]).is_file()
    assert Path(result["synthetic_executor"]).is_file()
    assert len(file_inventory(destination)) == expected_files
    assert tree_sha256(destination) == expected_tree_sha256
    assert not (destination / "suite-layout.json").exists()
    assert (destination / "fixture" / "starter" / "priority_picker" / "server.py").is_file()
    assert (destination / "evaluation" / "evaluate.py").is_file()
    assert not any(path.name == "__pycache__" for path in destination.rglob("__pycache__"))
    assert not any(path.suffix in {".pyc", ".pyo"} for path in destination.rglob("*"))


def test_blinded_review_defects_are_mapped_without_treatment_leakage() -> None:
    labels = {"left": "workflow_full", "right": "control_raw"}
    defects = _unblind_blocking_defects(
        [
            {"label": "left", "description": "Broken mobile layout"},
            {"label": "both", "description": "Unreadable labels"},
        ],
        labels,
        "pair-1",
    )
    assert defects == [
        {"arm": "workflow_full", "description": "Broken mobile layout"},
        {"arm": "control_raw", "description": "Unreadable labels"},
        {"arm": "workflow_full", "description": "Unreadable labels"},
    ]
    with pytest.raises(WorkflowError, match="unique pair IDs"):
        _require_exact_pair_ids(
            [{"pair_id": "pair-1"}, {"pair_id": "pair-1"}],
            {"pair-1", "pair-2"},
        )
