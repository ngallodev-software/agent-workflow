"""Dispatch for the ``agent-workflow pack`` command domain."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from ..cli_output import print_json
from ..config import Settings
from ..manifests import validate_pack, write_checksum_manifest
from ..pack import archive as archive_pack
from ..pack import scaffold as scaffold_pack
from ..path import absolute_path


def handle_pack_command(
    settings: Settings,
    args: argparse.Namespace,
) -> tuple[Any, int | None]:
    """Return ``(data, exit_code)`` for one parsed prompt-pack command.

    ``exit_code`` is non-``None`` only when this handler has already rendered the
    complete command output and the CLI should return immediately.
    """
    if args.pack_command == "scaffold":
        return scaffold_pack(args.destination, args.phases, args.name), None
    if args.pack_command == "validate":
        report = validate_pack(
            absolute_path(args.source),
            verify_checksums=args.verify_checksums,
        )
        data = report.as_dict()
        if args.json:
            print_json(data)
        else:
            print(f"pack: {report.root}")
            print(
                f"phases: {report.phases}; tasks: {report.tasks}; "
                f"valid: {report.ok}"
            )
            for warning in report.warnings:
                print(f"warning: {warning}")
            for error in report.errors:
                print(f"error: {error}", file=sys.stderr)
        return None, 0 if report.ok else 1
    if args.pack_command == "checksum":
        path = write_checksum_manifest(absolute_path(args.source))
        return {"manifest": str(path)}, None
    return archive_pack(settings, args.source, args.output), None
