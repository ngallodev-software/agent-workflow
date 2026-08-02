"""Dispatch for the ``agent-workflow workflow`` command domain."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ..cli_output import print_json
from ..config import Settings
from ..scheduler import SchedulerService
from ..util import atomic_write_json, expand_path, read_json
from ..workflow import snapshot_sha256
from ..workflow_service import WorkflowService
from ..workflow_templates import expand_workflow_template


def handle_workflow_command(
    settings: Settings,
    args: argparse.Namespace,
) -> tuple[Any, bool]:
    """Return ``(data, output_complete)`` for one parsed workflow command."""
    if args.workflow_command == "template":
        spec = read_json(expand_path(args.spec))
        snapshot = expand_workflow_template(
            args.template,
            workflow_id=str(spec.get("workflow_id", "")),
            pack_id=str(spec.get("pack_id", "")),
            pack_manifest_sha256=str(spec.get("pack_manifest_sha256", "")),
            parameters=spec.get("parameters", {}),
        )
        output = expand_path(args.output)
        atomic_write_json(output, snapshot)
        data = {"output": str(output), "snapshot_sha256": snapshot_sha256(snapshot)}
        if args.json:
            print_json(data)
        else:
            print(output)
        return None, True

    run_dir = expand_path(getattr(args, "run_dir", Path.cwd()))
    service = WorkflowService(
        scheduler=SchedulerService(
            settings=settings,
            run_dir=run_dir,
            workdir=run_dir,
        )
    )
    if args.workflow_command == "validate":
        return service.validate(args.snapshot), False
    if args.workflow_command == "start":
        return service.start(args.snapshot), False
    if args.workflow_command == "status":
        return service.status(args.snapshot), False
    if args.workflow_command == "resume":
        return service.resume(args.snapshot), False
    if args.workflow_command == "seal":
        return service.seal(args.snapshot), False
    return service.verify(args.snapshot), False
