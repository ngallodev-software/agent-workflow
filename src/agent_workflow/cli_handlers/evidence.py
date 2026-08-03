"""Dispatch for append-only supplemental evidence repair commands."""

from __future__ import annotations

import argparse

from ..config import Settings
from ..evidence_repair import (
    create_evidence_repair,
    list_evidence_repairs,
    verify_evidence_repair,
)


def handle_evidence_command(settings: Settings, args: argparse.Namespace):
    if args.evidence_command == "repair":
        return create_evidence_repair(
            settings,
            source_session_id=args.source_run,
            source_receipt_sha256=args.source_receipt,
            source_artifact_path=args.artifact,
            adapter=args.adapter,
            output_run=args.output_run,
            actor=args.actor,
        )
    if args.evidence_command == "verify":
        return verify_evidence_repair(settings, args.repair_id)
    if args.evidence_command == "list":
        rows = list_evidence_repairs(settings, source_session_id=args.source_run)
        return {"schema": "agent-workflow/evidence-repair-list/v1", "repairs": rows, "count": len(rows)}
    raise AssertionError(f"unhandled evidence command: {args.evidence_command}")
