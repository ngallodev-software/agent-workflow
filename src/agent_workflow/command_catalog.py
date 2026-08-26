from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Iterable

from . import __version__
from .contracts import validate_instance
from .errors import WorkflowError
from .path import read_regular_file
from .util import atomic_write_bytes

COMMAND_CATALOG_SCHEMA = "agent-workflow/command-catalog/v1"
COMMAND_CATALOG_FILENAME = "command-catalog.json"
COMMAND_CARD_FILENAME = "command-card.md"
COMMAND_ROLES = ("orchestrator", "implementation", "review")

_ROLE_COMMANDS: dict[str, frozenset[str]] = {
    "implementation": frozenset(
        {
            "agent-run status",
            "agent-run progress",
            "agent-run ack",
            "agent-run watch",
            "agent context",
            "agent completion-validate",
            "agent task-complete",
        }
    ),
    "review": frozenset(
        {
            "agent-run status",
            "agent-run progress",
            "agent-run ack",
            "agent-run watch",
            "agent context",
            "agent completion-validate",
            "agent task-complete",
            "assess-sealed-runs",
            "ledger",
            "eval report",
            "eval benchmark-report",
        }
    ),
    "orchestrator": frozenset(
        {
            "doctor",
            "commands",
            "config show",
            "orchestrator registry create",
            "orchestrator registry inspect",
            "orchestrator registry register",
            "orchestrator registry unregister",
            "orchestrator inbox import",
            "orchestrator inbox list",
            "orchestrator inbox read",
            "orchestrator watch",
            "worktree create",
            "worktree list",
            "worktree remove",
            "worktree closeout",
            "worktree closeout-verify",
            "agent-run prepare",
            "agent-run start",
            "agent-run list",
            "agent-run archive",
            "agent-run status",
            "agent-run repair",
            "agent-run finalize",
            "agent-run tail",
            "agent-run steer",
            "agent-run progress",
            "agent-run ack",
            "agent-run watch",
            "agent-run interrupt",
            "agent-run terminate",
            "agent-run restart",
            "agent-run review",
            "agent-run accept",
            "agent-run reject",
            "agent-run force-accept",
            "supervisor once",
            "supervisor run",
            "index status",
            "index sync",
            "index rebuild",
            "index verify",
            "index query",
            "agent context",
            "agent roles",
            "workflow validate",
            "workflow start",
            "workflow status",
            "workflow resume",
            "workflow seal",
            "workflow verify",
            "assess-sealed-runs",
            "ledger",
            "eval validate",
            "eval validate-benchmark",
            "eval report",
            "eval benchmark-report",
            "pack validate",
            "pack checksum",
            "pack archive",
        }
    ),
}



def role_for_agent_class(agent_class: str | None) -> str:
    value = (agent_class or "").strip().lower()
    if "orchestrat" in value or "coordinator" in value:
        return "orchestrator"
    if "review" in value or "gate" in value or "audit" in value:
        return "review"
    return "implementation"


def _json_value(value: Any) -> Any:
    if value is argparse.SUPPRESS:
        return None
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return str(value)


def _type_name(action: argparse.Action) -> str:
    value = getattr(action, "type", None)
    if value is Path:
        return "path"
    if value is int:
        return "integer"
    if value is float:
        return "number"
    if value is None:
        if isinstance(
            action,
            (
                argparse._StoreTrueAction,
                argparse._StoreFalseAction,
                argparse.BooleanOptionalAction,
            ),
        ):
            return "boolean"
        return "string"
    return getattr(value, "__name__", str(value))


def _nargs(value: Any) -> str | int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return str(value)


def _action_record(action: argparse.Action) -> dict[str, Any]:
    record: dict[str, Any] = {
        "dest": action.dest,
        "required": bool(getattr(action, "required", False)),
        "nargs": _nargs(action.nargs),
        "type": _type_name(action),
        "default": _json_value(action.default),
        "help": None if action.help in {None, argparse.SUPPRESS} else str(action.help),
    }
    choices = getattr(action, "choices", None)
    if choices is not None:
        record["choices"] = [_json_value(item) for item in choices]
    metavar = getattr(action, "metavar", None)
    if metavar is not None:
        record["metavar"] = _json_value(metavar)
    return record


def _parser_arguments(parser: argparse.ArgumentParser) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    positionals: list[dict[str, Any]] = []
    options: list[dict[str, Any]] = []
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        if action.help is argparse.SUPPRESS:
            continue
        record = _action_record(action)
        if action.option_strings:
            record["flags"] = list(action.option_strings)
            options.append(record)
        else:
            positionals.append(record)
    return positionals, options


def _subparser_help(action: argparse._SubParsersAction) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for choice in action._choices_actions:
        result[str(choice.dest)] = None if choice.help in {None, argparse.SUPPRESS} else str(choice.help)
    return result


def _normalized_usage(parser: argparse.ArgumentParser) -> str:
    usage = parser.format_usage().strip()
    if usage.startswith("usage: "):
        usage = usage[7:]
    return " ".join(usage.replace(" [-h]", "").split())


def _walk_commands(
    parser: argparse.ArgumentParser,
    *,
    path: tuple[str, ...] = (),
    summary: str | None = None,
) -> Iterable[dict[str, Any]]:
    subparsers = [
        action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
    ]
    if not subparsers:
        positionals, options = _parser_arguments(parser)
        yield {
            "path": list(path),
            "command": " ".join(path),
            "summary": summary,
            "synopsis": _normalized_usage(parser),
            "positionals": positionals,
            "options": options,
        }
        return
    for subparser_action in subparsers:
        help_by_name = _subparser_help(subparser_action)
        seen: set[int] = set()
        for name, child in sorted(subparser_action.choices.items()):
            identity = id(child)
            if identity in seen:
                continue
            seen.add(identity)
            yield from _walk_commands(
                child,
                path=(*path, name),
                summary=help_by_name.get(name),
            )


def build_command_catalog(
    parser: argparse.ArgumentParser,
    *,
    plugin_inventory: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    global_positionals, global_options = _parser_arguments(parser)
    if global_positionals:
        raise WorkflowError("top-level command parser unexpectedly contains positionals")
    catalog = {
        "schema": COMMAND_CATALOG_SCHEMA,
        "version": 1,
        "application": {
            "name": "agent-workflow",
            "version": __version__,
            "cli_invocation": ["agent-workflow"],
        },
        "global_options": global_options,
        "commands": sorted(_walk_commands(parser), key=lambda item: item["command"]),
        "plugins": list(plugin_inventory),
    }
    validate_instance(catalog, COMMAND_CATALOG_SCHEMA, artifact="command catalog")
    return catalog


def filter_catalog(catalog: dict[str, Any], role: str | None) -> dict[str, Any]:
    if role is None or role == "all":
        return catalog
    if role not in COMMAND_ROLES:
        raise WorkflowError(f"unknown command-card role: {role}")
    allowed = set(_ROLE_COMMANDS[role])
    represented = {str(item["command"]) for item in catalog["commands"]}
    if role == "orchestrator":
        plugin_roots = {
            str(command)
            for plugin in catalog.get("plugins", [])
            for command in plugin.get("commands", [])
        }
        allowed.update(
            command
            for command in represented
            if command.split(" ", 1)[0] in plugin_roots
        )
    missing = sorted(allowed - represented)
    if missing:
        raise WorkflowError(
            f"command-card role {role!r} references missing parser commands: {missing}"
        )
    filtered = dict(catalog)
    filtered["role"] = role
    filtered["commands"] = [
        item for item in catalog["commands"] if str(item["command"]) in allowed
    ]
    return filtered


def render_command_markdown(catalog: dict[str, Any], *, role: str | None = None) -> str:
    selected = filter_catalog(catalog, role)
    title = "Agent-workflow command catalog" if role in {None, "all"} else f"Agent-workflow {role} command card"
    lines = [
        f"# {title}",
        "",
        f"Catalog schema: `{catalog['schema']}`",
        f"Application version: `{catalog['application']['version']}`",
        "",
        "Use these signatures directly. Do not run `--help` for a command represented here.",
        "Use `--help` only after a catalog/version mismatch, an argument error, or when a required command is absent.",
        "Global `--json` and `--config PATH` may appear before or after a subcommand.",
        "",
    ]
    for item in selected["commands"]:
        lines.append(f"## `{item['command']}`")
        lines.append("")
        if item.get("summary"):
            lines.append(str(item["summary"]))
            lines.append("")
        lines.extend(["```text", str(item["synopsis"]), "```", ""])
    return "\n".join(lines).rstrip() + "\n"


def encode_command_catalog(catalog: dict[str, Any]) -> bytes:
    return (json.dumps(catalog, indent=2, sort_keys=True) + "\n").encode("utf-8")


def command_catalog_sha256(catalog: dict[str, Any]) -> str:
    return hashlib.sha256(encode_command_catalog(catalog)).hexdigest()


def runtime_command_catalog(
    settings: Any | None = None,
    *,
    no_plugins: bool = False,
) -> dict[str, Any]:
    # Imported lazily to avoid a module-import cycle while Agent Run preparation
    # writes the catalog only after the CLI module is fully initialized.
    from .cli import build_parser
    from .plugins import EMPTY_PLUGIN_REGISTRY, load_plugin_registry

    registry = (
        load_plugin_registry(settings.plugins_enabled, suppress=no_plugins)
        if settings is not None
        else EMPTY_PLUGIN_REGISTRY
    )
    return build_command_catalog(
        build_parser(registry),
        plugin_inventory=registry.catalog_inventory(),
    )


def resolve_cli_executable() -> str:
    launched_as = Path(sys.argv[0])
    if launched_as.is_absolute() and launched_as.is_file() and os.access(launched_as, os.X_OK):
        return str(launched_as.resolve())
    return shutil.which("agent-workflow") or "agent-workflow"


def write_launch_command_artifacts(
    state_dir: Path,
    *,
    role: str,
    settings: Any | None = None,
    agent_visible_dir: Path | None = None,
) -> dict[str, Any]:
    catalog = filter_catalog(runtime_command_catalog(settings), role)
    catalog_path = state_dir / COMMAND_CATALOG_FILENAME
    card_path = state_dir / COMMAND_CARD_FILENAME
    atomic_write_bytes(catalog_path, encode_command_catalog(catalog), mode=0o444)
    card = render_command_markdown(catalog, role=role).encode("utf-8")
    atomic_write_bytes(card_path, card, mode=0o444)
    if agent_visible_dir is not None:
        agent_visible_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(
            agent_visible_dir / COMMAND_CATALOG_FILENAME,
            encode_command_catalog(catalog),
            mode=0o444,
        )
        atomic_write_bytes(
            agent_visible_dir / COMMAND_CARD_FILENAME,
            card,
            mode=0o444,
        )
    # Re-read through the safe regular-file boundary before binding digests.
    catalog_read = read_regular_file(catalog_path)
    card_read = read_regular_file(card_path)
    if json.loads(catalog_read.data.decode("utf-8")) != catalog:
        raise WorkflowError("command catalog changed during launch preparation")
    return {
        "role": role,
        "catalog_path": COMMAND_CATALOG_FILENAME,
        "catalog_sha256": catalog_read.sha256,
        "catalog_schema": COMMAND_CATALOG_SCHEMA,
        "card_path": COMMAND_CARD_FILENAME,
        "card_sha256": card_read.sha256,
        "cli_invocation": [resolve_cli_executable()],
    }
