"""CLI argument normalization and plugin-aware bootstrap services."""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from .config import defaults, load_settings
from .errors import WorkflowError


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
        if token in {"--config", "--decision-mode", "--decision-profile"}:
            if index + 1 >= len(raw):
                parser.error(f"argument {token}: expected one argument")
            normalized_globals.extend([token, raw[index + 1]])
            index += 2
            continue
        if token.startswith("--config=") or token.startswith("--decision-mode=") or token.startswith("--decision-profile="):
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



def top_level_command(argv: list[str] | None) -> str | None:
    """Return the requested top-level command without constructing/loading plugins."""
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--" in raw:
        raw = raw[: raw.index("--")]
    pre_parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    pre_parser.add_argument("--config", type=Path)
    pre_parser.add_argument("--json", action="store_true")
    pre_parser.add_argument("--no-plugins", action="store_true")
    pre_parser.add_argument("--decision-mode")
    pre_parser.add_argument("--decision-profile")
    pre_parser.add_argument("command", nargs="?")
    known, _ = pre_parser.parse_known_args(raw)
    return known.command


def plugins_required_for_command(argv: list[str] | None, builtin_commands: set[str]) -> bool:
    """Return whether parser construction/execution needs configured plugin registration.

    Normal built-in lifecycle commands intentionally skip plugin discovery. Plugin-aware
    inventory/help surfaces and unknown top-level commands still load plugins so enabled
    plugin commands remain available without becoming common-path startup cost.
    """
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--version" in raw:
        return False
    command = top_level_command(argv)
    if command is None:
        # Top-level help is a discovery surface. Load enabled plugins so their
        # commands appear in the live parser help. Recovery remains available
        # through ``--no-plugins --help`` when a configured plugin is broken.
        return ("--help" in raw or "-h" in raw) and "--no-plugins" not in raw
    # The inventory command discovers entry-point metadata without importing
    # enabled plugin code.  It must remain useful in recovery mode so callers
    # can see which configured plugins were deliberately suppressed.
    if command in {"plugins", "decision"}:
        return True
    if "--no-plugins" in raw:
        return False
    if command not in builtin_commands:
        return True
    if command in {"doctor", "completion"}:
        return True
    if command == "commands":
        try:
            role_index = raw.index("--role")
        except ValueError:
            return not any(token.startswith("--role=") and token.split("=", 1)[1] != "all" for token in raw)
        return role_index + 1 >= len(raw) or raw[role_index + 1] == "all"
    return False

def bootstrap_plugins(
    argv: list[str] | None,
    *,
    load_plugins: bool = True,
) -> tuple[Any, Any]:
    """Load settings and, when requested, the enabled plugin registry for one CLI run."""
    raw = list(sys.argv[1:] if argv is None else argv)
    if "--" in raw:
        raw = raw[: raw.index("--")]
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path)
    pre_parser.add_argument("--no-plugins", action="store_true")
    pre_parser.add_argument("--decision-mode")
    pre_parser.add_argument("--decision-profile")
    known, _ = pre_parser.parse_known_args(raw)
    # Version reporting must remain available even when local configuration or
    # a plugin is broken. All other commands honor configured strict loading.
    if "--version" in raw:
        return defaults(known.config), None
    settings = load_settings(known.config)
    if known.decision_mode:
        settings = replace(settings, decision_mode=known.decision_mode)
    if known.decision_profile:
        if known.decision_profile != "default" and known.decision_profile not in settings.decision_profiles:
            raise WorkflowError(f"decision profile is not configured: {known.decision_profile}")
        settings = replace(settings, decision_profile=known.decision_profile)
    if known.no_plugins and settings.decision_mode != "deterministic":
        if known.decision_mode:
            raise WorkflowError("--no-plugins cannot be combined with a plugin decision mode")
        settings = replace(settings, decision_mode="deterministic")
    if not load_plugins:
        return settings, None
    from .plugins import load_plugin_registry

    return settings, load_plugin_registry(
        settings.plugins_enabled,
        suppress=known.no_plugins,
    )
