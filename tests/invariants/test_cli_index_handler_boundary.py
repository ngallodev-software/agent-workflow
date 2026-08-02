from __future__ import annotations

import json
from argparse import Namespace
from dataclasses import replace
from pathlib import Path

from agent_workflow.cli_handlers.index import handle_index_command
from agent_workflow.config import Settings, defaults


def _settings(tmp_path: Path) -> Settings:
    config = tmp_path / "config.toml"
    state_root = tmp_path / "state"
    worktree_root = tmp_path / "worktrees"
    config.write_text(
        "schema_version = 1\n\n"
        "[paths]\n"
        f"state_root = {json.dumps(str(state_root))}\n"
        f"worktree_root = {json.dumps(str(worktree_root))}\n",
        encoding="utf-8",
    )
    return replace(
        defaults(config),
        state_root=state_root,
        worktree_root=worktree_root,
    )


def test_index_status_handler_returns_data_for_shared_cli_rendering(tmp_path: Path) -> None:
    data, output_complete = handle_index_command(
        _settings(tmp_path),
        Namespace(index_command="status"),
    )

    assert output_complete is False
    assert data["schema"] == "agent-workflow/index-status/v1"


def test_index_query_handler_owns_domain_specific_terminal_rendering(
    tmp_path: Path,
    capsys,
) -> None:
    settings = _settings(tmp_path)
    handle_index_command(
        settings,
        Namespace(index_command="rebuild", session_id=None, active_only=False),
    )
    data, output_complete = handle_index_command(
        settings,
        Namespace(
            index_command="query",
            kind="runs",
            session_id=None,
            state=None,
            category=None,
            executor=None,
            model=None,
            pack_id=None,
            limit=10,
            json=False,
        ),
    )

    assert data is None
    assert output_complete is True
    output = capsys.readouterr().out
    assert output.startswith("index: current")
    assert "No records." in output
