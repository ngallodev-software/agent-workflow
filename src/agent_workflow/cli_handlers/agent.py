"""Dispatch for the ``agent-workflow agent`` command domain."""

from __future__ import annotations

import argparse
from typing import Any

from ..config import Settings


def handle_agent_command(settings: Settings, args: argparse.Namespace) -> Any:
    """Execute one parsed Agent Run worker-context command."""
    if hasattr(args, "agent_run_id") and args.agent_command in {
        "criterion", "limitation", "finish"
    }:
        from ..worker_completion import record_protocol_cli

        record_protocol_cli(settings, args.agent_run_id, args.agent_command)
    if args.agent_command == "roles":
        from ..roles import public_role_catalog

        catalog = public_role_catalog(settings.role_paths)
        if args.role_id is None:
            return catalog
        matches = [item for item in catalog["roles"] if item.get("id") == args.role_id]
        if not matches:
            raise ValueError(f"unknown agent role: {args.role_id}")
        return matches[0]
    if args.agent_command == "criterion":
        from ..worker_completion import record_criterion

        return record_criterion(
            settings, args.agent_run_id, criterion_id=args.criterion_id,
            result=args.result, evidence=args.evidence, evidence_files=args.evidence_file,
        )
    if args.agent_command == "limitation":
        from ..worker_completion import record_limitation

        return record_limitation(
            settings,
            args.agent_run_id,
            limitation_id=args.limitation_id,
            evidence=args.evidence,
            evidence_files=args.evidence_file,
        )
    if args.agent_command == "finish":
        from ..worker_completion import finish

        return finish(
            settings, args.agent_run_id, result=args.result,
            unresolved=args.unresolved, review_disposition=args.review_disposition,
        )
    raise ValueError(f"unsupported agent command: {args.agent_command}")
