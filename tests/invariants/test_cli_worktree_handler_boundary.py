from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import agent_workflow.cli_handlers.worktree as handler
from agent_workflow.config import defaults


def test_worktree_create_handler_forwards_exact_arguments(tmp_path: Path, monkeypatch) -> None:
    settings = defaults(tmp_path / "config.toml")
    captured = {}

    def fake_create(received_settings, **kwargs):
        captured["settings"] = received_settings
        captured.update(kwargs)
        return {"created": True}

    monkeypatch.setattr(handler, "create_worktree", fake_create)
    args = Namespace(
        worktree_command="create",
        repo=tmp_path / "repo",
        ticket_id="TICKET-1",
        base_ref="main",
        dest=tmp_path / "dest",
        branch="feature/ticket-1",
        allow_dirty=True,
    )

    assert handler.handle_worktree_command(settings, args) == {"created": True}
    assert captured == {
        "settings": settings,
        "repo": tmp_path / "repo",
        "ticket_id": "TICKET-1",
        "base_ref": "main",
        "destination": tmp_path / "dest",
        "branch": "feature/ticket-1",
        "allow_dirty": True,
    }


def test_worktree_remove_and_list_handlers_preserve_public_calls(
    tmp_path: Path, monkeypatch
) -> None:
    settings = defaults(tmp_path / "config.toml")
    calls = []

    def fake_remove(repo, worktree, *, force, delete_branch):
        calls.append(("remove", repo, worktree, force, delete_branch))
        return {"removed": str(worktree)}

    def fake_list(repo):
        calls.append(("list", repo))
        return [{"worktree": str(repo)}]

    monkeypatch.setattr(handler, "remove_worktree", fake_remove)
    monkeypatch.setattr(handler, "list_worktrees", fake_list)

    remove_args = Namespace(
        worktree_command="remove",
        repo=tmp_path / "repo",
        worktree=tmp_path / "tree",
        force=True,
        delete_branch=True,
    )
    list_args = Namespace(worktree_command="list", repo=tmp_path / "repo")

    assert handler.handle_worktree_command(settings, remove_args) == {
        "removed": str(tmp_path / "tree")
    }
    assert handler.handle_worktree_command(settings, list_args) == [
        {"worktree": str(tmp_path / "repo")}
    ]
    assert calls == [
        ("remove", tmp_path / "repo", tmp_path / "tree", True, True),
        ("list", tmp_path / "repo"),
    ]
