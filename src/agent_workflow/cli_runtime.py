"""CLI argument normalization and plugin-aware bootstrap services."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .config import defaults, load_settings
from .plugins import EMPTY_PLUGIN_REGISTRY, PluginRegistry, load_plugin_registry


def parse_args(
    parser: argparse.ArgumentParser,
    argv: list[str] | None,
) -> argparse.Namespace:
    """Parse CLI arguments while preserving global-option and Agent Run prepare rules."""
    raw = list(sys.argv[1:] if argv is None else argv)
    explicit_command: list[str] | None = None
    if "--" in raw:
        separator = raw.index("--")
        explicit_command = raw[separator + 1 :]
        raw = raw[:separator]
        if not explicit_command:
            parser.error("missing explicit command after --")

    normalized_globals: list[str] = []
    normalized_rest: list[str] = []
    index = 0
    while index < len(raw):
        token = raw[index]
        if token in {"--json", "--no-plugins"}:
            normalized_globals.append(token)
            index += 1
            continue
        if token == "--config":
            if index + 1 >= len(raw):
                parser.error("argument --config: expected one argument")
            normalized_globals.extend([token, raw[index + 1]])
            index += 2
            continue
        if token.startswith("--config="):
            normalized_globals.append(token)
            index += 1
            continue
        normalized_rest.append(token)
        index += 1

    if explicit_command is not None and normalized_rest[:2] != ["agent-run", "prepare"]:
        parser.error("-- COMMAND is only supported by agent-run prepare")

    args = parser.parse_args(normalized_globals + normalized_rest)
    setattr(args, "explicit_command", explicit_command)
    return args


def bootstrap_plugins(
    argv: list[str] | None,
) -> tuple[Any, PluginRegistry]:
    """Load settings and the explicitly enabled plugin registry for one CLI run."""
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--" in raw:
        raw = raw[: raw.index("--")]
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path)
    pre_parser.add_argument("--no-plugins", action="store_true")
    known, _ = pre_parser.parse_known_args(raw)
    # Version reporting must remain available even when local configuration or
    # a plugin is broken. All other commands honor configured strict loading.
    if "--version" in raw:
        return defaults(known.config), EMPTY_PLUGIN_REGISTRY
    settings = load_settings(known.config)
    return settings, load_plugin_registry(
        settings.plugins_enabled,
        suppress=known.no_plugins,
    )
