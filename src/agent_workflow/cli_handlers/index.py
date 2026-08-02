"""Dispatch for the ``agent-workflow index`` command domain."""

from __future__ import annotations

import argparse
from typing import Any

from ..cli_output import print_json, print_table
from ..config import Settings
from ..index_store import (
    index_status,
    migrate_integrity_authority,
    query_index_report,
    record_integrity_authority,
    rebuild_index,
    sync_index,
    verify_index,
)


def handle_index_command(
    settings: Settings,
    args: argparse.Namespace,
) -> tuple[Any, bool]:
    """Return ``(data, output_complete)`` for one parsed index command."""
    if args.index_command == "status":
        return index_status(settings), False
    if args.index_command == "sync":
        return (
            sync_index(
                settings,
                session_id=args.session_id,
                include_archived=not args.active_only,
            ),
            False,
        )
    if args.index_command == "rebuild":
        return (
            rebuild_index(
                settings,
                session_id=args.session_id,
                include_archived=not args.active_only,
            ),
            False,
        )
    if args.index_command == "verify":
        return verify_index(settings, full=args.full, review_session_id=args.review_session_id), False
    if args.index_command == "integrity":
        if args.integrity_command == "migrate":
            return migrate_integrity_authority(settings), False
        return record_integrity_authority(
            settings,
            session_id=args.session_id,
            artifact_path=args.artifact_path,
            error_id=args.error_id,
            error_category=args.error_category,
            error_detail=args.error_detail,
        ), False

    report = query_index_report(
        settings,
        args.kind,
        session_id=args.session_id,
        state=args.state,
        category=args.category,
        executor=args.executor,
        model=args.model,
        pack_id=args.pack_id,
        limit=args.limit,
    )
    if args.json:
        print_json(report)
    else:
        print(
            "index: "
            f"{report['freshness']} "
            f"({report['current_run_count']} current, "
            f"{report['stale_run_count']} stale, "
            f"{report['error_count']} errors)"
        )
        rows = report["rows"]
        columns = [(key, key.upper()) for key in (rows[0].keys() if rows else [])]
        print_table(rows, columns)
    return None, True
