"""Dispatch for core catalog, configuration, doctor, plugin, and completion commands."""

from __future__ import annotations

import argparse
from typing import Any

from ..cli_output import print_json
from ..cli_parser import build_parser
from ..command_catalog import build_command_catalog, filter_catalog, render_command_markdown
from ..config import Settings, as_dict
from ..doctor import run_doctor
from ..errors import WorkflowError
from ..plugins import PluginRegistry

CORE_COMMANDS = frozenset({"commands", "plugins", "doctor", "completion", "config"})


def handle_core_command(
    settings: Settings,
    args: argparse.Namespace,
    *,
    parser: argparse.ArgumentParser,
    plugin_registry: PluginRegistry,
) -> tuple[Any, bool]:
    """Execute a parsed core utility command.

    The boolean result is true when the handler has emitted the complete user
    response and the shared CLI renderer must not run.
    """
    if args.command == "commands":
        catalog = build_command_catalog(
            parser,
            plugin_inventory=plugin_registry.catalog_inventory(),
        )
        output_format = args.format or ("json" if args.json else "markdown")
        if output_format == "json":
            print_json(filter_catalog(catalog, args.role))
        else:
            print(render_command_markdown(catalog, role=args.role), end="")
        return None, True

    if args.command == "plugins":
        return {
            "configured_enabled": list(settings.plugins_enabled),
            "suppressed": bool(args.no_plugins),
            "plugins": plugin_registry.inventory(),
        }, False

    if args.command == "doctor":
        return run_doctor(settings), False

    if args.command == "completion":
        try:
            import shtab
        except ModuleNotFoundError as exc:
            raise WorkflowError(
                "shell completion requires: pip install 'agent-workflow[completion]'"
            ) from exc
        print(shtab.complete(build_parser(plugin_registry), shell=args.shell), end="")
        return None, True

    if args.command == "config":
        return as_dict(settings), False

    raise WorkflowError(f"unsupported core command: {args.command}")
