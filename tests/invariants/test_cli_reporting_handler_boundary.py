from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_workflow.cli_handlers.reporting import (
    REPORTING_COMMANDS,
    handle_reporting_command,
)
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError


def _args(command: str, **values: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "command": command,
        "root": Path("runs"),
        "output": None,
        "pack": Path("pack"),
        "runs_root": None,
        "json": False,
    }
    base.update(values)
    return argparse.Namespace(**base)


def test_reporting_command_inventory_is_explicit() -> None:
    assert REPORTING_COMMANDS == {"assess-sealed-runs", "ledger"}


def test_assessment_preserves_output_file_and_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = defaults(tmp_path / "config.toml")
    expected = {"schema": "agent-workflow/sealed-run-assessment/v1", "runs": []}
    output = tmp_path / "assessment.json"
    with patch(
        "agent_workflow.cli_handlers.reporting.assess_exported_runs",
        return_value=expected,
    ) as assess:
        result, complete = handle_reporting_command(
            settings,
            _args("assess-sealed-runs", root=tmp_path / "runs", output=output),
        )
    assert result is None
    assert complete is True
    assess.assert_called_once_with(tmp_path / "runs")
    assert json.loads(output.read_text(encoding="utf-8")) == expected
    assert json.loads(capsys.readouterr().out) == expected


def test_ledger_stdout_preserves_human_renderer(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = defaults(tmp_path / "config.toml")
    value = {"rows": [{"ticket": "P0"}]}
    with (
        patch("agent_workflow.cli_handlers.reporting.build_ledger", return_value=value) as build,
        patch("agent_workflow.cli_handlers.reporting.render_ledger", return_value="ledger\n"),
    ):
        result, complete = handle_reporting_command(
            settings,
            _args("ledger", pack=tmp_path / "pack"),
        )
    assert result is None
    assert complete is True
    assert capsys.readouterr().out == "ledger\n"
    build.assert_called_once()


def test_ledger_file_mode_returns_existing_summary(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    value = {"rows": [{"ticket": "P0"}, {"ticket": "P1"}]}
    output = tmp_path / "reports" / "ledger.json"
    with patch("agent_workflow.cli_handlers.reporting.build_ledger", return_value=value):
        result, complete = handle_reporting_command(
            settings,
            _args(
                "ledger",
                pack=tmp_path / "pack",
                runs_root=tmp_path / "runs",
                output=output,
                json=True,
            ),
        )
    assert complete is False
    assert result == {"output": str(output), "row_count": 2}
    assert json.loads(output.read_text(encoding="utf-8")) == value


def test_unknown_reporting_command_fails_closed(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    with pytest.raises(WorkflowError, match="unsupported reporting command"):
        handle_reporting_command(settings, _args("unknown"))
