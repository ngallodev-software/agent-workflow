from __future__ import annotations

import argparse
import sys
from typing import Any

from . import __version__
from .cli_contract import BUILTIN_TOP_LEVEL_COMMANDS, CORE_COMMANDS, REPORTING_COMMANDS
from .cli_parser import build_parser
from .cli_runtime import bootstrap_plugins, parse_args, plugins_required_for_command, top_level_command
from .cli_output import print_json as _print_json
from .cli_output import print_mapping as _print_mapping
from .errors import WorkflowError




def main(argv: list[str] | None = None) -> int:
    args: argparse.Namespace | None = None
    try:
        requested_command = top_level_command(argv)
        load_plugins = plugins_required_for_command(argv, set(BUILTIN_TOP_LEVEL_COMMANDS))
        settings, plugin_registry = bootstrap_plugins(argv, load_plugins=load_plugins)
        # Plugin-aware surfaces need the complete tree. Normal built-in commands
        # materialize only their own top-level branch from the same parser source.
        parser = (
            build_parser(plugin_registry)
            if load_plugins
            else build_parser(command_scope=requested_command)
        )
        args = parse_args(parser, argv)
        data: Any

        if hasattr(args, "_plugin_execute"):
            from .plugin_api import PluginExecutionContext

            data = args._plugin_execute(
                args,
                PluginExecutionContext(
                    settings=settings,
                    json_output=args.json,
                    host_version=__version__,
                ),
            )
        elif args.command in CORE_COMMANDS:
            from .cli_handlers.core import handle_core_command

            data, output_complete = handle_core_command(
                settings,
                args,
                parser=parser,
                plugin_registry=plugin_registry,
            )
            if output_complete:
                return 0
        elif args.command == "orchestrator":
            from .cli_handlers.orchestrator import handle_orchestrator_command

            data = handle_orchestrator_command(settings, args)
        elif args.command == "delegate":
            from .cli_handlers.delegate import handle_delegate_command

            data = handle_delegate_command(settings, args)
        elif args.command == "worktree":
            from .cli_handlers.worktree import handle_worktree_command

            data = handle_worktree_command(settings, args)
        elif args.command == "agent-run":
            from .cli_handlers.agent_run import handle_agent_run_command

            data, output_complete = handle_agent_run_command(
                settings,
                args,
                argv=argv,
            )
            if output_complete:
                return 0
        elif args.command == "workflow":
            from .cli_handlers.workflow import handle_workflow_command

            data, output_complete = handle_workflow_command(settings, args)
            if output_complete:
                return 0
        elif args.command in REPORTING_COMMANDS:
            from .cli_handlers.reporting import handle_reporting_command

            data, output_complete = handle_reporting_command(settings, args)
            if output_complete:
                return 0
        elif args.command == "supervisor":
            from .cli_handlers.supervisor import handle_supervisor_command

            data = handle_supervisor_command(settings, args)
        elif args.command == "index":
            from .cli_handlers.index import handle_index_command

            data, output_complete = handle_index_command(settings, args)
            if output_complete:
                return 0
        elif args.command == "agent":
            from .cli_handlers.agent import handle_agent_command

            data = handle_agent_command(settings, args)
        elif args.command == "eval":
            from .cli_handlers.eval import handle_eval_command

            data, output_complete = handle_eval_command(settings, args)
            if output_complete:
                return 0
        elif args.command == "benchmark":
            from .cli_handlers.benchmark import handle_benchmark_command

            data = handle_benchmark_command(settings, args)
        elif args.command == "pack":
            from .cli_handlers.pack import handle_pack_command

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
    except WorkflowError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
