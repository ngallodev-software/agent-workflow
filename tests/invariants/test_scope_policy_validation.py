from __future__ import annotations

from pathlib import Path

import pytest

from agent_workflow.errors import WorkflowError
from agent_workflow.eval.scope import ScopePolicy, validate_scope_policy


def test_scope_policy_rejects_existing_directory_in_writable_paths(
    tmp_path: Path,
) -> None:
    (tmp_path / "events").mkdir()
    policy = ScopePolicy(
        authorized_root=tmp_path,
        writable_paths=("events",),
    )

    with pytest.raises(WorkflowError, match="use writable_trees"):
        validate_scope_policy(policy)


def test_scope_policy_allows_directory_in_writable_trees(tmp_path: Path) -> None:
    (tmp_path / "events").mkdir()
    policy = ScopePolicy(
        authorized_root=tmp_path,
        writable_trees=("events",),
    )

    validate_scope_policy(policy)


def test_scope_policy_allows_exact_file_in_writable_paths(tmp_path: Path) -> None:
    target = tmp_path / "event.md"
    target.write_text("before\n", encoding="utf-8")
    policy = ScopePolicy(
        authorized_root=tmp_path,
        writable_paths=("event.md",),
    )

    validate_scope_policy(policy)
