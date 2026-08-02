from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.session_artifacts import (
    _create_handoff_dir,
    _discover_prompt_pack_root,
    _link_worktree_state,
    _pack_id,
    _write_runner,
)


def _git_repo(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def test_handoff_creation_is_excluded_and_collision_safe(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _git_repo(repo)
    handoff = _create_handoff_dir(repo, "session-1")
    assert handoff == (repo / ".agent-workflow-handoff" / "session-1").resolve()
    exclude = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--git-path", "info/exclude"],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    exclude_path = Path(exclude)
    if not exclude_path.is_absolute():
        exclude_path = repo / exclude_path
    assert ".agent-workflow-handoff/" in exclude_path.read_text(encoding="utf-8")
    with pytest.raises(WorkflowError, match="already exists"):
        _create_handoff_dir(repo, "session-1")


def test_worktree_state_link_is_idempotent_but_rejects_retargeting(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _git_repo(repo)
    state = tmp_path / "state-1"
    state.mkdir()
    _link_worktree_state(repo, "session-1", state)
    _link_worktree_state(repo, "session-1", state)
    assert (repo / ".delegations" / "session-1").resolve() == state.resolve()
    other = tmp_path / "state-2"
    other.mkdir()
    with pytest.raises(WorkflowError, match="already exists"):
        _link_worktree_state(repo, "session-1", other)


def test_runner_generation_preserves_bound_environment_and_bash_syntax(tmp_path: Path) -> None:
    state = tmp_path / "state"
    workdir = tmp_path / "work"
    handoff = workdir / ".agent-workflow-handoff" / "session-1"
    state.mkdir()
    workdir.mkdir()
    handoff.mkdir(parents=True)
    (state / "prompt.md").write_text("Do work.\n", encoding="utf-8")
    runner = _write_runner(
        state,
        workdir,
        ["python", "-c", "print('ok')"],
        python_executable="python",
        session_id="session-1",
        prompt_source=state / "prompt.md",
        handoff_dir=handoff,
        completion_template_path=handoff / "completion-template.json",
        command_artifacts={
            "catalog_path": "command-catalog.json",
            "card_path": "command-card.md",
            "cli_invocation": ["agent-workflow"],
        },
        interactive=True,
        close_tmux_on_exit=True,
    )
    text = runner.read_text(encoding="utf-8")
    assert "AGENT_WORKFLOW_SESSION_ID=session-1" in text
    assert "AGENT_WORKFLOW_CONTROL_BRIDGE=" in text
    assert "AGENT_WORKFLOW_TMUX_SESSION=session-1" in text
    assert os.access(runner, os.X_OK)
    subprocess.run(["bash", "-n", str(runner)], check=True)


def test_prompt_pack_discovery_and_identity_are_stable(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    prompt = pack / "phase-0" / "prompt.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("prompt\n", encoding="utf-8")
    (pack / "pack.yaml").write_text('pack_id: "fixture-pack"\n', encoding="utf-8")
    assert _discover_prompt_pack_root(prompt) == pack
    assert _pack_id(pack) == "fixture-pack"
