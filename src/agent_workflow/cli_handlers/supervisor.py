"""Dispatch for the ``agent-workflow supervisor`` command domain."""

from __future__ import annotations

import argparse
from typing import Any

from ..config import Settings
from ..supervisor import SupervisorOptions, supervise_loop, supervise_once


def handle_supervisor_command(settings: Settings, args: argparse.Namespace) -> Any:
    """Execute one parsed supervisor command without changing service policy."""
    options = SupervisorOptions.from_settings(
        settings,
        capture_interactive=args.capture_interactive,
        capture_lines=args.capture_lines,
        probe_stalled=args.probe_stalled,
        interrupt_stalled=args.interrupt_stalled,
        restart_orphaned=args.restart_orphaned,
        max_remediation_attempts=args.max_remediation_attempts,
        sync_index_enabled=args.sync_index,
    )
    if args.supervisor_command == "once":
        return supervise_once(
            settings,
            session_ids=args.session,
            options=options,
        )
    reports = supervise_loop(
        settings,
        interval_seconds=args.interval_seconds,
        max_cycles=args.max_cycles,
        session_ids=args.session,
        options=options,
    )
    return {
        "schema": "agent-workflow/supervisor-loop-report/v1",
        "cycle_count": len(reports),
        "reports": reports,
    }
