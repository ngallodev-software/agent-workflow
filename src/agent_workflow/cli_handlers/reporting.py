"""Dispatch for sealed-run assessment and evaluation-ledger reporting."""

from __future__ import annotations

import argparse
import json
from typing import Any

from ..cli_output import print_json
from ..config import Settings
from ..eval.assessment import assess_exported_runs
from ..errors import WorkflowError
from ..ledger import build_ledger, render_ledger
from ..state import runs_root
from ..util import atomic_write_json, expand_path

REPORTING_COMMANDS = frozenset({"assess-sealed-runs", "ledger"})


def handle_reporting_command(
    settings: Settings,
    args: argparse.Namespace,
) -> tuple[Any, bool]:
    """Execute sealed-run assessment or ledger reporting.

    The boolean result is true when the handler emitted the complete response.
    """
    if args.command == "assess-sealed-runs":
        data = assess_exported_runs(expand_path(args.root))
        if args.output:
            atomic_write_json(expand_path(args.output), data)
        print_json(data)
        return None, True

    if args.command == "ledger":
        value = build_ledger(
            expand_path(args.pack),
            expand_path(args.runs_root) if args.runs_root else runs_root(settings),
        )
        rendered = (
            json.dumps(value, indent=2, sort_keys=True) + "\n"
            if args.json
            else render_ledger(value)
        )
        if args.output:
            output = expand_path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            return {"output": str(output), "row_count": len(value["rows"])}, False
        print(rendered, end="")
        return None, True

    raise WorkflowError(f"unsupported reporting command: {args.command}")
