from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

from agent_workflow.cli_handlers.supervisor import handle_supervisor_command
from agent_workflow.config import defaults


def _args(command: str) -> argparse.Namespace:
    return argparse.Namespace(
        supervisor_command=command,
        capture_interactive=True,
        capture_lines=37,
        probe_stalled=True,
        interrupt_stalled=False,
        restart_orphaned=True,
        max_remediation_attempts=4,
        sync_index=True,
        session=["session-1", "session-2"],
        interval_seconds=2.5,
        max_cycles=3,
    )


def test_once_preserves_all_policy_overrides(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    sentinel_options = object()
    expected = {"schema": "agent-workflow/supervisor-report/v1"}
    with (
        patch(
            "agent_workflow.cli_handlers.supervisor.SupervisorOptions.from_settings",
            return_value=sentinel_options,
        ) as build,
        patch(
            "agent_workflow.cli_handlers.supervisor.supervise_once",
            return_value=expected,
        ) as once,
    ):
        result = handle_supervisor_command(settings, _args("once"))
    assert result is expected
    build.assert_called_once_with(
        settings,
        capture_interactive=True,
        capture_lines=37,
        probe_stalled=True,
        interrupt_stalled=False,
        restart_orphaned=True,
        max_remediation_attempts=4,
        sync_index_enabled=True,
    )
    once.assert_called_once_with(
        settings,
        session_ids=["session-1", "session-2"],
        options=sentinel_options,
    )


def test_loop_wraps_reports_without_transforming_them(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    reports = [{"cycle": 1}, {"cycle": 2}]
    with (
        patch(
            "agent_workflow.cli_handlers.supervisor.SupervisorOptions.from_settings",
            return_value="options",
        ),
        patch(
            "agent_workflow.cli_handlers.supervisor.supervise_loop",
            return_value=reports,
        ) as loop,
    ):
        result = handle_supervisor_command(settings, _args("loop"))
    assert result == {
        "schema": "agent-workflow/supervisor-loop-report/v1",
        "cycle_count": 2,
        "reports": reports,
    }
    loop.assert_called_once_with(
        settings,
        interval_seconds=2.5,
        max_cycles=3,
        session_ids=["session-1", "session-2"],
        options="options",
    )
