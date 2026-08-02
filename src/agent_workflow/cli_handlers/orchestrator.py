"""Dispatch for the ``agent-workflow orchestrator`` command domain."""

from __future__ import annotations

import argparse
from typing import Any

from ..config import Settings
from ..orchestrator_inbox import (
    create_registry,
    import_registered,
    read_child_registry,
    read_inbox,
    register_child,
    unregister_child,
)
from ..orchestrator_supervisor import watch as watch_orchestrator


def handle_orchestrator_command(settings: Settings, args: argparse.Namespace) -> Any:
    """Execute one parsed orchestrator registry, inbox, or watch command."""
    if args.orchestrator_command == "registry":
        if args.registry_command == "create":
            return create_registry(
                settings, args.orchestrator_id, workflow_id=args.workflow_id
            )
        if args.registry_command == "inspect":
            return read_child_registry(settings, args.orchestrator_id)
        if args.registry_command == "register":
            return register_child(settings, args.orchestrator_id, args.session_id)
        return unregister_child(
            settings, args.orchestrator_id, args.session_id, state=args.state
        )

    if args.orchestrator_command == "watch":
        return watch_orchestrator(
            settings,
            args.orchestrator_id,
            interval_seconds=args.interval_seconds,
            poll_seconds=args.poll_seconds,
            batch_size=args.batch_size,
            max_per_child=args.max_per_child,
            max_cycles=args.max_cycles,
        )
    if args.inbox_command == "import":
        return import_registered(
            settings,
            args.orchestrator_id,
            session_id=args.session_id,
            max_per_child=args.max_per_child,
        )
    return read_inbox(
        settings,
        args.orchestrator_id,
        after_sequence=args.after,
        limit=args.limit,
        event_id=args.event_id,
        include_content=args.include_content,
    )
