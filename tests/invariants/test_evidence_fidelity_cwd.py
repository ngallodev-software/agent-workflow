from __future__ import annotations

from pathlib import Path

from agent_workflow.eval.scoring import _command_identity


def test_command_identity_treats_relative_and_absolute_worktree_cwd_as_equivalent(
    tmp_path: Path,
) -> None:
    worktree = (tmp_path / "repo").resolve()
    worktree.mkdir()

    collected = {"argv": ["true"], "cwd": ".", "exit_code": 0}
    completion = {"argv": ["true"], "cwd": str(worktree), "exit_code": 0}

    assert _command_identity(collected, worktree=worktree) == _command_identity(
        completion,
        worktree=worktree,
    )


def test_command_identity_preserves_distinct_subdirectories(tmp_path: Path) -> None:
    worktree = (tmp_path / "repo").resolve()
    (worktree / "a").mkdir(parents=True)
    (worktree / "b").mkdir()

    first = {"argv": ["true"], "cwd": "a", "exit_code": 0}
    second = {"argv": ["true"], "cwd": "b", "exit_code": 0}

    assert _command_identity(first, worktree=worktree) != _command_identity(
        second,
        worktree=worktree,
    )
