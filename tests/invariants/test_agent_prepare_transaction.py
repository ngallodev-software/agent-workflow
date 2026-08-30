from pathlib import Path

import pytest

from agent_workflow import agent_runs
from agent_workflow.agent_identity import claim_agent_name
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError


def _settings(tmp_path: Path):
    settings = defaults(tmp_path / "config.toml")
    object.__setattr__(settings, "state_root", tmp_path / "state")
    return settings


def test_prepare_failure_removes_created_artifacts_and_lease(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    workdir = tmp_path / "repo"
    workdir.mkdir()

    def fail_after_side_effects(settings, *, agent_run_id, workdir, **kwargs):
        run = agent_runs.run_dir(settings, agent_run_id)
        run.mkdir(parents=True)
        handoff = workdir / ".agent-workflow-handoff" / agent_run_id
        handoff.mkdir(parents=True)
        claim_agent_name(
            settings, agent_name="worker", agent_run_id=agent_run_id, interactive=False
        )
        raise WorkflowError("preparation failed")

    monkeypatch.setattr(agent_runs, "_prepare", fail_after_side_effects)

    with pytest.raises(WorkflowError, match="preparation failed"):
        agent_runs.prepare(
            settings,
            agent_run_id="run-1",
            workdir=workdir,
            prompt_path=tmp_path / "prompt.md",
            agent_name="worker",
        )

    assert not agent_runs.run_dir(settings, "run-1").exists()
    assert not (workdir / ".agent-workflow-handoff" / "run-1").exists()
    assert not (settings.state_root / "agent-name-leases" / "worker.json").exists()


def test_name_collision_rolls_back_artifacts(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    workdir = tmp_path / "repo"
    workdir.mkdir()
    claim_agent_name(
        settings, agent_name="worker", agent_run_id="other-run", interactive=False
    )

    def collide(settings, *, agent_run_id, workdir, **kwargs):
        run = agent_runs.run_dir(settings, agent_run_id)
        run.mkdir(parents=True)
        (workdir / ".agent-workflow-handoff" / agent_run_id).mkdir(parents=True)
        claim_agent_name(
            settings, agent_name="worker", agent_run_id=agent_run_id, interactive=False
        )

    monkeypatch.setattr(agent_runs, "_prepare", collide)

    with pytest.raises(WorkflowError, match="already active"):
        agent_runs.prepare(
            settings,
            agent_run_id="run-1",
            workdir=workdir,
            prompt_path=tmp_path / "prompt.md",
            agent_name="worker",
        )

    assert not agent_runs.run_dir(settings, "run-1").exists()
    assert not (workdir / ".agent-workflow-handoff" / "run-1").exists()
    assert (settings.state_root / "agent-name-leases" / "worker.json").exists()


def test_intentional_preflight_evidence_is_preserved(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    workdir = tmp_path / "repo"
    workdir.mkdir()

    def preflight_failure(settings, *, agent_run_id, **kwargs):
        run = agent_runs.run_dir(settings, agent_run_id)
        run.mkdir(parents=True)
        (run / "preflight.json").write_text("{}", encoding="utf-8")
        raise WorkflowError("preflight failed")

    monkeypatch.setattr(agent_runs, "_prepare", preflight_failure)

    with pytest.raises(WorkflowError, match="preflight failed"):
        agent_runs.prepare(
            settings,
            agent_run_id="run-1",
            workdir=workdir,
            prompt_path=tmp_path / "prompt.md",
        )

    assert (agent_runs.run_dir(settings, "run-1") / "preflight.json").is_file()
