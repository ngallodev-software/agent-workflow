"""Dispatch for the ``agent-workflow agent`` command domain."""

from __future__ import annotations

import argparse
from typing import Any

from ..agent_context import complete_task as complete_agent_task
from ..agent_context import read as read_agent_context
from ..config import Settings
from ..completion import validate_completion_handoff
from ..state import run_dir
from ..roles import public_role_catalog


def handle_agent_command(settings: Settings, args: argparse.Namespace) -> Any:
    """Execute one parsed Agent Run worker-context command."""
    if args.agent_command == "context":
        return read_agent_context(settings, args.agent_run_id)
    if args.agent_command == "roles":
        catalog = public_role_catalog(settings.role_paths)
        if args.role_id is None:
            return catalog
        matches = [item for item in catalog["roles"] if item.get("id") == args.role_id]
        if not matches:
            raise ValueError(f"unknown agent role: {args.role_id}")
        return matches[0]
    if args.agent_command == "completion-validate":
        return validate_completion_handoff(run_dir(settings, args.agent_run_id))
    if args.agent_command == "task-complete":
        return complete_agent_task(
            settings,
            args.agent_run_id,
            actor=args.actor,
            summary=args.summary,
            tags=args.tag,
            files=args.file,
            terminal=True,
        )
    raise ValueError(f"unsupported agent command: {args.agent_command}")
