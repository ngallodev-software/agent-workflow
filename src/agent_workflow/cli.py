from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from .command_catalog import (
    build_command_catalog,
    filter_catalog,
    render_command_markdown,
)
from .cli_parser import build_parser
from .cli_handlers.index import handle_index_command
from .cli_handlers.workflow import handle_workflow_command
from .cli_handlers.worktree import handle_worktree_command
from .cli_handlers.pack import handle_pack_command
from .cli_handlers.orchestrator import handle_orchestrator_command
from .cli_handlers.agent import handle_agent_command
from .cli_handlers.eval import handle_eval_command
from .cli_handlers.benchmark import handle_benchmark_command
from .cli_handlers.session import SESSION_COMMANDS, handle_session_command
from .cli_handlers.supervisor import handle_supervisor_command
from .cli_output import print_json as _print_json
from .cli_output import print_mapping as _print_mapping
from .cli_output import print_table as _print_table
from .config import as_dict, defaults, load_settings
from .doctor import run_doctor
from .eval.assessment import assess_exported_runs
from .errors import InteractiveCapacityError, WorkflowError
from .ledger import build_ledger, render_ledger
from .plugin_api import PluginExecutionContext
from .plugins import EMPTY_PLUGIN_REGISTRY, PluginRegistry, load_plugin_registry
from .receipts import verify_seal_details
from .state import runs_root
from .util import atomic_write_json, expand_path




def _verified_receipt_hash(run: Path) -> str:
    """Return the digest of the exact receipt verified from stable bytes."""
    _, digest = verify_seal_details(run)
    return digest






def _parse_args(
    parser: argparse.ArgumentParser,
    argv: list[str] | None,
) -> argparse.Namespace:
    raw = list(sys.argv[1:] if argv is None else argv)
    explicit_command: list[str] | None = None
    if "--" in raw:
        separator = raw.index("--")
        if "launch" not in raw[:separator]:
            parser.error("-- COMMAND is only supported by launch")
        explicit_command = raw[separator + 1 :]
        raw = raw[:separator]
        if not explicit_command:
            parser.error("missing explicit command after --")
    # argparse normally requires global options before the subcommand.  The
    # workflow CLI accepts --json and --config in either position because the
    # documented/operator-friendly form is often `command --json`.  Only the
    # portion before an explicit launch `-- COMMAND...` separator is normalized.
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

    args = parser.parse_args(normalized_globals + normalized_rest)
    setattr(args, "explicit_command", explicit_command)
    return args


def _bootstrap_plugins(
    argv: list[str] | None,
) -> tuple[Any, PluginRegistry]:
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




def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace | None = None
    try:
        settings, plugin_registry = _bootstrap_plugins(argv)
        parser = build_parser(plugin_registry)
        args = _parse_args(parser, argv)
        if args.command == "commands":
            catalog = build_command_catalog(
                parser,
                plugin_inventory=plugin_registry.catalog_inventory(),
            )
            output_format = args.format or ("json" if args.json else "markdown")
            if output_format == "json":
                _print_json(filter_catalog(catalog, args.role))
            else:
                print(render_command_markdown(catalog, role=args.role), end="")
            return 0
        data: Any

        if hasattr(args, "_plugin_execute"):
            data = args._plugin_execute(
                args,
                PluginExecutionContext(
                    settings=settings,
                    json_output=args.json,
                    host_version=__version__,
                ),
            )
        elif args.command == "plugins":
            data = {
                "configured_enabled": list(settings.plugins_enabled),
                "suppressed": bool(args.no_plugins),
                "plugins": plugin_registry.inventory(),
            }
        elif args.command == "doctor":
            data = run_doctor(settings)
        elif args.command == "completion":
            try:
                import shtab
            except ModuleNotFoundError as exc:
                raise WorkflowError(
                    "shell completion requires: pip install 'agent-workflow[completion]'"
                ) from exc
            print(shtab.complete(build_parser(plugin_registry), shell=args.shell), end="")
            return 0
        elif args.command == "config":
            data = as_dict(settings)
        elif args.command == "orchestrator":
            data = handle_orchestrator_command(settings, args)
        elif args.command == "worktree":
            data = handle_worktree_command(settings, args)
        elif args.command in SESSION_COMMANDS:
            data, output_complete = handle_session_command(
                settings,
                args,
                argv=argv,
            )
            if output_complete:
                return 0
        elif args.command == "workflow":
            data, output_complete = handle_workflow_command(settings, args)
            if output_complete:
                return 0
        elif args.command == "assess-sealed-runs":
            data = assess_exported_runs(expand_path(args.root))
            if args.output:
                output = expand_path(args.output)
                atomic_write_json(output, data)
            _print_json(data)
            return 0
        elif args.command == "ledger":
            value = build_ledger(
                expand_path(args.pack),
                expand_path(args.runs_root) if args.runs_root else runs_root(settings),
            )
            rendered = json.dumps(value, indent=2, sort_keys=True) + "\n" if args.json else render_ledger(value)
            if args.output:
                output = expand_path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(rendered, encoding="utf-8")
                data = {"output": str(output), "row_count": len(value["rows"])}
            else:
                print(rendered, end="")
                return 0
        elif args.command == "supervisor":
            data = handle_supervisor_command(settings, args)
        elif args.command == "index":
            data, output_complete = handle_index_command(settings, args)
            if output_complete:
                return 0
        elif args.command == "agent":
            data = handle_agent_command(settings, args)
        elif args.command == "eval":
            data, output_complete = handle_eval_command(settings, args)
            if output_complete:
                return 0
        elif args.command == "benchmark":
            data = handle_benchmark_command(settings, args)
        elif args.command == "pack":
            data, exit_code = handle_pack_command(settings, args)
            if exit_code is not None:
                return exit_code
        else:
            parser.error("unhandled command")
            return 2

        if args.json:
            _print_json(data)
        elif isinstance(data, dict):
            _print_mapping(data)
        else:
            _print_json(data)
        return 0
    except InteractiveCapacityError as exc:
        if bool(getattr(args, "json", False)):
            _print_json(exc.as_dict())
        else:
            print(f"error: {exc}", file=sys.stderr)
        return 2
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
