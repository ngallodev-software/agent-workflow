from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from agent_workflow.cli_handlers.core import CORE_COMMANDS, handle_core_command
from agent_workflow.cli_parser import build_parser
from agent_workflow.config import defaults
from agent_workflow.errors import WorkflowError
from agent_workflow.plugins import EMPTY_PLUGIN_REGISTRY


def _args(command: str, **values: object) -> argparse.Namespace:
    base: dict[str, object] = {
        "command": command,
        "json": False,
        "no_plugins": False,
        "format": None,
        "role": None,
        "shell": "bash",
    }
    base.update(values)
    return argparse.Namespace(**base)


def test_core_command_inventory_is_explicit() -> None:
    assert CORE_COMMANDS == {"commands", "plugins", "doctor", "completion", "config"}


def test_commands_preserves_parser_catalog_and_output_modes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = defaults(tmp_path / "config.toml")
    parser = build_parser(EMPTY_PLUGIN_REGISTRY)
    _, complete = handle_core_command(
        settings,
        _args("commands", json=True, format="json", role="implementation"),
        parser=parser,
        plugin_registry=EMPTY_PLUGIN_REGISTRY,
    )
    assert complete is True
    assert '"schema": "agent-workflow/command-catalog/v1"' in capsys.readouterr().out


def test_plugins_and_config_return_data_for_shared_renderer(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    parser = build_parser(EMPTY_PLUGIN_REGISTRY)
    plugins, complete = handle_core_command(
        settings,
        _args("plugins", no_plugins=True),
        parser=parser,
        plugin_registry=EMPTY_PLUGIN_REGISTRY,
    )
    assert complete is False
    assert plugins == {"configured_enabled": [], "suppressed": True, "plugins": []}

    config, complete = handle_core_command(
        settings,
        _args("config"),
        parser=parser,
        plugin_registry=EMPTY_PLUGIN_REGISTRY,
    )
    assert complete is False
    assert config["schema_version"] == 1
    assert config["config_path"] == str(settings.config_path)


def test_doctor_delegates_without_transforming_result(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    parser = build_parser(EMPTY_PLUGIN_REGISTRY)
    expected = {"schema": "fixture"}
    with patch("agent_workflow.cli_handlers.core.run_doctor", return_value=expected) as doctor:
        result, complete = handle_core_command(
            settings,
            _args("doctor"),
            parser=parser,
            plugin_registry=EMPTY_PLUGIN_REGISTRY,
        )
    assert result is expected
    assert complete is False
    doctor.assert_called_once_with(settings)


def test_completion_missing_extra_preserves_actionable_error(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    parser = build_parser(EMPTY_PLUGIN_REGISTRY)
    with patch.dict("sys.modules", {"shtab": None}):
        with pytest.raises(WorkflowError, match=r"agent-workflow\[completion\]"):
            handle_core_command(
                settings,
                _args("completion"),
                parser=parser,
                plugin_registry=EMPTY_PLUGIN_REGISTRY,
            )


def test_unknown_core_command_fails_closed(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    parser = build_parser(EMPTY_PLUGIN_REGISTRY)
    with pytest.raises(WorkflowError, match="unsupported core command"):
        handle_core_command(
            settings,
            _args("unknown"),
            parser=parser,
            plugin_registry=EMPTY_PLUGIN_REGISTRY,
        )
