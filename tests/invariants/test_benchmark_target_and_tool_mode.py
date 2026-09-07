from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from agent_workflow.benchmarking.planning import create_run_plan, materialize_fixture
from agent_workflow.benchmarking.service import export_builtin_suite
from agent_workflow.benchmarking.targets import prepare_target
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError


def _git(path: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(path), *args], check=True, text=True, capture_output=True).stdout.strip()


def test_target_prepare_clones_exact_manifest_commit_and_tree(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(remote), str(seed)], check=True, capture_output=True)
    _git(seed, "config", "user.email", "benchmark@example.invalid")
    _git(seed, "config", "user.name", "Benchmark")
    (seed / "fixture.txt").write_text("pinned\n", encoding="utf-8")
    _git(seed, "add", "fixture.txt")
    _git(seed, "commit", "-m", "fixture")
    _git(seed, "push", "origin", "HEAD")
    commit, tree = _git(seed, "rev-parse", "HEAD"), _git(seed, "rev-parse", "HEAD^{tree}")
    manifest = tmp_path / "target.json"
    manifest.write_text(json.dumps({"schema": "agent-workflow/benchmark-target/v1", "target_id": "fixture", "remote": remote.as_uri(), "commit": commit, "tree": tree}), encoding="utf-8")
    result = prepare_target(manifest, tmp_path / "checkout")
    assert result["commit"] == commit
    assert result["tree"] == tree
    assert _git(Path(result["repository"]), "rev-parse", "HEAD") == commit
    manifest.write_text(json.dumps({**json.loads(manifest.read_text()), "tree": "0" * 40}), encoding="utf-8")
    with pytest.raises(WorkflowError, match="tree mismatch"):
        prepare_target(manifest, tmp_path / "checkout")


def test_plan_seals_one_codebase_memory_mode_for_both_arms(tmp_path: Path) -> None:
    exported = export_builtin_suite(tmp_path / "suite", benchmark_id="priority-picker-v1")
    suite = Path(exported["destination"])
    fixture = materialize_fixture(suite / "benchmark-spec.json", tmp_path / "fixture")
    settings = replace(defaults(tmp_path / "config.toml"), worktree_root=tmp_path / "worktrees", state_root=tmp_path / "state")
    result = create_run_plan(settings, spec_path=suite / "benchmark-spec.json", executor_path=suite / "executors" / "synthetic.json", repo=Path(fixture["destination"]), base_ref="HEAD", codebase_memory_mode="cli")
    plan = json.loads(Path(result["run_plan"]).read_text(encoding="utf-8"))
    assert plan["codebase_memory_mode"] == "cli"
    assert plan["environment"]["codebase_memory_mode"] == "cli"
    for arm in plan["pairs"][0]["arms"].values():
        prompt = Path(arm["prompts"][0]["path"]).read_text(encoding="utf-8")
        assert "Use only `cli`" in prompt
