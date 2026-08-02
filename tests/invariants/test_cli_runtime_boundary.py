from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from agent_workflow.cli_parser import build_parser
from agent_workflow.cli_runtime import bootstrap_plugins, parse_args
from agent_workflow.config import defaults
from agent_workflow.plugins import EMPTY_PLUGIN_REGISTRY


def test_global_options_are_accepted_after_the_subcommand(tmp_path: Path) -> None:
    parser = build_parser(EMPTY_PLUGIN_REGISTRY)
    args = parse_args(
        parser,
        ["doctor", "--json", "--config", str(tmp_path / "config.toml")],
    )
    assert args.command == "doctor"
    assert args.json is True
    assert args.config == tmp_path / "config.toml"
    assert args.explicit_command is None


def test_launch_explicit_command_is_preserved_verbatim() -> None:
    parser = build_parser(EMPTY_PLUGIN_REGISTRY)
    args = parse_args(
        parser,
        [
            "launch",
            "session-1",
            "repo",
            "prompt.md",
            "--tier",
            "low",
            "--",
            "python",
            "-c",
            "print('ok')",
        ],
    )
    assert args.command == "launch"
    assert args.explicit_command == ["python", "-c", "print('ok')"]


def test_explicit_command_is_rejected_outside_launch() -> None:
    parser = build_parser(EMPTY_PLUGIN_REGISTRY)
    with pytest.raises(SystemExit) as exc:
        parse_args(parser, ["doctor", "--", "echo", "no"])
    assert exc.value.code == 2


def test_version_bypasses_broken_configuration_and_plugins(tmp_path: Path) -> None:
    config = tmp_path / "missing.toml"
    with (
        patch("agent_workflow.cli_runtime.load_settings") as load_settings,
        patch("agent_workflow.cli_runtime.load_plugin_registry") as load_plugins,
    ):
        settings, registry = bootstrap_plugins(["--config", str(config), "--version"])
    assert settings.config_path == config
    assert registry is EMPTY_PLUGIN_REGISTRY
    load_settings.assert_not_called()
    load_plugins.assert_not_called()


def test_bootstrap_preserves_explicit_plugin_suppression(tmp_path: Path) -> None:
    settings = defaults(tmp_path / "config.toml")
    object.__setattr__(settings, "plugins_enabled", ("fixture",))
    with (
        patch("agent_workflow.cli_runtime.load_settings", return_value=settings),
        patch(
            "agent_workflow.cli_runtime.load_plugin_registry",
            return_value=EMPTY_PLUGIN_REGISTRY,
        ) as load_plugins,
    ):
        returned, registry = bootstrap_plugins(["--no-plugins", "doctor"])
    assert returned is settings
    assert registry is EMPTY_PLUGIN_REGISTRY
    load_plugins.assert_called_once_with(("fixture",), suppress=True)
